from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Dict, Any
import asyncio
import logging
from app.storage.transcripts import transcript_storage
from app.utils.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Health check endpoint for monitoring service status.
    
    Returns:
        dict: Service health status and basic metrics
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "telegram-transcription-bot",
            "version": "1.0.0"
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/health/detailed", response_model=Dict[str, Any])
async def detailed_health_check():
    """
    Detailed health check with service dependencies and statistics.
    
    Returns:
        dict: Detailed health status including storage and configuration
    """
    try:
        # Basic health info
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "telegram-transcription-bot",
            "version": "1.0.0",
            "checks": {}
        }
        
        # Check storage
        try:
            storage_stats = await transcript_storage.get_storage_stats()
            health_status["checks"]["storage"] = {
                "status": "healthy",
                "stats": storage_stats
            }
        except Exception as e:
            logger.error(f"Storage check failed: {e}")
            health_status["checks"]["storage"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Check configuration
        try:
            config_check = {
                "telegram_token_configured": bool(settings.telegram_token),
                "openai_api_key_configured": bool(settings.openai_api_key),
                "shared_secret_configured": bool(settings.shared_secret),
                "allowed_users_count": len(settings.allowed_user_ids_list),
                "webhook_url": settings.webhook_url,
                "transcripts_file": settings.transcripts_file
            }
            health_status["checks"]["configuration"] = {
                "status": "healthy",
                "details": config_check
            }
        except Exception as e:
            logger.error(f"Configuration check failed: {e}")
            health_status["checks"]["configuration"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Detailed health check failed: {str(e)}"
        )


@router.get("/health/ready", response_model=Dict[str, Any])
async def readiness_check():
    """
    Readiness check for Kubernetes/container orchestration.
    
    Returns:
        dict: Readiness status indicating if service can accept requests
    """
    try:
        # Check if all required configuration is present
        required_configs = [
            settings.telegram_token,
            settings.openai_api_key,
            settings.shared_secret,
            settings.allowed_user_ids_list
        ]
        
        if not all(required_configs):
            raise HTTPException(
                status_code=503, 
                detail="Service not ready: missing required configuration"
            )
        
        # Test storage accessibility
        try:
            await transcript_storage.get_storage_stats()
        except Exception as e:
            raise HTTPException(
                status_code=503, 
                detail=f"Service not ready: storage check failed: {e}"
            )
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": "Service is ready to accept requests"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=503, 
            detail=f"Service not ready: {str(e)}"
        )