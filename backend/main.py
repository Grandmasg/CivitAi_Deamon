# --- Standard imports always first ---
import os
import json
import threading
import asyncio
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from fastapi import Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.daemon import make_queue_item, DownloadDaemon, ws_manager
from backend.database import get_all_metrics, log_download, log_error
from backend import sdsage
from loguru import logger

# App instance and universal logging middleware (after app creation)
from contextlib import asynccontextmanager


def load_secret_key():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            key = config.get('jwt_secret')
            if key:
                return key
    return "CHANGE_THIS_SECRET"


# --- Loguru file logging setup (also if main.py is loaded directly) ---
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(log_dir, exist_ok=True)

if not any([h._name == 'daemon.log' for h in logger._core.handlers.values()]):
    logger.add(os.path.join(log_dir, "daemon.log"), rotation="5 MB", retention=5, encoding="utf-8", filter=lambda record: record["extra"].get("name", "") in ("civitai.download", "civitai.api"))
    logger.add(os.path.join(log_dir, "update.log"), rotation="2 MB", retention=5, encoding="utf-8", filter=lambda record: record["extra"].get("name", "") == "civitai.updater")
# Always proxy logs to proxy.txt and console, regardless of previous loguru config
logger.add(os.path.join(log_dir, "proxy.txt"), rotation="2 MB", retention=5, encoding="utf-8", filter=lambda record: '[PROXY]' in str(record["message"]))
logger.add(lambda msg: print(msg, end=''), filter=lambda record: '[PROXY]' in str(record["message"]))

# Bind logger for API logging
log = logger.bind(name="civitai.api")


# Initialization (after imports, before any function/endpoint definitions)
log = logger.bind(name="civitai.api")
daemon_instance = DownloadDaemon()
if not hasattr(daemon_instance, 'is_alive') or not daemon_instance.is_alive():
    log.info('Daemon started')
    daemon_instance.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_manager.set_loop(asyncio.get_event_loop())
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # of ["*"] voor alle origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

SECRET_KEY = load_secret_key()
if not sdsage.ENABLED:
    print('Backend loaded SECRET_KEY:', SECRET_KEY)
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# OPTIONS handlers for CORS preflight on /api/download and /api/batch
from fastapi import Response
@app.options("/api/download")
async def options_download():
    return Response(status_code=204)

@app.options("/api/batch")
async def options_batch():
    return Response(status_code=204)

# Log every request via middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        # log.info(f"Request: {request.method} {request.url.path}")
        response = await call_next(request)
        # log.info(f"Response: {request.method} {request.url.path} {response.status_code}")
        return response
app.add_middleware(LogRequestsMiddleware)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ws_manager.set_loop(asyncio.get_event_loop())
    yield


