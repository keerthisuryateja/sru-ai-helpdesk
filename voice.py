import os
import io
import base64
import asyncio
import logging
import tempfile

import speech_recognition as sr

logger = logging.getLogger("voice")
logging.basicConfig(level=logging.INFO)

# ============================================================================
# TTS Engine Selection (Ordered by speed)
# ============================================================================
# 1. edge-tts  — Microsoft Edge neural voices via network (~200-400ms, best quality)
# 2. pyttsx3   — System SAPI5 voices, instant offline (~50-100ms, lower quality)
# 3. Kokoro    — ONNX neural TTS, local but slow (~2-8s on CPU, highest quality)
# ============================================================================

_pyttsx3_engine = None
_edge_tts_cooldown_until = 0.0


def _get_pyttsx3():
    """Lazy-init pyttsx3 engine (Windows SAPI5 voices)."""
    global _pyttsx3_engine
    if _pyttsx3_engine is None:
        try:
            import pyttsx3
            _pyttsx3_engine = pyttsx3.init()
            _pyttsx3_engine.setProperty('rate', 175)  # Slightly faster than default
            _pyttsx3_engine.setProperty('volume', 0.95)
            # Try to pick a female voice if available
            voices = _pyttsx3_engine.getProperty('voices')
            for v in voices:
                if 'zira' in v.name.lower() or 'female' in v.name.lower():
                    _pyttsx3_engine.setProperty('voice', v.id)
                    break
            logger.info("pyttsx3 engine initialized successfully.")
        except Exception as e:
            logger.warning(f"pyttsx3 init failed: {e}")
            _pyttsx3_engine = None
    return _pyttsx3_engine


def _tts_edge(text: str) -> str:
    """Generate TTS via edge-tts (Microsoft Edge neural voices). Returns base64 data URI."""
    global _edge_tts_cooldown_until
    import time
    if time.time() < _edge_tts_cooldown_until:
        return ""

    try:
        import edge_tts
    except ImportError:
        logger.warning("edge-tts not installed")
        return ""

    async def _generate():
        communicate = edge_tts.Communicate(
            text,
            voice="en-US-AriaNeural",
            rate="+10%",
            pitch="+0Hz"
        )
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data

    try:
        # Run async edge-tts in a sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an existing event loop (e.g., FastAPI with uvicorn)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                mp3_bytes = pool.submit(lambda: asyncio.run(_generate())).result(timeout=2.0)
        else:
            mp3_bytes = asyncio.run(_generate())

        if mp3_bytes and len(mp3_bytes) > 100:
            return f"data:audio/mp3;base64,{base64.b64encode(mp3_bytes).decode('utf-8')}"
    except Exception as e:
        # Set cooldown for 15 minutes so subsequent requests do not pay a timeout penalty
        _edge_tts_cooldown_until = time.time() + 900
        logger.warning(f"edge-tts failed ({e}). Cooling down edge-tts for 15 minutes, using fast pyttsx3.")

    return ""


def _tts_pyttsx3(text: str) -> str:
    """Generate TTS via pyttsx3 (system SAPI5 voices). Returns base64 data URI."""
    engine = _get_pyttsx3()
    if engine is None:
        return ""

    try:
        # pyttsx3 requires saving to file, use a temp file
        tmp_path = os.path.join(tempfile.gettempdir(), "sru_tts_temp.wav")
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()

        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 100:
            with open(tmp_path, "rb") as f:
                wav_bytes = f.read()
            b64 = base64.b64encode(wav_bytes).decode("utf-8")
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            return f"data:audio/wav;base64,{b64}"
    except Exception as e:
        logger.warning(f"pyttsx3 generation failed: {e}")

    return ""


# Kokoro lazy loader (kept as fallback but not primary)
_kokoro_instance = None
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "kokoro-v0_19.onnx")
VOICES_PATH = os.path.join(MODEL_DIR, "voices.bin")


