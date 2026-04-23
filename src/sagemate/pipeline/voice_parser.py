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
    2. Save original file to `data/raw/voice/` (Permanent Archive).
    3. Transcode to WAV using ffmpeg (WeChat voice is usually SILK/AMR).
    4. Transcribe to text using local Whisper.
    """

    # Load model once (singleton-like behavior)
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            logger.info("🎤 Loading Whisper 'base' model (this may take a moment)...")
            cls._model = whisper.load_model("base")
        return cls._model

    @classmethod
    async def parse_voice(cls, voice_bytes: bytes, file_id: str, raw_dir: Path, encode_type: int = 6) -> str:
        """
        Process voice bytes and return transcribed text.
        
        Args:
            voice_bytes: The raw voice data (usually SILK format from WeChat).
            file_id: A unique identifier for the filename.
            raw_dir: Path to the raw directory.
            encode_type: WeChat voice encoding type (5=AMR, 6=SILK, 7=MP3).
            
        Returns:
            Transcribed text.
        """
        # 1. Determine extension based on encode_type
        # WeChat Voice Types: 1:pcm, 2:adpcm, 3:feature, 4:speex, 5:amr, 6:silk, 7:mp3, 8:ogg
        type_map = {
            1: "pcm", 2: "adpcm", 3: "dat", 4: "speex",
            5: "amr", 6: "silk", 7: "mp3", 8: "ogg"
        }
        ext = type_map.get(encode_type, "silk") # Default to silk if unknown
        
        # 2. Detect actual format by file header (more reliable than encode_type)
        # SILK_V3 files start with b'\x02#!SILK_V3' or b'#!SILK_V3'
        if voice_bytes.startswith(b'#!SILK_V3') or (len(voice_bytes) > 1 and voice_bytes[1:].startswith(b'#!SILK_V3')):
            ext = "silk"
            logger.info("🔍 Detected SILK_V3 format by file header")
        
        # 3. Save original file (Permanent Archive)
        voice_dir = raw_dir / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        original_path = voice_dir / f"{file_id}.{ext}"
        original_path.write_bytes(voice_bytes)
        logger.info(f"📥 Saved original voice to: {original_path}")

        # 4. Transcode to WAV for Whisper
        wav_path = voice_dir / f"{file_id}.wav"
        try:
            if ext == "silk":
                # Use pysilk for SILK decoding (ffmpeg doesn't support SILK on macOS)
                import pysilk
                import wave
                
                logger.info("🔄 Decoding SILK using pysilk...")
                pcm_data = pysilk.decode(voice_bytes, sample_rate=16000)
                
                with wave.open(str(wav_path), 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(16000)
                    wav_file.writeframes(pcm_data)
                
                logger.info(f"✅ SILK decoded to {len(pcm_data)} PCM bytes -> WAV")
            else:
                # Use ffmpeg for other formats (AMR, MP3, OGG, etc.)
                input_args = []
                if ext == "amr":
                    input_args = ["-f", "amr"]
                
                cmd = [
                    "ffmpeg", "-y",
                    *input_args,
                    "-i", str(original_path), 
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                    str(wav_path)
                ]
                
                proc = await asyncio.create_subprocess_exec(
                    *cmd, 
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if proc.returncode != 0:
                    error_msg = stderr.decode()
                    raise Exception(f"FFmpeg failed: {error_msg[:200]}")
                
        except Exception as e:
            logger.error(f"❌ Voice transcoding failed: {e}")
            return f"[Voice Transcoding Error: {e}]"

        # 5. Transcribe with Whisper
        try:
            model = cls.get_model()
            logger.info(f"🗣️ Transcribing {wav_path}...")
            
            # Use language="zh" for better Chinese accuracy
            result = model.transcribe(str(wav_path), language="zh")
            
            text = result.get("text", "").strip()
            logger.info(f"✅ Transcription successful: {text[:50]}...")
            
            # Clean up temp WAV (we keep the original .silk as the source of truth)
            if wav_path.exists():
                wav_path.unlink()
                
            return text
            
        except Exception as e:
            logger.error(f"❌ Whisper transcription failed: {e}")
            return f"[Voice Transcription Error: {e}]"
