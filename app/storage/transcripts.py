import json
import asyncio
import aiofiles
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from pathlib import Path
from app.utils.config import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Custom exception for storage failures."""
    pass


class TranscriptStorage:
    """Service for persisting transcriptions to JSONL format."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = Path(file_path or settings.transcripts_file)
        self._lock = asyncio.Lock()

    async def save_transcription(
        self,
        user_id: int,
        message_id: int,
        file_id: str,
        transcription: str,
        file_type: str = "voice",
        filename: Optional[str] = None
    ) -> bool:
        """
        Save a transcription to the JSONL file.

        Args:
            user_id: The Telegram user ID
            message_id: The Telegram message ID
            file_id: The Telegram file ID
            transcription: The transcribed text
            file_type: The type of file ('voice' or 'audio')
            filename: Optional filename from the audio message

        Returns:
            bool: True if saved successfully, False otherwise

        Raises:
            StorageError: If saving fails
        """
        try:
            transcript_record = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "user_id": user_id,
                "message_id": message_id,
                "file_id": file_id,
                "file_type": file_type,
                "filename": filename,
                "transcription": transcription,
                "character_count": len(transcription)
            }

            # Use lock to ensure thread-safe file writing
            async with self._lock:
                # Ensure directory exists
                self.file_path.parent.mkdir(parents=True, exist_ok=True)

                # Append to JSONL file
                async with aiofiles.open(self.file_path, mode='a', encoding='utf-8') as f:
                    await f.write(json.dumps(transcript_record, ensure_ascii=False) + '\n')

            logger.info(f"Saved transcription for user {user_id}, message {message_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving transcription: {e}")
            raise StorageError(f"Failed to save transcription: {e}")

    async def get_transcriptions(
        self,
        user_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> list[Dict[str, Any]]:
        """
        Retrieve transcriptions from the JSONL file.

        Args:
            user_id: Filter by user ID (optional)
            limit: Maximum number of records to return (optional)

        Returns:
            list: List of transcription records

        Raises:
            StorageError: If reading fails
        """
        try:
            transcriptions = []

            # Check if file exists
            if not self.file_path.exists():
                logger.info(f"Transcriptions file does not exist: {self.file_path}")
                return transcriptions

            async with self._lock:
                async with aiofiles.open(self.file_path, mode='r', encoding='utf-8') as f:
                    async for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            record = json.loads(line)

                            # Filter by user ID if specified
                            if user_id is not None and record.get('user_id') != user_id:
                                continue

                            transcriptions.append(record)

                            # Check limit
                            if limit and len(transcriptions) >= limit:
                                break

                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON in transcriptions file: {e}")
                            continue

            logger.info(f"Retrieved {len(transcriptions)} transcriptions")
            return transcriptions

        except Exception as e:
            logger.error(f"Error reading transcriptions: {e}")
            raise StorageError(f"Failed to read transcriptions: {e}")

    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the stored transcriptions.

        Returns:
            dict: Statistics including total count, unique users, file size
        """
        try:
            stats = {
                "total_transcriptions": 0,
                "unique_users": set(),
                "file_size_bytes": 0,
                "file_exists": False
            }

            if not self.file_path.exists():
                return stats

            stats["file_exists"] = True
            stats["file_size_bytes"] = self.file_path.stat().st_size

            async with self._lock:
                async with aiofiles.open(self.file_path, mode='r', encoding='utf-8') as f:
                    async for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            record = json.loads(line)
                            stats["total_transcriptions"] += 1
                            stats["unique_users"].add(record.get('user_id'))
                        except json.JSONDecodeError:
                            continue

            # Convert set to count for JSON serialization
            stats["unique_users"] = len(stats["unique_users"])

            return stats

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            raise StorageError(f"Failed to get storage stats: {e}")

    async def backup_transcriptions(self, backup_path: str) -> bool:
        """
        Create a backup of the transcriptions file.

        Args:
            backup_path: Path for the backup file

        Returns:
            bool: True if backup was successful
        """
        try:
            if not self.file_path.exists():
                logger.warning("No transcriptions file to backup")
                return False

            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)

            async with self._lock:
                async with aiofiles.open(self.file_path, mode='rb') as src:
                    async with aiofiles.open(backup_file, mode='wb') as dst:
                        async for chunk in src:
                            await dst.write(chunk)

            logger.info(f"Backup created: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            raise StorageError(f"Failed to create backup: {e}")


# Create singleton instance
transcript_storage = TranscriptStorage()
