import os
import json
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from daemon import make_queue_item, DownloadDaemon
from logger import get_download_logger
from database import downloads_per_day
from database import get_all_metrics


# Initialization (after imports, before any function/endpoint definitions)
log = get_download_logger()
daemon_instance = DownloadDaemon()
if not hasattr(daemon_instance, 'is_alive') or not daemon_instance.is_alive():
    log.info('Daemon started')
    daemon_instance.start()


def load_secret_key():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            key = config.get('jwt_secret')
            if key:
                return key
    return "CHANGE_THIS_SECRET"


SECRET_KEY = load_secret_key()
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# App setup
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Auth dependency must be defined before any endpoint uses it ---
def get_current_user(token: str = Depends(oauth2_scheme), require_admin: bool = False):
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


# REST API endpoints
@app.get("/gui", response_class=HTMLResponse)
def gui(request: Request):
    return templates.TemplateResponse(request, "gui.html", {"request": request})


# Admin endpoints (pause, resume, stop)
@app.post("/api/pause")
def api_pause(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    daemon_instance.paused = True
    log.info(f"Daemon paused by {user['user']}")
    return {"status": "paused"}

@app.post("/api/resume")
def api_resume(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    daemon_instance.paused = False
    log.info(f"Daemon resumed by {user['user']}")
    return {"status": "resumed"}


@app.post("/api/stop")
def api_stop(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    daemon_instance.running = False
    log.info(f"Daemon stopped by {user['user']}")
    return {"status": "stopped"}


@app.post("/token")
async def login(request: Request):
    # Accepts username and optional role (default: user), returns JWT
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


# WebSocket with JWT auth
@app.websocket("/ws/downloads")
async def websocket_endpoint(websocket: WebSocket):
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
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        pass

@app.post("/api/download")
async def api_download(request: Request, user: str = Depends(get_current_user)):
    data = await request.json()
    # Validate required fields
    required_fields = ["model_id", "url", "filename", "model_type", "model_version_id"]
    if not all(f in data and data[f] for f in required_fields):
        raise HTTPException(status_code=422, detail="Missing required fields: model_id, url, filename, model_type, model_version_id")
    from database import is_already_downloaded
    if is_already_downloaded(data.get('model_id'), data.get('model_version_id')):
        return {"status": "already downloaded"}
    item = make_queue_item(
        model_id=data.get('model_id'),
        url=data.get('url'),
        filename=data.get('filename'),
        sha256=data.get('sha256'),
        priority=data.get('priority', 0),
        model_type=data.get('model_type'),
        model_version_id=data.get('model_version_id')
    )
    daemon_instance.add_job(item)
    return {"status": "queued", "item": item}


@app.post("/api/batch")
async def api_batch(request: Request, user: str = Depends(get_current_user)):
    data = await request.json()
    manifest = data.get('manifest', [])
    if not isinstance(manifest, list):
        raise HTTPException(status_code=422, detail="Manifest must be a list of jobs")
    from database import is_already_downloaded
    count = 0
    skipped = 0
    for entry in manifest:
        if not isinstance(entry, dict):
            continue
        if not all(f in entry and entry[f] for f in ["model_id", "url", "filename", "model_type", "model_version_id"]):
            continue
        if is_already_downloaded(entry.get('model_id'), entry.get('model_version_id')):
            skipped += 1
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
        daemon_instance.add_job(item)
        count += 1
    return {"status": "batch_queued", "queued": count, "skipped": skipped}


@app.get("/api/status")
def api_status(user: str = Depends(get_current_user)):
    return {"queue_size": daemon_instance.queue.qsize(), "running": daemon_instance.running, "paused": daemon_instance.paused}


@app.get("/api/metrics")
def api_metrics(user: str = Depends(get_current_user)):
    try:
        result = get_all_metrics()
    except Exception as e:
        result = {}
        log.error(f"Error in get_all_metrics: {e}")
    return result


@app.get("/api/queue")
def api_queue(user: str = Depends(get_current_user)):
    # Geeft de huidige queue als lijst terug
    try:
        queue_items = list(daemon_instance.queue.queue)
        # Converteer naar dicts als mogelijk
        queue_json = []
        for item in queue_items:
            if hasattr(item, 'asdict'):
                queue_json.append(item.asdict())
            elif hasattr(item, '__dict__'):
                queue_json.append(dict(item.__dict__))
            else:
                queue_json.append(str(item))
        if not queue_json:
            queue_json = ["De wachtrij is leeg."]
        return {"queue": queue_json}
    except Exception as e:
        return {"queue": [f"Fout: {str(e)}"], "error": str(e)}