def _tts_kokoro(text: str) -> str:
    """Generate TTS via Kokoro ONNX (local neural TTS). Slow but high quality."""
    global _kokoro_instance
    if _kokoro_instance is None:
        if not os.path.exists(MODEL_PATH) or not os.path.exists(VOICES_PATH):
            return ""
        try:
            import numpy as np
            _orig_np_load = np.load
            np.load = lambda *args, **kwargs: _orig_np_load(
                *args, allow_pickle=True,
                **{k: v for k, v in kwargs.items() if k != 'allow_pickle'}
            )
            from kokoro_onnx import Kokoro
            _kokoro_instance = Kokoro(MODEL_PATH, VOICES_PATH)
            np.load = _orig_np_load
            logger.info("Kokoro ONNX TTS initialized (fallback).")
        except Exception as e:
            logger.warning(f"Kokoro init failed: {e}")
            return ""

    try:
        import numpy as np
        import soundfile as sf
        samples, sample_rate = _kokoro_instance.create(text, voice="af_sarah", speed=1.0, lang="en-us")
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, samples, sample_rate, format="WAV")
        b64 = base64.b64encode(wav_buffer.getvalue()).decode("utf-8")
        return f"data:audio/wav;base64,{b64}"
    except Exception as e:
        logger.error(f"Kokoro TTS generation error: {e}")
        return ""


def text_to_speech_base64(text: str, voice: str = "af_sarah", speed: float = 1.0) -> str:
    """
    Synthesize text to speech using the fastest available engine.
    Priority: edge-tts (fast neural) > pyttsx3 (instant offline) > Kokoro (slow neural)
    Returns a base64-encoded audio data URI.
    """
    if not text or not text.strip():
        return ""

    import time

    # Clean text for TTS
    clean_text = (
        text.replace("*", "")
        .replace("#", "")
        .replace("`", "")
        .replace("[", "")
        .replace("]", "")
        .strip()
    )

    if not clean_text:
        return ""

    # Engine 1: edge-tts (best speed + quality combo)
    t0 = time.perf_counter()
    result = _tts_edge(clean_text)
    if result:
        ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[TTS] edge-tts: {ms:.0f}ms for {len(clean_text)} chars")
        return result

    # Engine 2: pyttsx3 (instant offline fallback)
    t0 = time.perf_counter()
    result = _tts_pyttsx3(clean_text)
    if result:
        ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[TTS] pyttsx3: {ms:.0f}ms for {len(clean_text)} chars")
        return result

    # Engine 3: Kokoro ONNX (slowest but best quality, only if models present)
    t0 = time.perf_counter()
    result = _tts_kokoro(clean_text)
    if result:
        ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[TTS] kokoro: {ms:.0f}ms for {len(clean_text)} chars")
        return result

    logger.warning("[TTS] All engines failed, returning empty audio.")
    return ""


def speech_to_text(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Convert speech audio bytes (WebM, WAV, MP3, OGG) into text.
    Uses Groq Whisper-large-v3 if GROQ_API_KEY is available for high-speed, multi-format STT,
    with local SpeechRecognition fallback.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        return ""

    # 1. Groq Whisper (Handles WebM, WAV, MP3 natively with extreme accuracy and speed)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key and groq_key.strip():
        try:
            from openai import OpenAI
            client = OpenAI(api_key=groq_key.strip(), base_url="https://api.groq.com/openai/v1")

            # Determine extension from filename or default to webm
            _, ext = os.path.splitext(filename)
            if not ext:
                ext = ".webm"

            audio_buf = io.BytesIO(audio_bytes)
            audio_buf.name = f"voice_input{ext}"

            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_buf,
                language="en",
                temperature=0.0
            )
            recognized = transcription.text.strip()
            if recognized:
                logger.info(f"[GROQ WHISPER STT] Successfully transcribed: '{recognized}'")
                return recognized
        except Exception as e:
            logger.warning(f"Groq Whisper transcription failed, trying fallback: {e}")

    # 2. Local SpeechRecognition fallback (for standard PCM WAV files)
    recognizer = sr.Recognizer()
    try:
        audio_file = io.BytesIO(audio_bytes)
        with sr.AudioFile(audio_file) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            logger.info(f"[SPEECH_RECOGNITION STT] Transcribed: '{text}'")
            return text.strip()
    except sr.UnknownValueError:
        logger.info("SpeechRecognition could not understand audio")
        return ""
    except Exception as e:
        logger.error(f"Audio processing error in SpeechRecognition: {e}")
        return ""
