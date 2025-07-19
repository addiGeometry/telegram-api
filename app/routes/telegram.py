from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional, Dict, Any
import json
import logging
import aiohttp
from datetime import datetime
from app.services.auth import auth_service, AuthenticationError
from app.services.transcription import transcription_service, TranscriptionError
from app.storage.transcripts import transcript_storage
from app.utils.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class TelegramWebhookHandler:
    """Handler for processing Telegram webhook requests."""

    def __init__(self):
        self.telegram_token = settings.telegram_token

    async def send_message(self, chat_id: int, text: str, reply_to_message_id: Optional[int] = None) -> bool:
        """
        Send a message back to the Telegram chat.

        Args:
            chat_id: The chat ID to send the message to
            text: The message text
            reply_to_message_id: Optional message ID to reply to

        Returns:
            bool: True if message was sent successfully
        """
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }

            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Message sent successfully to chat {chat_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send message: {response.status} - {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def process_voice_message(self, message: Dict[str, Any]) -> Optional[str]:
        """
        Process a voice message and return transcription.

        Args:
            message: The Telegram message object

        Returns:
            str: The transcription text or None if processing fails
        """
        try:
            voice = message.get("voice")
            if not voice:
                return None

            file_id = voice.get("file_id")
            if not file_id:
                logger.error("No file_id in voice message")
                return None

            # Process the audio file
            transcription = await transcription_service.process_audio_message(file_id)

            # Save to storage
            await transcript_storage.save_transcription(
                user_id=message["from"]["id"],
                message_id=message["message_id"],
                file_id=file_id,
                transcription=transcription,
                file_type="voice"
            )

            return transcription

        except TranscriptionError as e:
            logger.error(f"Transcription error: {e}")
            return f"⚠️ Transcription failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error processing voice message: {e}")
            return f"❌ Error processing voice message: {str(e)}"

    async def process_audio_message(self, message: Dict[str, Any]) -> Optional[str]:
        """
        Process an audio message and return transcription.

        Args:
            message: The Telegram message object

        Returns:
            str: The transcription text or None if processing fails
        """
        try:
            audio = message.get("audio")
            if not audio:
                return None

            file_id = audio.get("file_id")
            filename = audio.get("file_name", "audio.mp3")

            if not file_id:
                logger.error("No file_id in audio message")
                return None

            # Process the audio file
            transcription = await transcription_service.process_audio_message(file_id, filename)

            # Save to storage
            await transcript_storage.save_transcription(
                user_id=message["from"]["id"],
                message_id=message["message_id"],
                file_id=file_id,
                transcription=transcription,
                file_type="audio",
                filename=filename
            )

            return transcription

        except TranscriptionError as e:
            logger.error(f"Transcription error: {e}")
            return f"⚠️ Transcription failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error processing audio message: {e}")
            return f"❌ Error processing audio message: {str(e)}"


webhook_handler = TelegramWebhookHandler()


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    """
    Handle incoming Telegram webhook requests.

    Args:
        request: FastAPI request object
        x_telegram_bot_api_secret_token: Telegram webhook secret token header

    Returns:
        dict: Response status
    """
    try:
        # Get raw request body for signature verification
        body = await request.body()
        raw_data = body.decode('utf-8')

        # Parse JSON data
        try:
            update = json.loads(raw_data)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in webhook request: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        # Extract message
        message = update.get("message")
        if not message:
            logger.info("No message in update, ignoring")
            return {"status": "ok", "message": "No message to process"}

        # Check if message has required fields
        if not message.get("from") or not message.get("from", {}).get("id"):
            logger.warning("Message missing user information")
            return {"status": "ok", "message": "Invalid message format"}

        user_id = message["from"]["id"]
        chat_id = message["chat"]["id"]
        message_id = message["message_id"]

        # Authenticate request
        try:
            auth_service.authenticate_request(
                x_telegram_bot_api_secret_token,
                raw_data,
                user_id
            )
        except AuthenticationError as e:
            logger.warning(f"Authentication failed: {e}")
            # Don't send error message to unauthorized users
            return {"status": "ok", "message": "Authentication failed"}

        # Check if message contains voice or audio
        has_voice = "voice" in message
        has_audio = "audio" in message

        if not has_voice and not has_audio:
            # Send help message for text messages
            help_text = (
                "🎤 <b>Audio Transcription Bot</b>\n\n"
                "Send me a voice message or audio file and I'll transcribe it for you!\n\n"
                "Supported formats:\n"
                "• Voice messages (OGG)\n"
                "• Audio files (MP3, WAV, M4A, etc.)\n\n"
                "Just record a voice message or upload an audio file to get started."
            )
            await webhook_handler.send_message(chat_id, help_text, message_id)
            return {"status": "ok", "message": "Help message sent"}

        # Process voice message
        if has_voice:
            logger.info(f"Processing voice message from user {user_id}")
            transcription = await webhook_handler.process_voice_message(message)

            if transcription:
                # Format response
                response_text = f"🎤 <b>Voice Transcription:</b>\n\n{transcription}"
                await webhook_handler.send_message(chat_id, response_text, message_id)

                logger.info(f"Voice transcription completed for user {user_id}")
                return {"status": "ok", "message": "Voice transcription completed"}
            else:
                error_text = "❌ Failed to transcribe voice message. Please try again."
                await webhook_handler.send_message(chat_id, error_text, message_id)
                return {"status": "error", "message": "Voice transcription failed"}

        # Process audio message
        if has_audio:
            logger.info(f"Processing audio message from user {user_id}")
            transcription = await webhook_handler.process_audio_message(message)

            if transcription:
                # Format response
                filename = message["audio"].get("file_name", "Unknown")
                response_text = f"🎵 <b>Audio Transcription</b> ({filename}):\n\n{transcription}"
                await webhook_handler.send_message(chat_id, response_text, message_id)

                logger.info(f"Audio transcription completed for user {user_id}")
                return {"status": "ok", "message": "Audio transcription completed"}
            else:
                error_text = "❌ Failed to transcribe audio file. Please try again."
                await webhook_handler.send_message(chat_id, error_text, message_id)
                return {"status": "error", "message": "Audio transcription failed"}

        return {"status": "ok", "message": "Request processed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/webhook")
async def webhook_info():
    """
    Get webhook information (for debugging).

    Returns:
        dict: Webhook configuration info
    """
    return {
        "webhook_url": settings.webhook_url,
        "status": "active",
        "supported_message_types": ["voice", "audio"],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
