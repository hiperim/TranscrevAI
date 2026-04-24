import time
from typing import Dict, Any, Optional
import asyncio
import logging
from fastapi import WebSocket
from src.error_messages import get_user_message
from src.exceptions import ValidationError, SessionError, AudioProcessingError
# Import pipeline function
from src.pipeline import process_audio_pipeline

logger = logging.getLogger(__name__)

# Limits for live recording
MAX_RECORDING_DURATION = 600  # 10 min

class WebSocketValidator:

    def validate_action(self, action: Optional[str]):
        """Validates the 'action' field, raising ValidationError"""
        if not action or action not in ["start", "audio_chunk", "stop", "pause", "resume"]:
            logger.warning("Invalid or missing action received", extra={"action": action})
            raise ValidationError(get_user_message("invalid_action"))
        return None

    def validate_audio_format(self, audio_format: str):
        """Validates the audio format, raising ValidationError"""
        if audio_format not in ["wav", "mp4"]:
            logger.warning("Invalid audio format received", extra={"format": audio_format})
            raise ValidationError(get_user_message("invalid_format"))
        return None

    def validate_recording_duration(self, recording_start_time: Optional[float]):
        """Checks if recording reached 60min limit and auto-stops"""
        if recording_start_time is None:
            return False
        elapsed_time = time.time() - recording_start_time
        if elapsed_time > MAX_RECORDING_DURATION:
            logger.warning("Recording duration reached 60min limit", extra={"duration": elapsed_time, "limit": MAX_RECORDING_DURATION})
            return True  # Signal for auto-stop
        return False