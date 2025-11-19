import os
import platform
import subprocess
import time
import threading
import numpy as np
import scipy.io.wavfile as wav
import traceback

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default

try:
    import speech_recognition as sr
    _SPEECH_RECOGNITION_AVAILABLE = True
    _SPEECH_RECOGNITION_IMPORT_ERROR: Exception | None = None
except Exception as import_error:
    sr = None  # type: ignore[assignment]
    _SPEECH_RECOGNITION_AVAILABLE = False
    _SPEECH_RECOGNITION_IMPORT_ERROR = import_error

try:
    import sounddevice as sd
    _SOUNDDEVICE_AVAILABLE = True
    _SOUNDDEVICE_IMPORT_ERROR: Exception | None = None
except Exception as import_error:
    sd = None  # type: ignore[assignment]
    _SOUNDDEVICE_AVAILABLE = False
    _SOUNDDEVICE_IMPORT_ERROR = import_error

_STT_DEFAULT_MAX_SECONDS = _env_float("IRAA_STT_MAX_SECONDS", 12.0)

# Audio lock to prevent conflicts between recording and speaking
_audio_lock = threading.Lock()

# -------------------------------------------
#   SPEECH TO TEXT (STT) without PyAudio
# -------------------------------------------

def _list_input_devices():
    if not _SOUNDDEVICE_AVAILABLE:
        if _SOUNDDEVICE_IMPORT_ERROR:
            print(f"[STT] sounddevice unavailable: {_SOUNDDEVICE_IMPORT_ERROR}")
        return []

    try:
        devs = sd.query_devices()
        return [
            (i, d["name"], d.get("max_input_channels", 0))
            for i, d in enumerate(devs)
            if d.get("max_input_channels", 0) > 0
        ]
    except Exception as e:
        print("[STT] Could not list devices:", e)
        return []


def _write_silence(filename: str, seconds: int, samplerate: int):
    """Create a silent WAV placeholder when audio input is unavailable."""
    duration = max(seconds, 0)
    samples = int(duration * samplerate)
    data = np.zeros(samples or 1, dtype=np.int16)
    wav.write(filename, samplerate, data)
    print(f"[STT] Wrote silent audio to {filename} ({duration:.2f}s)")

