"""Voice Processing Module."""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import whisper

logger = logging.getLogger(__name__)


class VoiceParser:
    """
    Handles voice message ingestion:
    1. Download voice data (bytes).
    2. Save original file to `data/raw/voice/`.
    3. Transcode to WAV using ffmpeg (WeChat voice is usually SILK).
    4. Transcribe to text using local Whisper.
    """

    # Load model once (singleton-like behavior)
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            logger.info("🎤 Loading Whisper 'base' model...")
            cls._model = whisper.load_model("base")
        return cls._model

    @classmethod
    async def parse_voice(cls, voice_bytes: bytes, file_id: str, raw_dir: Path) -> str:
        """
        Process voice bytes and return transcribed text.
        
        Args:
            voice_bytes: The raw voice data (usually SILK format from WeChat).
            file_id: A unique identifier for the filename.
            raw_dir: Path to the raw directory.
            
        Returns:
            Transcribed text.
        """
        # 1. Save original file
        voice_dir = raw_dir / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        original_path = voice_dir / f"{file_id}.mp3" # WeChat often sends mp3/silk, save as mp3 for safety
        original_path.write_bytes(voice_bytes)
        logger.info(f"📥 Saved original voice to: {original_path}")

        # 2. Transcode to WAV for Whisper
        wav_path = voice_dir / f"{file_id}.wav"
        try:
            # ffmpeg command to decode to 16kHz mono wav
            cmd = [
                "ffmpeg", "-y", "-i", str(original_path), 
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                str(wav_path)
            ]
            
            # Run ffmpeg asynchronously
            proc = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                raise Exception(f"FFmpeg failed: {stderr.decode()}")
                
        except Exception as e:
            logger.error(f"❌ FFmpeg transcoding failed: {e}")
            return f"[Voice Transcoding Error: {e}]"

        # 3. Transcribe with Whisper
        try:
            model = cls.get_model()
            logger.info(f"🗣️ Transcribing {wav_path}...")
            
            result = model.transcribe(str(wav_path), language="zh") # Force Chinese
            
            text = result.get("text", "").strip()
            logger.info(f"✅ Transcription successful: {text[:50]}...")
            
            # Clean up temp WAV if needed, but keeping original mp3 is enough
            if wav_path.exists():
                wav_path.unlink()
                
            return text
            
        except Exception as e:
            logger.error(f"❌ Whisper transcription failed: {e}")
            return f"[Voice Transcription Error: {e}]"
