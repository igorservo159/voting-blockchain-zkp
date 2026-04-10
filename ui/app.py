"""
Dashboard UI — connects to all blockchain nodes and shows live state.
Built with FastAPI + Jinja2. Browser talks directly to node APIs.
"""

import os
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)

NODE_URLS_INTERNAL = [u.strip() for u in os.environ.get("NODE_URLS", "").split(",") if u.strip()]
CANDIDATES = [c.strip() for c in os.environ.get("CANDIDATES", "Alice,Bob,Carol").split(",")]

# External URLs the browser can reach (mapped ports from docker-compose)
NODE_URLS_EXTERNAL = [f"http://localhost:{8001 + i}" for i in range(len(NODE_URLS_INTERNAL))]

app = FastAPI(title="Voting Blockchain Dashboard")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    nodes = [
        {"id": f"node{i+1}", "url": NODE_URLS_EXTERNAL[i]}
        for i in range(len(NODE_URLS_INTERNAL))
    ]
    return templates.TemplateResponse("index.html", {
        "request": request,
        "nodes": nodes,
        "candidates": CANDIDATES,
    })
