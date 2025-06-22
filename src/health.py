"""
Health check endpoint for the FastAPI application
"""
import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/api/health")
async def health_check():
    """Health check endpoint for load balancer"""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "mcp-backend",
            "version": "1.0.0",
            "timestamp": int(time.time())
        },
        status_code=200,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@router.get("/health")
async def simple_health_check():
    """Simple health check endpoint"""
    return {"status": "ok"}