def record_to_wav(filename: str, seconds: int = 4, samplerate: int = 16000, device: int | None = None, max_seconds: float | None = None):
    """
    Record audio via sounddevice (int16 mono), write to WAV.
    Leverages an adaptive stop on trailing silence so we return faster once
    the speaker finishes talking. Uses audio lock to prevent conflicts with speaking.
    """

    def _adaptive_capture(target_seconds: float, sr: int, input_device: int | None, hard_limit_seconds: float) -> np.ndarray:
        """
        Capture audio in small blocks and stop early when silence is detected.
        Falls back to the fixed-length recorder if anything goes wrong.
        """
        channels = 1
        base_seconds = max(target_seconds, 0.5)
        hard_limit_seconds = max(hard_limit_seconds, base_seconds)
        max_frames = int(base_seconds * sr)
        hard_limit_frames = int(hard_limit_seconds * sr)
        dynamic_limit = max_frames
        # Heuristics: shorter prompts use shorter silence windows
        if base_seconds <= 4:
            silence_window = 0.55
            min_duration = 0.4
        elif base_seconds <= 7:
            silence_window = 0.75
            min_duration = 0.55
        else:
            silence_window = 1.0
            min_duration = 0.65
        min_frames = int(min(min_duration, base_seconds) * sr)
        block_duration = 0.12  # seconds
        block_frames = max(256, int(block_duration * sr))
        silence_limit = int(silence_window * sr)
        extension_step = max(block_frames, int(0.6 * sr))

        total_frames = 0
        silence_frames = 0
        triggered = False
        last_voice_time = start
        noise_floor: float | None = None
        blocks: list[np.ndarray] = []

        start = time.monotonic()
        print(f" Recording up to {hard_limit_seconds:.1f}s @ {sr}Hz (device={input_device})...")

        with sd.InputStream(
            samplerate=sr,
            channels=channels,
            dtype="int16",
            device=input_device,
        ) as stream:
            while total_frames < hard_limit_frames:
                chunk, _ = stream.read(block_frames)
                if chunk is None:
                    continue
                chunk = np.asarray(chunk, dtype=np.int16).reshape(-1)
                blocks.append(chunk)
                total_frames += len(chunk)

                level = float(np.mean(np.abs(chunk)))
                if noise_floor is None:
                    noise_floor = level
                else:
                    noise_floor = 0.92 * noise_floor + 0.08 * level

                speech_level = max((noise_floor or 0.0) * 2.6, 160.0)
                quiet_level = max((noise_floor or 0.0) * 1.4, 80.0)

                if level >= speech_level:
                    triggered = True
                    silence_frames = 0
                    last_voice_time = time.monotonic()
                elif triggered:
                    if level <= quiet_level:
                        silence_frames += len(chunk)
                    else:
                        silence_frames = 0

                    if silence_frames >= silence_limit and total_frames >= min_frames:
                        break

                # Safety: if we have substantial audio but never crossed activation threshold,
                # allow the silence detector to kick in so we don't wait for the hard stop.
                if not triggered and (time.monotonic() - start) > base_seconds * 0.8:
                    triggered = True

                if total_frames >= dynamic_limit:
                    if (
                        triggered
                        and silence_frames < silence_limit
                        and dynamic_limit < hard_limit_frames
                    ):
                        dynamic_limit = min(dynamic_limit + extension_step, hard_limit_frames)
                    else:
                        break

                if (
                    triggered
                    and total_frames >= min_frames
                    and (time.monotonic() - last_voice_time) >= max(0.4, silence_window * 1.2)
                ):
                    break

        if not blocks:
            raise RuntimeError("No audio blocks captured")

        audio = np.concatenate(blocks)
        captured = len(audio) / sr

        # Trim trailing low-energy tail to shave a few hundred ms
        tail_size = int(0.25 * sr)
        window_size = max(int(0.02 * sr), 1)
        if captured > 0.3 and tail_size < len(audio):
            threshold = 200
            for idx in range(len(audio) - tail_size, len(audio), window_size):
                window = audio[idx: idx + window_size]
                if np.mean(np.abs(window)) < threshold and (len(audio) - idx) > int(0.05 * sr):
                    audio = audio[:idx]
                    break

        print(f" Audio captured in {captured:.2f}s (requested {base_seconds}s)")
        return audio

    with _audio_lock:
        if not _SOUNDDEVICE_AVAILABLE:
            print(
                "[STT] sounddevice module missing; generating silent placeholder "
                f"(error: {_SOUNDDEVICE_IMPORT_ERROR})"
            )
            _write_silence(filename, seconds, samplerate)
            return

        capture_seconds = max(float(seconds), 0.5)
        abs_limit_seconds = max(
            float(max_seconds) if max_seconds is not None else _STT_DEFAULT_MAX_SECONDS,
            capture_seconds,
        )

        try:
            if device is None:
                # Try default; if missing, pick the first input device
                try:
                    default_in = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else sd.default.device
                except Exception:
                    default_in = None
                if default_in is None:
                    inputs = _list_input_devices()
                    if inputs:
                        device = inputs[0][0]
                        print(f"[STT] Using input device index {device}: {inputs[0][1]}")
                    else:
                        raise RuntimeError("No input devices with channels > 0 found")

            try:
                audio = _adaptive_capture(capture_seconds, samplerate, device, abs_limit_seconds)
            except Exception as adaptive_err:
                print(f"[STT] Adaptive capture failed ({adaptive_err}); falling back to fixed-length capture.")
                frames = int(seconds * samplerate)
                audio = sd.rec(frames, samplerate=samplerate, channels=1, dtype="int16", device=device)
                sd.wait()
                audio = np.asarray(audio).reshape(-1)
                print(f" Audio recorded to {filename} (fallback, {seconds}s)")

            wav.write(filename, samplerate, np.asarray(audio, dtype=np.int16))
            print(f" Audio saved to {filename} ({len(audio) / samplerate:.2f}s)")
        except Exception as e:
            print(f"[STT] Recording error (sounddevice): {e}")
            traceback.print_exc()
            _write_silence(filename, seconds, samplerate)

def transcribe_wav(filename: str) -> dict:
    """
    Read the WAV file with SpeechRecognition (no microphone needed here).
    Returns {'text': ...}
    """
    if not _SPEECH_RECOGNITION_AVAILABLE:
        print(
            "[STT] speech_recognition module missing; returning empty transcription "
            f"(error: {_SPEECH_RECOGNITION_IMPORT_ERROR})"
        )
        return {"text": ""}

    r = sr.Recognizer()
    try:
        with sr.AudioFile(filename) as source:
            audio = r.record(source)
        print(" Transcribing speech...")
        text = r.recognize_google(audio)
        print(f" Heard: {text}")
        return {"text": text}
    except sr.UnknownValueError:
        print("[STT] Speech unintelligible or not recognized.")
        return {"text": ""}
    except sr.RequestError as e:
        print(f"[STT] SpeechRecognition API error: {e}")
        return {"text": ""}
    except Exception as e:
        print(f"[STT] Transcription error: {e}")
        traceback.print_exc()
        return {"text": ""}

# -------------------------------------------
#   TEXT TO SPEECH (TTS)
# -------------------------------------------

