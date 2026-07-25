"""
main.py
-------
FastAPI application entrypoint for AIVOA.
"""

import sys
import logging
import traceback

from dotenv import load_dotenv
load_dotenv()  # must run before app.routers -> app.graph is imported

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import init_db
from app.routers import complaint

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="AIVOA - AI-Powered Complaint Management System",
    description="Pharmaceutical customer complaint intake, AI risk triage, and QMS ledger commit API.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FIX: router already declares prefix="/api/complaint" inside complaint.py
# (`router = APIRouter(prefix="/api/complaint", ...)`), so include it ONCE
# with no extra prefix here. Including it twice (once with an extra prefix,
# once without) is what produced the duplicate
# /api/complaint/api/complaint/... routes you saw in Swagger.
print("Loading complaint router...", flush=True)
app.include_router(complaint.router)
print("Complaint router loaded.", flush=True)


ALLOWED_ORIGINS = {"http://localhost:3000", "http://localhost:5173"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Logs the full traceback to terminal AND returns it in the response
    body, so Swagger stops showing a bare 'Internal Server Error'.

    FIX: also manually sets the CORS header here. Starlette's CORSMiddleware
    normally injects Access-Control-Allow-Origin by wrapping `send`, but that
    wrapping is unreliable for responses built by a custom Exception handler
    (a known FastAPI/Starlette gotcha) — which is exactly why the browser
    console showed "CORS header 'Access-Control-Allow-Origin' missing" only
    on the 500 responses, never on the 200s.
    """
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception on {request.method} {request.url.path}:\n{tb}")
    print(tb, file=sys.stderr, flush=True)

    response = JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}", "path": str(request.url.path)},
    )
    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.on_event("startup")
def on_startup():
    print("STARTUP: Initializing database...", file=sys.stderr, flush=True)
    init_db()
    print("STARTUP: Database initialized", file=sys.stderr, flush=True)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "AIVOA backend"}
