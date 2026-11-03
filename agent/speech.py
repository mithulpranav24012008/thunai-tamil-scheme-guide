"""Speech-to-text layer for Thunai.

Kept separate from agent logic.  Uses Amazon Transcribe streaming (no S3 needed)
for both file transcription (--audio, the testable path) and microphone input
(--voice).  Returns a dict with transcript, confidence, and a low-confidence flag.

No agent imports, no safety logic — pure STT.
"""
from __future__ import annotations

import os
import tempfile
import wave

# Confidence below this → is_low_confidence = True.  Configurable via env.
_CONFIDENCE_THRESHOLD = float(os.environ.get("SHIP_STT_CONFIDENCE", "0.6"))


def transcribe_file(path: str, language_code: str = "ta-IN") -> dict:
    """Transcribe a WAV file via Amazon Transcribe streaming.

    Args:
        path: Path to a 16 kHz mono PCM WAV file.
        language_code: "ta-IN" (Tamil), "en-IN" (Indian English), or other Transcribe code.

    Returns:
        {"transcript": str, "confidence": float, "language_code": str, "is_low_confidence": bool}

    Raises:
        FileNotFoundError if the file doesn't exist.
        RuntimeError if Transcribe fails or the package isn't installed.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    try:
        from amazon_transcribe.client import TranscribeStreamingClient
    except ImportError:
        raise RuntimeError(
            "amazon-transcribe package not installed. Run: pip install amazon-transcribe==0.6.4"
        )

    region = os.environ.get("AWS_REGION", "us-east-1")
    client = TranscribeStreamingClient(region=region)

    with wave.open(path, "rb") as wf:
        frames = wf.readframes(wf.getnframes())

    stream = client.start_stream_transcription(
        language_code=language_code,
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )

    chunk_size = 8192
    for i in range(0, len(frames), chunk_size):
        stream.input_stream.send_audio_event(audio_chunk=frames[i:i + chunk_size])
    stream.input_stream.end_stream()

    transcript_parts = []
    confidence_scores = []
    try:
        for event in stream.output_stream:
            results = event.transcript.results
            for result in results:
                if not result.is_partial:
                    for alt in result.alternatives:
                        transcript_parts.append(alt.transcript)
                        if hasattr(alt, "confidence") and alt.confidence:
                            confidence_scores.append(float(alt.confidence))
                        break
    except Exception:
        pass

    transcript = " ".join(transcript_parts).strip()
    confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    is_low = confidence < _CONFIDENCE_THRESHOLD

    return {
        "transcript": transcript,
        "confidence": round(confidence, 3),
        "language_code": language_code,
        "is_low_confidence": is_low or not transcript,
    }


def record_microphone(max_seconds: int = 15, sample_rate: int = 16000) -> str:
    """Record from the default microphone until silence, Enter, or max_seconds.

    Saves to a temporary WAV file and returns its path.  Caller must call
    cleanup(path) after transcription.

    Raises:
        RuntimeError if sounddevice is not installed or no microphone is found.
    """
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        raise RuntimeError(
            "sounddevice not installed. Run: pip install sounddevice numpy  (macOS may also need: brew install portaudio)"
        )

    print("🎤 Recording... (speak now, press Enter to stop)", flush=True)
    recording = []
    import threading

    stop_flag = threading.Event()

    def _wait_enter():
        try:
            input()
        except EOFError:
            pass
        stop_flag.set()

    t = threading.Thread(target=_wait_enter, daemon=True)
    t.start()

    chunk_duration = 0.5
    chunks_needed = int(max_seconds / chunk_duration)
    for _ in range(chunks_needed):
        if stop_flag.is_set():
            break
        audio = sd.rec(int(sample_rate * chunk_duration), samplerate=sample_rate,
                      channels=1, dtype="int16")
        sd.wait()
        recording.append(audio)

    if not recording:
        raise RuntimeError("No audio recorded.")

    audio_data = np.concatenate(recording, axis=0)
    print(f"🎤 Recorded {len(audio_data) / sample_rate:.1f}s", flush=True)

    fd, tmp_path = tempfile.mkstemp(suffix=".wav", prefix="thunai_stt_")
    os.close(fd)
    with wave.open(tmp_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())

    return tmp_path


def cleanup(path: str) -> None:
    """Delete a temporary audio file.  Silent if it doesn't exist."""
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def pick_language_code(text_hint: str) -> str:
    """Pick a Transcribe language code from a short text hint."""
    from .tools import language_of
    return "ta-IN" if language_of(text_hint) == "ta" else "en-IN"