_TTS_ENGINE = None
_TTS_READY = False
_MAC = platform.system() == "Darwin"

def _init_tts():
    global _TTS_ENGINE, _TTS_READY
    try:
        import pyttsx3
        driver = "nsss" if _MAC else None
        _TTS_ENGINE = pyttsx3.init(driverName=driver) if driver else pyttsx3.init()

        # Prefer female voices - try multiple options
        try:
            voices = _TTS_ENGINE.getProperty("voices") or []
            chosen = None
            female_names = ["samantha", "karen", "kathy", "victoria", "susan", "sarah", "zira"]
            for name in female_names:
                for v in voices:
                    if name in getattr(v, "name", "").lower():
                        chosen = v.id
                        break
                if chosen:
                    break
            if chosen:
                _TTS_ENGINE.setProperty("voice", chosen)
                print(f" Using female voice: {chosen}")
        except Exception:
            pass

        _TTS_ENGINE.setProperty("rate", 185)
        _TTS_ENGINE.setProperty("volume", 1.0)

        _TTS_ENGINE.say(" ")
        _TTS_ENGINE.runAndWait()
        _TTS_READY = True
        print(" TTS engine initialized.")
    except Exception as e:
        print("[TTS] pyttsx3 init failed:", e)
        _TTS_ENGINE = None
        _TTS_READY = False

def speak(text: str):
    """
    Speak text using female voice. Ensure completion before returning.
    On macOS, uses native 'say' command with Samantha (female) voice.
    Uses audio lock to prevent conflicts with recording.
    """
    global _TTS_READY, _TTS_ENGINE
    
    if not text or not text.strip():
        return
    
    # Check if sleep mode was requested before speaking
    try:
        from app import is_sleep_requested
        if is_sleep_requested():
            print("[TTS] Sleep mode requested - skipping speech")
            return
    except ImportError:
        pass  # If app not imported yet, continue
    
    # Use lock to prevent audio conflicts
    with _audio_lock:
        # On macOS, prefer the native 'say' command with female voice
        if _MAC:
            try:
                # Use ONLY Samantha voice and ensure completion
                # Use communicate() to ensure process fully completes
                process = subprocess.Popen(
                    ["say", "-v", "Samantha", text],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                # Wait for process to complete (with timeout)
                try:
                    stdout, stderr = process.communicate(timeout=60)
                    # Wait briefly to ensure audio hardware completes
                    time.sleep(0.05)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                    print("[TTS] Speech timed out")
                    return
                except Exception as e:
                    print(f"[TTS] Error waiting for speech: {e}")
                    return
                
                if process.returncode == 0:
                    print(f"[Iraa SPEAKING] {text}")
                else:
                    stderr_output = stderr.decode() if stderr else ""
                    print(f"[TTS] Speech process error: {stderr_output}")
                return
            except Exception as e:
                print(f"[TTS] macOS 'say' failed: {e}")
                # If Samantha fails, don't fall back - just log and return
                print(f"[TTS] Only Samantha voice is supported. Please check if Samantha voice is available.")
                return
    
        # On non-Mac systems, try pyttsx3 but prioritize Samantha-like voices
        if not _TTS_READY:
            _init_tts()

        if _TTS_ENGINE:
            try:
                # Prioritize Samantha voice, fallback to other female voices only if needed
                try:
                    voices = _TTS_ENGINE.getProperty("voices") or []
                    samantha_found = False
                    for v in voices:
                        name = getattr(v, "name", "").lower()
                        if "samantha" in name:
                            _TTS_ENGINE.setProperty("voice", v.id)
                            samantha_found = True
                            break
                    
                    # If Samantha not found, try other female voices
                    if not samantha_found:
                        for v in voices:
                            name = getattr(v, "name", "").lower()
                            if any(f in name for f in ["karen", "kathy", "victoria", "susan", "sarah", "zira"]):
                                _TTS_ENGINE.setProperty("voice", v.id)
                                break
                except Exception:
                    pass
                
                _TTS_ENGINE.say(text)
                _TTS_ENGINE.runAndWait()
                time.sleep(0.05)  # Short delay for audio buffer completion
                print(f"[Iraa SPEAKING] {text}")
                return
            except Exception as e:
                print(f"[TTS] pyttsx3 speak failed: {e}")

        print(f"[Iraa (TEXT ONLY)] {text}")

# -------------------------------------------
#  Self-test
# -------------------------------------------
if __name__ == "__main__":
    import tempfile
    print(" Testing mic & TTS without PyAudio...")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        record_to_wav(f.name, seconds=4)
        res = transcribe_wav(f.name)
        print("Transcription result:", res)
    speak("Hello Arya, Iraa is speaking using the new audio pipeline.")