# --- Auth dependency must be defined before any endpoint uses it ---
def get_current_user(request: Request, token: str = Depends(oauth2_scheme), require_admin: bool = False):
    # As an SD.Sage plugin, only the gateway may call us: it sends its token and the user.
    if sdsage.ENABLED:
        if not sdsage.check_token(token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid plugin token")
        role = request.headers.get("x-sdsage-role", "user")
        if require_admin and role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
        return {"user": request.headers.get("x-sdsage-user", "sdsage"), "role": role}
    # Allow testtoken if test auth is enabled
    if os.environ.get("CIVITAI_TEST_AUTH") == "1" and token == "testtoken":
        return {"user": "test", "role": "admin"}
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = payload.get("sub")
        role = payload.get("role", "user")
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
        if require_admin and role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
        return {"user": user, "role": role}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

# Add root redirect to /gui
@app.get("/")
def root():
    return RedirectResponse(url="/gui")

# --- Proxy endpoint for CivitAI models API (including cursor support) ---
@app.get("/api/models")
async def proxy_models(request: Request):
    """Proxy for CivitAI models API with cursor, params, and timeout handling."""
    base_url = "https://civitai.com/api/v1/models"
    params = dict(request.query_params)
    headers = {"User-Agent": "CivitaiDaemonProxy/1.0"}
    timeout = httpx.Timeout(30.0)  # 20 seconds timeout
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(base_url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[PROXY] {request.url.path}?{request.url.query} -> {base_url} [{resp.status_code}]")
            return JSONResponse(content=data, status_code=resp.status_code)
    except httpx.ReadTimeout:
        logger.error(f"[PROXY] Timeout at proxy {base_url} [{params}]")
        return JSONResponse(content={"error": "Upstream timeout"}, status_code=504)
    except httpx.HTTPStatusError as e:
        logger.error(f"[PROXY] Upstream error {e.response.status_code} at {base_url}: {e.response.text}")
        return JSONResponse(content={"error": f"Upstream error: {e.response.status_code}"}, status_code=502)
    except Exception as e:
        logger.error(f"[PROXY] Unexpected proxy error: {e}")
        return JSONResponse(content={"error": "Proxy error", "detail": str(e)}, status_code=500)



# Only the first item in the queue is considered the active download
@app.get("/api/active_downloads")
def api_active_downloads(user: str = Depends(get_current_user)):
    try:
        queue_items = list(daemon_instance.queue.queue)
        if queue_items:
            # Return only the first item as the active download
            item = queue_items[0]
            # If item is a tuple (priority, ts, dict), extract dict
            if isinstance(item, tuple) and len(item) == 3 and isinstance(item[2], dict):
                item = item[2]
            if hasattr(item, 'asdict'):
                return {"active_downloads": [item.asdict()]}
            elif hasattr(item, '__dict__'):
                return {"active_downloads": [dict(item.__dict__)]}
            elif isinstance(item, dict):
                return {"active_downloads": [item]}
            else:
                return {"active_downloads": []}
        else:
            return {"active_downloads": []}
    except Exception as e:
        log.error(f"Error in active_downloads endpoint: {e}")
        log_error('system', '-', f"Error in active_downloads endpoint: {e}")
        return {"active_downloads": [], "error": str(e)}


# New endpoint: only model_id and model_version_id for all downloaded models
@app.get("/api/downloaded_ids")
def api_downloaded_ids(user: str = Depends(get_current_user)):
    # all_downloaded is a list of dicts or objects; extract only model_id and model_version_id
    result = []
    for item in daemon_instance.all_downloaded:
        # Support both dict and object
        if isinstance(item, dict):
            mid = item.get("model_id")
            mvid = item.get("model_version_id")
        else:
            mid = getattr(item, "model_id", None)
            mvid = getattr(item, "model_version_id", None)
        if mid and mvid:
            result.append({"model_id": mid, "model_version_id": mvid})
    return {"downloaded": result}


# New endpoint: return full details of last downloaded models
@app.get("/api/last_downloaded")
def api_last_downloaded(user: str = Depends(get_current_user)):
    # Return all fields for each downloaded model
    result = []
    for item in daemon_instance.last_downloaded:
        if hasattr(item, 'asdict'):
            result.append(item.asdict())
        elif isinstance(item, dict):
            result.append(item)
        elif hasattr(item, '__dict__'):
            result.append(dict(item.__dict__))
        else:
            result.append(str(item))
    return {"last_downloaded": result}


@app.get("/gui", response_class=HTMLResponse)
def gui(request: Request):
    return templates.TemplateResponse(request, "gui.html", {"request": request})


@app.post("/api/pause")
def api_pause(user=Depends(get_current_user)):
    if user["role"] != "admin":
        log_error('system', '-', f"Unauthorized pause attempt by {user['user']}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    daemon_instance.paused = True
    log.info(f"Daemon paused by {user['user']}")
    log_download('system', None, '-', 'paused', message=f"Paused by {user['user']}")
    return {"status": "paused"}


@app.post("/api/resume")
def api_resume(user=Depends(get_current_user)):
    if user["role"] != "admin":
        log_error('system', '-', f"Unauthorized resume attempt by {user['user']}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    daemon_instance.paused = False
    log.info(f"Daemon resumed by {user['user']}")
    log_download('system', None, '-', 'resumed', message=f"Resumed by {user['user']}")
    return {"status": "resumed"}


@app.post("/api/stop")
def api_stop(user=Depends(get_current_user)):
    if user["role"] != "admin":
        log_error('system', '-', f"Unauthorized stop attempt by {user['user']}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    daemon_instance.running = False
    log.info(f"Daemon stopped by {user['user']}")
    log_download('system', None, '-', 'stopped', message=f"Stopped by {user['user']}")
    return {"status": "stopped"}


@app.get("/health")
def health():
    return {"status": "ok", "plugin": sdsage.ENABLED}


def _public(item: dict) -> dict:
    """A queue item without internal fields (hooks, raw CivitAI data)."""
    keys = ("model_id", "model_version_id", "filename", "model_type", "base_model", "name", "downloaded", "total", "path")
    return {k: item.get(k) for k in keys if k in item}


@app.get("/api/sdsage/downloads")
def sdsage_downloads(user: dict = Depends(get_current_user)):
    """Active, queued and recent downloads in one call, for SD.Sage's UI."""
    queued = []
    for entry in list(daemon_instance.queue.queue):
        item = entry[2] if isinstance(entry, tuple) and len(entry) == 3 else entry
        if isinstance(item, dict):
            queued.append(_public(item))
    return {
        "active": [_public(i) for i in list(daemon_instance.active_downloads)],
        "queued": queued,
        "recent": list(daemon_instance.last_downloaded)[:10],
        "paused": daemon_instance.paused,
    }


@app.get("/api/sdsage/downloads/history")
def sdsage_downloads_history(limit: int = 100, user: dict = Depends(get_current_user)):
    """What was downloaded (or failed) lately, kept across restarts: for 'what have I done'."""
    from backend.database import recent_downloads
    return {"items": recent_downloads(max(1, min(limit, 500)))}


def civitai_api_key():
    """CIVITAI_API_KEY from the environment, else civitai_api_key from configs/config.json."""
    if os.environ.get('CIVITAI_API_KEY'):
        return os.environ['CIVITAI_API_KEY']
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('civitai_api_key')
    return None


if sdsage.ENABLED:
    from backend import sdsage_updates
    sdsage_updates.start_schedule(civitai_api_key)


@app.get("/api/sdsage/updates")
def sdsage_updates_list(user: dict = Depends(get_current_user)):
    """Newer versions on CivitAI for models in the folder (last check)."""
    from backend import sdsage_updates
    return sdsage_updates.load()


@app.post("/api/sdsage/updates/check")
def sdsage_updates_check(user: dict = Depends(get_current_user)):
    """Start an update check now. Admins only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    from backend import sdsage_updates
    sdsage_updates.check_in_background(civitai_api_key())
    return {"status": "started"}


@app.post("/api/sdsage/updates/ignore")
async def sdsage_updates_ignore(request: Request, user: dict = Depends(get_current_user)):
    """Stop (or resume) reporting updates for a model. Admins only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    data = await request.json()
    try:
        model_id = int(data.get("model_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="model_id is required")
    from backend import sdsage_updates
    sdsage_updates.set_ignored(model_id, bool(data.get("ignore", True)))
    return {"status": "ok"}


def _admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")


@app.get("/api/sdsage/metadata")
def sdsage_metadata_status(user: dict = Depends(get_current_user)):
    """How the lookup of missing CivitAI info is going."""
    from backend import sdsage_metadata
    return sdsage_metadata.status()


@app.post("/api/sdsage/metadata/fetch")
def sdsage_metadata_fetch(user: dict = Depends(get_current_user)):
    """Find CivitAI info, by hash, for models that have none. Admins only."""
    _admin(user)
    from backend import sdsage_metadata
    return {"status": "started" if sdsage_metadata.start(civitai_api_key()) else "running"}


@app.get("/api/sdsage/duplicates")
def sdsage_duplicates_status(user: dict = Depends(get_current_user)):
    """The last search for the same model in several places."""
    from backend import sdsage_duplicates
    return sdsage_duplicates.status()


@app.post("/api/sdsage/duplicates/scan")
def sdsage_duplicates_scan(user: dict = Depends(get_current_user)):
    """Look for duplicates (files of equal size are hashed). Admins only; nothing is deleted."""
    _admin(user)
    from backend import sdsage_duplicates
    return {"status": "started" if sdsage_duplicates.start() else "running"}


def _models_root():
    from pathlib import Path as _Path
    if not sdsage.MODELS_DIR:
        raise HTTPException(status_code=400, detail="SDSAGE_MODELS_DIR is not set")
    return _Path(sdsage.MODELS_DIR)


@app.get("/api/sdsage/trash")
def sdsage_trash_list(user: dict = Depends(get_current_user)):
    """Models in the trash (_oud). Admins only."""
    _admin(user)
    from backend import sdsage_trash
    return sdsage_trash.listing(_models_root())


@app.post("/api/sdsage/trash/{action}")
async def sdsage_trash_action(action: str, request: Request, user: dict = Depends(get_current_user)):
    """move (models to the trash), restore (back) or purge (delete for good,
    only with confirm: true). Body: {"files": [relative paths]}. Admins only."""
    _admin(user)
    from backend import sdsage_trash
    body = await request.json()
    files = [f for f in body.get("files") or [] if isinstance(f, str)][:2000]
    root = _models_root()
    if action == "move":
        return await asyncio.to_thread(sdsage_trash.move_out, root, files)
    if action == "restore":
        return await asyncio.to_thread(sdsage_trash.restore, root, files)
    if action == "purge":
        if body.get("confirm") is not True:
            raise HTTPException(status_code=400, detail="confirm is required to delete for good")
        return await asyncio.to_thread(sdsage_trash.purge, root, files)
    raise HTTPException(status_code=404, detail="unknown action")


@app.get("/api/sdsage/organize/plan")
def sdsage_organize_plan(user: dict = Depends(get_current_user)):
    """Which models would move to <type>/<base>/; nothing is touched. Admins only."""
    _admin(user)
    from pathlib import Path as _Path
    from backend import sdsage_organize
    if not sdsage.MODELS_DIR:
        raise HTTPException(status_code=400, detail="SDSAGE_MODELS_DIR is not set")
    return sdsage_organize.plan(_Path(sdsage.MODELS_DIR))


@app.post("/api/sdsage/organize/apply")
async def sdsage_organize_apply(request: Request, user: dict = Depends(get_current_user)):
    """Carry out the plan (worked out again now), or only the moves named in
    {"from": [...]}. Every move is logged for undo. Admins only."""
    _admin(user)
    from pathlib import Path as _Path
    from backend import sdsage_organize
    if not sdsage.MODELS_DIR:
        raise HTTPException(status_code=400, detail="SDSAGE_MODELS_DIR is not set")
    body = await request.json() if (await request.body()) else {}
    root = _Path(sdsage.MODELS_DIR)
    moves = sdsage_organize.plan(root)["moves"]
    if isinstance(body.get("from"), list):
        wanted = set(body["from"])
        moves = [m for m in moves if m["from"] in wanted]
    return await asyncio.to_thread(sdsage_organize.apply, root, moves)


@app.post("/api/sdsage/organize/undo")
def sdsage_organize_undo(user: dict = Depends(get_current_user)):
    """Move back what earlier runs moved. Admins only."""
    _admin(user)
    from backend import sdsage_organize
    return sdsage_organize.undo()


_local_versions: dict = {"at": 0.0, "ids": set(), "models": set()}


def _downloaded_versions() -> tuple[set, set]:
    """Version and model ids of the models in the folder, from their .civitai.info
    (cached a few minutes), and of what the daemon downloaded."""
    import time as _time
    from pathlib import Path as _Path
    from backend import sdsage_updates
    if sdsage.MODELS_DIR and _time.time() - _local_versions["at"] > 300:
        local = sdsage_updates.local_models(_Path(sdsage.MODELS_DIR))
        _local_versions["ids"] = {m["version_id"] for m in local}
        _local_versions["models"] = {m["model_id"] for m in local}
        _local_versions["at"] = _time.time()
    done = [i for i in daemon_instance.all_downloaded if isinstance(i, dict)]
    return (
        _local_versions["ids"] | {i.get("model_version_id") for i in done},
        _local_versions["models"] | {i.get("model_id") for i in done},
    )


@app.post("/api/sdsage/search")
async def sdsage_search(request: Request, user: dict = Depends(get_current_user)):
    """Search CivitAI: query, type, base model, sort, period, adult, cursor."""
    from backend import sdsage_search
    params = await request.json()
    try:
        versions, models = _downloaded_versions()
        return await asyncio.to_thread(sdsage_search.search, params, civitai_api_key(), versions, models)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"CivitAI did not answer: {e}")


@app.get("/api/sdsage/model")
async def sdsage_model(id: int, adult: bool = False, user: dict = Depends(get_current_user)):
    """One CivitAI model with its versions and images, for the model window."""
    from backend import sdsage_search
    try:
        versions, _ = _downloaded_versions()
        return await asyncio.to_thread(sdsage_search.model, id, civitai_api_key(), adult, versions)
    except PermissionError:
        raise HTTPException(status_code=403, detail="adult model")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"CivitAI did not answer: {e}")


@app.get("/api/sdsage/thumb")
async def sdsage_thumb(url: str, user: dict = Depends(get_current_user)):
    """A CivitAI preview image, fetched by the daemon for the page."""
    from backend import sdsage_search
    try:
        body, kind = await asyncio.to_thread(sdsage_search.thumbnail, url, civitai_api_key())
    except (ValueError, httpx.HTTPError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(content=body, media_type=kind, headers={"Cache-Control": "private, max-age=86400"})


@app.post("/api/sdsage/downloads/cancel")
async def sdsage_cancel(request: Request, user: dict = Depends(get_current_user)):
    """Cancel one download: the running one stops, a queued one leaves the queue. Admins only."""
    _admin(user)
    data = await request.json()
    filename = str(data.get("filename") or "")
    if not filename:
        raise HTTPException(status_code=422, detail="filename is required")
    if any(i.get("filename") == filename for i in list(daemon_instance.active_downloads)):
        daemon_instance.cancel()
        return {"status": "cancelling"}
    import heapq
    q = daemon_instance.queue
    with q.mutex:
        before = len(q.queue)
        q.queue[:] = [e for e in q.queue if not (isinstance(e, tuple) and len(e) == 3 and isinstance(e[2], dict) and e[2].get("filename") == filename)]
        heapq.heapify(q.queue)
        removed = before - len(q.queue)
        q.unfinished_tasks = max(0, q.unfinished_tasks - removed)
    return {"status": "removed" if removed else "not found"}


@app.post("/api/sdsage/downloads/pause")
async def sdsage_pause(request: Request, user: dict = Depends(get_current_user)):
    """Pause or resume all downloads. Admins only."""
    _admin(user)
    data = await request.json()
    daemon_instance.paused = bool(data.get("paused", True))
    return {"paused": daemon_instance.paused}


# ---- Hugging Face ----

import re as _re

_REPO = _re.compile(r"^[A-Za-z0-9][\w.-]{0,95}/[\w.-]{1,96}$")


def _repo(data: dict) -> str:
    repo = str(data.get("repo") or "").strip()
    if not _REPO.match(repo) or ".." in repo:
        raise HTTPException(status_code=422, detail="repo is <owner>/<name>")
    return repo


@app.post("/api/sdsage/hf/search")
async def hf_search(request: Request, user: dict = Depends(get_current_user)):
    """Search Hugging Face: query, task (text-to-image, image-to-video, ...), sort."""
    from backend import sdsage_hf
    try:
        return await asyncio.to_thread(sdsage_hf.search, await request.json())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Hugging Face did not answer: {e}")


@app.post("/api/sdsage/hf/plan")
async def hf_plan(request: Request, user: dict = Depends(get_current_user)):
    """What downloading a repo would fetch, and whether access is granted."""
    from backend import sdsage_hf
    repo = _repo(await request.json())
    try:
        return await asyncio.to_thread(sdsage_hf.plan, repo)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/sdsage/hf/download")
async def hf_download(request: Request, user: dict = Depends(get_current_user)):
    """Download a repo (or complete one) into the cache SD.Sage scans. Admins only."""
    _admin(user)
    from backend import sdsage_hf
    data = await request.json()
    repo = _repo(data)
    files = data.get("files") if isinstance(data.get("files"), list) else None
    try:
        return await asyncio.to_thread(sdsage_hf.enqueue, repo, files)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/sdsage/hf/downloads")
def hf_downloads(user: dict = Depends(get_current_user)):
    from backend import sdsage_hf
    return sdsage_hf.status()


@app.post("/api/sdsage/hf/cancel")
async def hf_cancel(request: Request, user: dict = Depends(get_current_user)):
    _admin(user)
    from backend import sdsage_hf
    return {"status": sdsage_hf.cancel(_repo(await request.json()))}


@app.get("/api/sdsage/hf/local")
async def hf_local(user: dict = Depends(get_current_user)):
    """The repos in the cache: complete, partial or configs only, with sizes."""
    from backend import sdsage_hf
    try:
        return {"repos": await asyncio.to_thread(sdsage_hf.local_repos)}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/api/sdsage/hf/delete")
async def hf_delete(request: Request, user: dict = Depends(get_current_user)):
    """Remove a repo from the cache, on the admin's word. Admins only."""
    _admin(user)
    from backend import sdsage_hf
    try:
        return {"freed": await asyncio.to_thread(sdsage_hf.delete_repo, _repo(await request.json()))}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/sdsage/hf/updates")
def hf_updates(user: dict = Depends(get_current_user)):
    from backend import sdsage_hf
    return sdsage_hf.updates()


@app.post("/api/sdsage/hf/updates/check")
def hf_updates_check(user: dict = Depends(get_current_user)):
    _admin(user)
    from backend import sdsage_hf
    threading.Thread(target=sdsage_hf.check_updates, daemon=True).start()
    return {"status": "started"}


@app.post("/api/download_civitai")
async def download_civitai(request: Request, user: dict = Depends(get_current_user)):
    """Queue a download from a CivitAI link, AIR or model id. Admins only."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    data = await request.json()
    ref = str(data.get("ref", "")).strip()
    if not ref:
        raise HTTPException(status_code=422, detail="ref is required")
    try:
        found = await asyncio.to_thread(sdsage.resolve_civitai, ref, civitai_api_key())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"CivitAI answered {e.response.status_code}")
    from backend.database import is_already_downloaded
    if is_already_downloaded(found['model_id'], found['model_version_id']):
        return {"status": "already downloaded", "name": found['name']}
    item = make_queue_item(
        model_id=found['model_id'],
        url=found['url'],
        filename=found['filename'],
        sha256=found['sha256'],
        priority=1,
        model_type=found['model_type'],
        model_version_id=found['model_version_id'],
        base_model=found['base_model'],
    )
    item['name'] = found['name']
    item['civitai_info'] = found['civitai_info']
    daemon_instance.add_job(item)
    log.info(f"{user['user']} queued {found['name']} ({found['filename']})")
    return {"status": "queued", "item": _public(item)}


@app.post("/token")
async def login(request: Request):
    # Accepts username and optional role (default: user), returns JWT.
    # Off as an SD.Sage plugin: there the gateway handles logins.
    if sdsage.ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    data = await request.json()
    username = data.get("username", "user")
    role = data.get("role", "user")
    token = jwt.encode({"sub": username, "role": role}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/protected")
def protected_route(user=Depends(get_current_user)):
    return {"message": f"Hello, {user['user']} (role: {user['role']}). This is a protected endpoint."}


# Example admin-only endpoint
@app.get("/api/admin-only")
def admin_only_route(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return {"message": f"Hello admin {user['user']}! This is an admin-only endpoint."}


# WebSocket with JWT or testtoken auth
@app.websocket("/ws/downloads")
async def websocket_endpoint(websocket: WebSocket):
    # Accept testtoken via Authorization header if test mode is enabled
    auth = websocket.headers.get("authorization")
    if os.environ.get("CIVITAI_TEST_AUTH") == "1" and auth == "Bearer testtoken":
        print("[WebSocket] Using testtoken branch (header)")
        await websocket.accept()
        ws_manager.add(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                print(f"[WebSocket] Received (testtoken): {data}")
                await websocket.send_text(f"Echo: {data}")
        except WebSocketDisconnect:
            pass
        finally:
            ws_manager.remove(websocket)
        return

    # Fallback: JWT via query param (production)
    token = websocket.query_params.get("token")
    if not token or not isinstance(token, str) or token.strip() == "" or token == "null":
        await websocket.close(code=4401)
        print("[WebSocket] Connection rejected: missing or invalid JWT token")
        return
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = payload.get("sub")
        if not user:
            await websocket.close(code=1008)
            return
    except Exception as e:
        await websocket.close(code=4401)
        print(f"[WebSocket] Connection rejected: JWT decode error: {e}")
        return
    print("[WebSocket] Using JWT branch (query param)")
    await websocket.accept()
    ws_manager.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"[WebSocket] Received (JWT): {data}")
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.remove(websocket)


@app.post("/api/download")
async def api_download(request: Request, user: str = Depends(get_current_user)):
    try:
        data = await request.json()
        required_fields = ["model_id", "url", "filename", "model_type", "model_version_id"]
        if not all(f in data and data[f] for f in required_fields):
            log_error('api', '-', f"Missing required fields in /api/download by {user['user']}")
            raise HTTPException(status_code=422, detail="Missing required fields: model_id, url, filename, model_type, model_version_id")
        from backend.database import is_already_downloaded
        if is_already_downloaded(data.get('model_id'), data.get('model_version_id')):
            item = make_queue_item(
                model_id=data.get('model_id'),
                url=data.get('url'),
                filename=data.get('filename'),
                sha256=data.get('sha256'),
                priority=data.get('priority', 0),
                model_type=data.get('model_type'),
                model_version_id=data.get('model_version_id'),
                base_model=data.get('baseModel')
            )
            daemon_instance.add_job(item, skipped=True, reason="already downloaded")
            return {"status": "already downloaded"}
        item = make_queue_item(
            model_id=data.get('model_id'),
            url=data.get('url'),
            filename=data.get('filename'),
            sha256=data.get('sha256'),
            priority=data.get('priority', 0),
            model_type=data.get('model_type'),
            model_version_id=data.get('model_version_id'),
            base_model=data.get('baseModel')
        )
        # After download: if hash check fails, remove the file
        def after_download_hook(item, file_path, hash_ok):
            if not hash_ok and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    log_error('download', item['model_id'], item['filename'], f"Hash check failed, file removed: {file_path}")
                except Exception as e:
                    log_error('download', item['model_id'], item['filename'], f"Hash check failed, could not remove file: {file_path}, error: {e}")
        item['after_download_hook'] = after_download_hook
        daemon_instance.add_job(item)
        return {"status": "queued", "item": item}
    except Exception as e:
        log_error('api', '-', f"Exception in /api/download: {e}")
        raise


@app.post("/api/batch")
async def api_batch(request: Request, user: str = Depends(get_current_user)):
    try:
        data = await request.json()
        manifest = data.get('manifest', [])
        if not isinstance(manifest, list):
            log_error('api', '-', f"Manifest not a list in /api/batch by {user['user']}")
            raise HTTPException(status_code=422, detail="Manifest must be a list of jobs")
        from backend.database import is_already_downloaded
        count = 0
        skipped = 0
        for entry in manifest:
            if not isinstance(entry, dict):
                continue
            if not all(f in entry and entry[f] for f in ["model_id", "url", "filename", "model_type", "model_version_id"]):
                continue
            item = make_queue_item(
                model_id=entry.get('model_id'),
                url=entry.get('url'),
                filename=entry.get('filename'),
                sha256=entry.get('sha256'),
                priority=entry.get('priority', 0),
                model_type=entry.get('model_type'),
                model_version_id=entry.get('model_version_id')
            )
            # After download: if hash check fails, remove the file
            def after_download_hook(item, file_path, hash_ok):
                if not hash_ok and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        log_error('download', item.model_id, item.filename, f"Hash check failed, file removed: {file_path}")
                    except Exception as e:
                        log_error('download', item.model_id, item.filename, f"Hash check failed, could not remove file: {file_path}, error: {e}")
            item['after_download_hook'] = after_download_hook
            if is_already_downloaded(entry.get('model_id'), entry.get('model_version_id')):
                skipped += 1
                daemon_instance.add_job(item, skipped=True, reason="already downloaded")
                continue
            daemon_instance.add_job(item)
            count += 1
        return {"status": "batch_queued", "queued": count, "skipped": skipped}
    except Exception as e:
        log_error('api', '-', f"Exception in /api/batch: {e}")
        raise


@app.get("/api/status")
def api_status(user: str = Depends(get_current_user)):
    return {"queue_size": daemon_instance.queue.qsize(), "running": daemon_instance.running, "paused": daemon_instance.paused}


@app.get("/api/metrics")
def api_metrics(user: str = Depends(get_current_user)):
    try:
        result = get_all_metrics()
    except Exception as e:
        log.error(f"Error in get_all_metrics: {e}")
        log_error('system', '-', f"Error in get_all_metrics: {e}")
        # Return all expected keys with empty lists or None
        result = {
            "downloads_per_day": [],
            "downloads_per_day_type_status": [],
            "file_size_stats_per_type": [],
            "download_time_stats_per_type": [],
            "file_size_stats_per_type_unique": [],
            "download_time_stats_per_type_unique": [],
            "downloads_per_day_base_model_status": [],
            "file_size_stats_per_base_model": [],
            "download_time_stats_per_base_model": [],
            "total_downloads": 0,
            "unique_successful_downloads": 0,
            "unique_failed_downloads": 0,
        }
    return result


@app.get("/api/queue")
def api_queue(user: str = Depends(get_current_user)):
    try:
        # Try to get the current active job from the daemon, fallback to first in queue
        active_job = getattr(daemon_instance, 'current_job', None)
        queue_items = list(daemon_instance.queue.queue)
        queue_json = []
        # If no explicit current_job, but queue is not empty, use first item as active
        if not active_job and queue_items:
            item = queue_items[0]
            if hasattr(item, 'asdict'):
                active_job = item.asdict()
            elif hasattr(item, '__dict__'):
                active_job = dict(item.__dict__)
            else:
                active_job = str(item)
            # Remove from queue_items so it's not duplicated
            queue_items = queue_items[1:]
        elif active_job:
            # If current_job is an object, convert to dict
            if hasattr(active_job, 'asdict'):
                active_job = active_job.asdict()
            elif hasattr(active_job, '__dict__'):
                active_job = dict(active_job.__dict__)
        # Add active job first if present
        if active_job:
            queue_json.append(active_job)
        # Add the rest of the queue
        for item in queue_items:
            # If item is a tuple (priority, ts, dict), extract dict
            if isinstance(item, tuple) and len(item) == 3 and isinstance(item[2], dict):
                item = item[2]
            if hasattr(item, 'asdict'):
                queue_json.append(item.asdict())
            elif hasattr(item, '__dict__'):
                queue_json.append(dict(item.__dict__))
            elif isinstance(item, dict):
                queue_json.append(item)
            else:
                queue_json.append(str(item))
        if not queue_json:
            queue_json = ["The queue is empty."]
        return {"queue": queue_json}
    except Exception as e:
        log.error(f"Error in queue endpoint: {e}")
        log_error('system', '-', f"Error in queue endpoint: {e}")
        return {"queue": [f"Error: {str(e)}"], "error": str(e)}


# --- Test-only endpoint to allow testtoken for local/test runs ---
import sys
if os.environ.get("CIVITAI_TEST_AUTH") == "1" or ("pytest" in sys.modules):
    @app.post("/test/enable-testtoken")
    def enable_testtoken():
        app.dependency_overrides[get_current_user] = lambda: {"user": "test", "role": "admin"}
        return {"status": "testtoken enabled"}

    @app.get("/test/env")
    def get_env(key: str):
        value = os.environ.get(key)
        return {"key": key, "value": value}


@app.websocket("/ws/downloads")
async def websocket_endpoint(websocket: WebSocket):
    from backend.database import log_download, log_error
    try:
        # Accept testtoken via Authorization header if test mode is enabled
        auth = websocket.headers.get("authorization")
        if os.environ.get("CIVITAI_TEST_AUTH") == "1" and auth == "Bearer testtoken":
            log_download('system', None, '-', 'ws_connect', message='WebSocket testtoken connect')
            await websocket.accept()
            ws_manager.add(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    log_download('system', None, '-', 'ws_message', message=f"WebSocket testtoken: {data}")
                    await websocket.send_text(f"Echo: {data}")
            except WebSocketDisconnect:
                log_download('system', None, '-', 'ws_disconnect', message='WebSocket testtoken disconnect')
                pass
            finally:
                ws_manager.remove(websocket)
            return

        # Fallback: JWT via query param (production)
        token = websocket.query_params.get("token")
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user = payload.get("sub")
            if not user:
                await websocket.close(code=1008)
                return
        except JWTError:
            await websocket.close(code=1008)
            return
        log_download('system', None, '-', 'ws_connect', message=f'WebSocket JWT connect: {user}')
        await websocket.accept()
        ws_manager.add(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                log_download('system', None, '-', 'ws_message', message=f"WebSocket JWT {user}: {data}")
                await websocket.send_text(f"Echo: {data}")
        except WebSocketDisconnect:
            log_download('system', None, '-', 'ws_disconnect', message=f'WebSocket JWT disconnect: {user}')
            pass
        finally:
            ws_manager.remove(websocket)
    except Exception as e:
        log_error('system', '-', f"WebSocket error: {e}")
        raise
