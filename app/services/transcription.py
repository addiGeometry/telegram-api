import os
import tempfile
import logging
from typing import Optional
import aiohttp
import openai
from openai import AsyncOpenAI
from app.utils.config import settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Custom exception for transcription failures."""
    pass


class TranscriptionService:
    """Service for handling audio transcription using OpenAI Whisper API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.telegram_token = settings.telegram_token

    async def download_audio_file(self, file_id: str) -> bytes:
        """
        Download audio file from Telegram servers.

        Args:
            file_id: The file ID from Telegram

        Returns:
            bytes: The audio file content

        Raises:
            TranscriptionError: If download fails
        """
        try:
            # First get file info from Telegram API
            file_info_url = f"https://api.telegram.org/bot{self.telegram_token}/getFile"

            async with aiohttp.ClientSession() as session:
                async with session.get(file_info_url, params={"file_id": file_id}) as response:
                    if response.status != 200:
                        raise TranscriptionError(f"Failed to get file info: {response.status}")

                    file_info = await response.json()
                    if not file_info.get("ok"):
                        raise TranscriptionError(f"Telegram API error: {file_info.get('description')}")

                    file_path = file_info["result"]["file_path"]

                # Download the actual file
                file_url = f"https://api.telegram.org/file/bot{self.telegram_token}/{file_path}"
                async with session.get(file_url) as response:
                    if response.status != 200:
                        raise TranscriptionError(f"Failed to download file: {response.status}")

                    return await response.read()

        except aiohttp.ClientError as e:
            logger.error(f"Network error downloading audio file: {e}")
            raise TranscriptionError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error downloading audio file: {e}")
            raise TranscriptionError(f"Download failed: {e}")

    async def transcribe_audio(self, audio_data: bytes, filename: str = "audio.ogg") -> str:
        """
        Transcribe audio data using OpenAI Whisper API.

        Args:
            audio_data: The audio file content as bytes
            filename: The filename to use for the temporary file

        Returns:
            str: The transcribed text

        Raises:
            TranscriptionError: If transcription fails
        """
        try:
            # Create temporary file for audio data
            with tempfile.NamedTemporaryFile(suffix=f".{filename.split('.')[-1]}", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # Transcribe using OpenAI Whisper
                with open(temp_file_path, "rb") as audio_file:
                    transcript = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )

                # Clean up whitespace and return
                transcribed_text = transcript.strip()

                if not transcribed_text:
                    raise TranscriptionError("Transcription resulted in empty text")

                logger.info(f"Successfully transcribed audio: {len(transcribed_text)} characters")
                return transcribed_text

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except openai.OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise TranscriptionError(f"OpenAI API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {e}")
            raise TranscriptionError(f"Transcription failed: {e}")

    async def process_audio_message(self, file_id: str, filename: Optional[str] = None) -> str:
        """
        Complete audio processing pipeline: download and transcribe.

        Args:
            file_id: The Telegram file ID
            filename: Optional filename for the audio file

        Returns:
            str: The transcribed text

        Raises:
            TranscriptionError: If any step fails
        """
        try:
            # Download audio file
            logger.info(f"Downloading audio file: {file_id}")
            audio_data = await self.download_audio_file(file_id)

            # Transcribe audio
            logger.info(f"Transcribing audio file: {file_id}")
            transcription = await self.transcribe_audio(
                audio_data,
                filename or "audio.ogg"
            )

            return transcription

        except TranscriptionError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing audio message: {e}")
            raise TranscriptionError(f"Processing failed: {e}")


transcription_service = TranscriptionService()
