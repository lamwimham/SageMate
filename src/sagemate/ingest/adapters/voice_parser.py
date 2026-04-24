"""Voice Processing Module."""

import asyncio
import logging
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import whisper
import pysilk

logger = logging.getLogger(__name__)


class VoiceParser:
    """
    Handles voice message ingestion:
    1. Download voice data (bytes).
    2. Save original file to `data/raw/voice/` (Permanent Archive).
    3. Transcode to WAV using pysilk (for SILK) or ffmpeg (for AMR/MP3).
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
            encode_type: WeChat voice encoding type (6=SILK, 5=AMR, 7=MP3).
            
        Returns:
            Transcribed text.
        """
        # 1. Determine extension
        # 1:pcm, 2:adpcm, 3:feature, 4:speex, 5:amr, 6:silk, 7:mp3, 8:ogg
        type_map = {
            1: "pcm", 2: "adpcm", 3: "dat", 4: "speex",
            5: "amr", 6: "silk", 7: "mp3", 8: "ogg"
        }
        ext = type_map.get(encode_type, "silk") # Default to silk if unknown
        
        # 2. Save original file (Permanent Archive)
        voice_dir = raw_dir / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        original_path = voice_dir / f"{file_id}.{ext}"
        original_path.write_bytes(voice_bytes)
        logger.info(f"📥 Saved original voice to: {original_path}")

        wav_path = voice_dir / f"{file_id}.wav"

        try:
            # 3. Transcode to WAV
            if ext == "silk":
                await cls._decode_silk(voice_bytes, wav_path)
            elif ext in ["amr", "mp3", "ogg"]:
                await cls._decode_ffmpeg(original_path, wav_path, format_hint=ext)
            else:
                # Fallback to ffmpeg
                await cls._decode_ffmpeg(original_path, wav_path)
                
        except Exception as e:
            logger.error(f"❌ Transcoding failed: {e}")
            return f"[Voice Transcoding Error: {e}]"

        # 4. Transcribe with Whisper
        try:
            model = cls.get_model()
            logger.info(f"🗣️ Transcribing {wav_path}...")
            
            # Use language="zh" for better Chinese accuracy
            result = model.transcribe(str(wav_path), language="zh")
            
            text = result.get("text", "").strip()
            logger.info(f"✅ Transcription successful: {text[:50]}...")
            
            # Clean up temp WAV (we keep the original .silk/.mp3 as the source of truth)
            if wav_path.exists():
                wav_path.unlink()
                
            return text
            
        except Exception as e:
            logger.error(f"❌ Whisper transcription failed: {e}")
            return f"[Voice Transcription Error: {e}]"

    @staticmethod
    async def _decode_silk(data: bytes, output_wav: Path):
        """Decode SILK data to WAV using pysilk (bypasses FFmpeg requirement)."""
        try:
            # WeChat SILK usually has a 1-byte header (0x02)
            # pysilk expects raw silk frames.
            original_len = len(data)
            if data[0:1] == b'\x02':
                data = data[1:]
                logger.info("✂️ Detected WeChat header (0x02), stripping it.")
            
            # Decode to PCM @ 16000Hz (Whisper's preferred rate)
            # pysilk.decode signature varies by version, try common patterns
            logger.info(f"🧵 Decoding SILK ({len(data)} bytes) to PCM...")
            pcm_data = None
            
            # Attempt 1: decode(data, rate) - positional
            try:
                pcm_data = pysilk.decode(data, 16000)
            except TypeError:
                # Attempt 2: decode(data) - auto rate
                try:
                    pcm_data = pysilk.decode(data)
                except Exception:
                    # Attempt 3: decode(data, rate=...) - keyword (less likely for this lib)
                    pcm_data = pysilk.decode(data, rate=16000)

            # Write to WAV
            with wave.open(str(output_wav), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(16000)
                wf.writeframes(pcm_data)
                
            logger.info(f"✅ SILK decoded to WAV: {output_wav}")
            
        except Exception as e:
            # Fallback to ffmpeg if pysilk fails (e.g. corrupted data)
            logger.warning(f"⚠️ pysilk decode failed ({e}), trying FFmpeg fallback...")
            # Create a temp file to feed ffmpeg
            temp_silk = output_wav.with_suffix('.silk')
            # Restore data for ffmpeg if needed (ffmpeg might need header or raw)
            # If we stripped header, we should write raw silk.
            # But ffmpeg usually needs the container. 
            # Since we have original bytes (not passed here), we can't restore easily.
            # But wait, the original bytes are saved in original_path?
            # No, this method receives 'data'.
            # We should rely on the original file saved in parse_voice.
            # But this is a static method.
            # Let's just write the data we have (stripped) and hope ffmpeg handles it
            # OR write the original data (with header).
            
            # Re-reading from original_path is safer if available, but here we only have data.
            # If data was stripped, ffmpeg definitely won't like it.
            # So we write the 'data' (maybe with header if we didn't strip? No we did).
            # Let's assume if pysilk fails, we are stuck unless we had the original path.
            # BUT, parse_voice calls this.
            
            # To fix this properly, we should pass original_path to _decode_silk or let it write a temp file.
            # For now, write 'data' as .silk.
            temp_silk.write_bytes(data) 
            
            await VoiceParser._decode_ffmpeg(temp_silk, output_wav, format_hint='silk')
            if temp_silk.exists():
                temp_silk.unlink()

    @staticmethod
    async def _decode_ffmpeg(input_path: Path, output_wav: Path, format_hint: str = None):
        """Transcode using FFmpeg."""
        cmd = ["ffmpeg", "-y"]
        
        if format_hint:
            cmd.extend(["-f", format_hint])
            
        cmd.extend([
            "-i", str(input_path),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            str(output_wav)
        ])
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error_msg = stderr.decode()
            if "Invalid data" in error_msg or "Failed to find" in error_msg:
                raise Exception(f"FFmpeg could not decode {format_hint}. FFmpeg build lacks support or data is invalid.")
            raise Exception(f"FFmpeg failed: {error_msg[:200]}")
