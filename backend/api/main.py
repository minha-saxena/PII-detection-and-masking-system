"""
Main FastAPI application
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime

from core.config import settings
from core.logger import log
from api import routes
from detectors.slm_detector import SLMDetector


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    log.info("=" * 50)
    log.info(f"Starting {settings.API_TITLE} v{settings.API_VERSION}")
    log.info("=" * 50)
    
    # Check Ollama connection
    try:
        slm = SLMDetector()
        is_healthy = await slm.check_ollama_health()
        if is_healthy:
            log.info("✓ Ollama connection successful")
        else:
            log.warning("⚠ Ollama connection failed - SLM detection will be disabled")
    except Exception as e:
        log.error(f"✗ Failed to check Ollama: {str(e)}")
    
    log.info(f"API ready at http://localhost:8000")
    log.info(f"Docs available at http://localhost:8000/docs")
    
    yield
    
    # Shutdown
    log.info("Shutting down application")


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(routes.router, prefix="/api")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs",
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle unexpected exceptions"""
    log.error(f"Unexpected error: {str(exc)}", exc_info=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.LOG_LEVEL == "DEBUG" else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
         f"{__name__}:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )