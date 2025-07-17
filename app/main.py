import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routes import telegram, health
from app.utils.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting Telegram Audio Transcription Bot")
    logger.info(f"Webhook URL: {settings.webhook_url}")
    logger.info(f"Allowed users: {len(settings.allowed_user_ids_list)}")
    logger.info(f"Transcripts file: {settings.transcripts_file}")
    
    # Validate configuration
    try:
        required_settings = {
            "telegram_token": settings.telegram_token,
            "openai_api_key": settings.openai_api_key,
            "shared_secret": settings.shared_secret,
            "webhook_url": settings.webhook_url
        }
        
        missing_settings = [key for key, value in required_settings.items() if not value]
        if missing_settings:
            logger.error(f"Missing required settings: {missing_settings}")
            raise ValueError(f"Missing required configuration: {missing_settings}")
        
        if not settings.allowed_user_ids_list:
            logger.error("No allowed user IDs configured")
            raise ValueError("No allowed user IDs configured")
        
        logger.info("Configuration validation passed")
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Telegram Audio Transcription Bot")


# Create FastAPI application
app = FastAPI(
    title="Telegram Audio Transcription Bot",
    description="A bot that transcribes voice messages and audio files using OpenAI Whisper",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(telegram.router, prefix="", tags=["telegram"])
app.include_router(health.router, prefix="", tags=["health"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled exceptions.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


@app.get("/")
async def root():
    """
    Root endpoint with basic service information.
    """
    return {
        "service": "Telegram Audio Transcription Bot",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health",
            "detailed_health": "/health/detailed",
            "readiness": "/health/ready"
        },
        "supported_formats": ["voice", "audio"],
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        reload=False,
        access_log=True
    )