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
from app.routers import complaint, followup

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="AIVOA - AI-Powered Complaint Management System",
    description="Pharmaceutical customer complaint intake, AI risk triage, and QMS ledger commit API.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "https://aivoa1.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The original complaint router provides intake, correction and commit endpoints.
# The follow-up router adds intent-aware routing so natural conversation and
# application questions don't get forced through the field-mutation workflow.
print("Loading complaint router...", flush=True)
app.include_router(complaint.router)
print("Complaint router loaded.", flush=True)
print("Loading intelligent follow-up router...", flush=True)
app.include_router(followup.router)
print("Intelligent follow-up router loaded.", flush=True)


ALLOWED_ORIGINS = {"http://localhost:3000", "http://localhost:5173", "https://aivoa1.netlify.app"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log the traceback server-side and return a CORS-safe JSON error."""
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
