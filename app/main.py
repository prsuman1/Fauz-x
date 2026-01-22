from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import APP_NAME, DEBUG
from app.api import router

# Create FastAPI app
app = FastAPI(
    title=APP_NAME,
    description="AI-powered JD-CV matching system for entry-level hiring",
    version="2.0.0",
    debug=DEBUG,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["API"])

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    """Serve the main UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "message": "FaujX JD-CV Matcher API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print(f"Starting {APP_NAME}...")
    print(f"Debug mode: {DEBUG}")
    print("API docs available at /docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print(f"Shutting down {APP_NAME}...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=DEBUG)
