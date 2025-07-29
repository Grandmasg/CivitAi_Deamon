import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from frontend import search
import httpx
from fastapi import Query
from fastapi.responses import Response
import random
import time
from fastapi.responses import JSONResponse

# Config laden (zelfde manier als backend)
def load_config():
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

CONFIG = load_config()

app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def gui(request: Request):
    # Add a random cache-busting value for static JS
    cache_bust = f"{int(time.time())}_{random.randint(1000,9999)}"
    return templates.TemplateResponse("search.html", {"request": request, "cache_bust": cache_bust})

# Serve config as JSON for frontend
# Serve config as JSON for frontend
@app.get("/configs/config.json")
def get_config():
    return JSONResponse(CONFIG)

# Add root redirect to /search
@app.get("/")
def root():
    return RedirectResponse(url="/search")

# Proxy endpoint for CivitAI API to avoid CORS
from fastapi import Query
from typing import Optional
from fastapi import Request

@app.get("/api/models")
async def proxy_models(request: Request,
    tags: Optional[str] = Query(None),
    types: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    nsfw: Optional[bool] = Query(None),
    limit: Optional[int] = Query(12),
    sort: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None)
):
    base_url = CONFIG.get("civitai_url", "https://civitai.com/api/v1")
    api_key = CONFIG.get("civitai_api_key")
    # Neem alle queryparams dynamisch over, inclusief onbekende (zoals cursor, page, etc)
    params = dict(request.query_params)
    # Optioneel: filter lege waarden eruit
    params = {k: v for k, v in params.items() if v not in (None, "", "null")}
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = f"{base_url}/models"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers)
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type", "application/json"))


# /search endpoint (voor frontend URL)
@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})

# Include search router
app.include_router(search.router)
