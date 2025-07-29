# search.py — FastAPI router voor search GUI/API (voorbeeld)
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import httpx
import os
import json

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../configs/config.json'))
with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

@router.get("/gui/search", response_class=HTMLResponse)
def search_gui(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})

@router.get("/api/search")
async def api_search(
    tags: str = None,
    types: str = None,
    period: str = None,
    sort: str = None,
    limit: int = 12,
    nsfw: bool = False,
    cursor: str = None
):
    civitai_url = CONFIG.get("civitai_url", "https://civitai.com/api/v1")
    api_key = CONFIG.get("civitai_api_key")
    params = {"limit": limit}
    if tags: params["tags"] = tags
    if types: params["types"] = types
    if period: params["period"] = period
    if sort: params["sort"] = sort
    if nsfw: params["nsfw"] = "true"
    if cursor: params["cursor"] = cursor
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{civitai_url}/models", params=params, headers=headers)
        return JSONResponse(r.json())
