"""
Brain Modular Voice Layer (Mouth) (Phase 19 Companion Evolution).
Provides zero-overhead speech synthesis (TTS) using native Linux Mint utilities
(spd-say / espeak-ng), intelligent response preparation, sentence segmentation,
and thread-safe speech queuing with synchronized companion avatar state.
"""

import os
import re
import queue
import shutil
import subprocess
import threading
import time
from typing import Optional, List, Dict, Any


class ResponsePreparer:
    """
    Cleans and prepares assistant outputs for pleasant, human-like voice synthesis.
    Strips raw markdown syntax, code fences, markdown tables, telemetry, and converts
    URLs or paths into natural spoken language tokens.
    """
    @staticmethod
    def prepare_for_speech(text: str) -> str:
        if not text or not isinstance(text, str):
            return ""

        # Remove code blocks ```...```
        cleaned = re.sub(r"```[\s\S]*?```", " [code snippet omitted] ", text)
        
        # Remove inline code `...`
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

        # Remove markdown tables (| ... |)
        cleaned = re.sub(r"(?:\|[^\n]+\|\n?)+", " [table omitted] ", cleaned)

        # Remove markdown links [title](url) -> title
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)

        # Convert remaining URLs to 'link'
        cleaned = re.sub(r"https?://\S+", "link", cleaned)

        # Remove internal telemetry markers and tags
        cleaned = re.sub(r"\[(TELEMETRY|TIMING|BENCHMARK|SYSTEM)\][^\n]*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"Confidence:\s*[\d.]+", "", cleaned)

        # Remove markdown headers and emphasis symbols
        cleaned = re.sub(r"[#*_~>]+", "", cleaned)

        # Remove excessive whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned


class SentenceSegmenter:
    """
    Splits text into natural pause chunks for progressive, low-latency speech.
    Protects common abbreviations, decimal numbers, and URLs.
    """
    ABBREVIATIONS = ("e.g.", "i.e.", "mr.", "ms.", "dr.", "vs.", "etc.", "v1.", "v2.")

    @classmethod
    def segment(cls, text: str) -> List[str]:
        if not text or not isinstance(text, str):
            return []

        # Replace known abbreviations with a placeholder to prevent split
        working = text
        for idx, abbr in enumerate(cls.ABBREVIATIONS):
            working = working.replace(abbr, f"__ABBR_{idx}__")

        # Split on sentence terminals followed by space or end-of-string
        raw_chunks = re.split(r"(?<=[.!?])\s+", working)

        sentences = []
        for chunk in raw_chunks:
            # Restore abbreviations
            for idx, abbr in enumerate(cls.ABBREVIATIONS):
                chunk = chunk.replace(f"__ABBR_{idx}__", abbr)
            chunk = chunk.strip()
            if chunk:
                sentences.append(chunk)

        return sentences


class BaseVoiceProvider:
    """Interface for text-to-speech providers."""
    def speak(self, text: str, wait: bool = False) -> bool:
        raise NotImplementedError()

    def is_available(self) -> bool:
        raise NotImplementedError()


class LinuxNativeTTS(BaseVoiceProvider):
    """
    Ultra-lightweight Linux-native speech synthesis.
    Leverages spd-say (Speech Dispatcher) or espeak-ng with zero GPU/RAM overhead.
    """
class LinuxNativeTTS(BaseVoiceProvider):
    """
    Ultra-lightweight Linux-native speech synthesis.
    Leverages spd-say (Speech Dispatcher) or espeak-ng with zero GPU/RAM overhead.
    """
    def __init__(self):
        self.engine = None
        if shutil.which("spd-say"):
            self.engine = "spd-say"
        elif shutil.which("espeak-ng"):
            self.engine = "espeak-ng"

        self._active_proc: Optional[subprocess.Popen] = None
        self._proc_lock = threading.Lock()

    def is_available(self) -> bool:
        return self.engine is not None and os.environ.get("BRAIN_MOCK_GUI") != "1"

    def stop(self):
        """Cancel and terminate any currently playing TTS process."""
        with self._proc_lock:
            if self._active_proc:
                try:
                    self._active_proc.terminate()
                    self._active_proc.wait(timeout=0.5)
                except Exception:
                    try:
                        self._active_proc.kill()
                    except Exception:
                        pass
                self._active_proc = None

    def speak(self, text: str, wait: bool = False) -> bool:
        if not text or not isinstance(text, str):
            return False

        if not self.is_available():
            return True  # Mock / headless environment

        clean_text = text.replace('"', '').replace("'", "").strip()
        if not clean_text:
            return False

        def _run():
            wav_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "tts.wav"))
            try:
                os.makedirs(os.path.dirname(wav_path), exist_ok=True)
                
                if self.engine == "spd-say":
                    with self._proc_lock:
                        self._active_proc = subprocess.Popen(["spd-say", "-r", "10", "-p", "5", clean_text])
                    self._active_proc.wait(timeout=15)
                elif self.engine == "espeak-ng":
                    # Save to WAV first
                    with self._proc_lock:
                        self._active_proc = subprocess.Popen(["espeak-ng", "-s", "175", "-p", "50", "-w", wav_path, clean_text])
                    self._active_proc.wait(timeout=15)
                    
                    # Notify Desktop Mate Bridge via Event Bus
                    from core.companion_state import default_companion_state
                    default_companion_state.broadcast("OS_EVENT", {"type": "VOICE_READY", "file": wav_path})

                    # Play locally as fallback/sync
                    with self._proc_lock:
                        self._active_proc = subprocess.Popen(["aplay", wav_path])
                    self._active_proc.wait(timeout=15)
            except Exception:
                pass
            finally:
                with self._proc_lock:
                    self._active_proc = None
                # Clean up temporary audio file to prevent storage buildup
                if os.path.isfile(wav_path):
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass

        if wait:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()
        return True



class SpeechQueue:
    """
    Thread-safe FIFO speech queue coordinating playback and companion mouth animation.
    """
    def __init__(self, provider: BaseVoiceProvider):
        self.provider = provider
        self._queue: queue.Queue = queue.Queue()
        self._stop_requested = threading.Event()
        self._is_speaking = False
        self._lock = threading.Lock()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def enqueue(self, sentence: str, broadcast_hook=None):
        """Enqueue a sentence to be spoken."""
        if not sentence:
            return
        self._queue.put((sentence, broadcast_hook))

    def interrupt(self):
        """Interrupt and flush all remaining speech in the queue."""
        self._stop_requested.set()
        if hasattr(self.provider, "stop"):
            try:
                self.provider.stop()
            except Exception:
                pass
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except Exception:
                    break
        self._is_speaking = False
        time.sleep(0.05)
        self._stop_requested.clear()


    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def _worker_loop(self):
        while True:
            try:
                item = self._queue.get()
                if item is None:
                    break
                sentence, broadcast_hook = item

                if self._stop_requested.is_set():
                    self._queue.task_done()
                    continue

                self._is_speaking = True
                if broadcast_hook:
                    try:
                        broadcast_hook(sentence, True)
                    except Exception:
                        pass

                # Speak sentence
                self.provider.speak(sentence, wait=True)

                if broadcast_hook and self._queue.empty():
                    try:
                        broadcast_hook("", False)
                    except Exception:
                        pass

                self._is_speaking = False
                self._queue.task_done()
            except Exception:
                self._is_speaking = False
                time.sleep(0.05)


class VoiceManager:
    """
    Central voice controller managing Mouth capabilities for Brain.
    Prepares responses, segments sentences, and manages the playback queue.
    """
    def __init__(self, provider: Optional[BaseVoiceProvider] = None):
        self.provider = provider or LinuxNativeTTS()
        self.speech_queue = SpeechQueue(self.provider)
        self.is_muted = False

    def speak(self, text: str, wait: bool = False) -> bool:
        if self.is_muted or not text:
            return False

        prepared = ResponsePreparer.prepare_for_speech(text)
        if not prepared:
            return False

        sentences = SentenceSegmenter.segment(prepared)
        if not sentences:
            return False

        # Limit to top sentences for concise voice responses
        if len(sentences) > 3:
            sentences = sentences[:3]

        def _broadcast_state(chunk: str, speaking: bool):
            try:
                from core.companion_state import default_companion_state, CompanionActivity, CompanionEvent
                if speaking:
                    default_companion_state.set_state(
                        speaking=True,
                        activity=CompanionActivity.SPEAKING,
                        status_text=f"Speaking: {chunk[:40]}..."
                    )
                    default_companion_state.broadcast(
                        CompanionEvent(
                            event_type="speech",
                            data={"speak_text": chunk, "speaking": True}
                        )
                    )
                else:
                    default_companion_state.set_state(
                        speaking=False,
                        activity=CompanionActivity.IDLE
                    )
                    default_companion_state.broadcast(
                        CompanionEvent(
                            event_type="speech",
                            data={"speak_text": "", "speaking": False}
                        )
                    )
            except Exception:
                pass

        if wait:
            # Synchronous playback of all segments
            for s in sentences:
                _broadcast_state(s, True)
                self.provider.speak(s, wait=True)
            _broadcast_state("", False)
            return True
        else:
            for s in sentences:
                self.speech_queue.enqueue(s, broadcast_hook=_broadcast_state)
            return True

    def interrupt(self):
        """Immediately stop speaking."""
        self.speech_queue.interrupt()
        try:
            from core.companion_state import default_companion_state, CompanionActivity
            default_companion_state.set_state(speaking=False, activity=CompanionActivity.IDLE)
        except Exception:
            pass

    def mute(self):
        self.is_muted = True
        self.interrupt()

    def unmute(self):
        self.is_muted = False


class SpeechInputProvider:
    """
    Stage 6L — Speech Input Provider Abstraction for future voice input integration.
    States: AVAILABLE, UNAVAILABLE, ERROR.
    Zero fake speech recognition, zero unauthorized background microphone recording.
    """
    def __init__(self):
        self.status = "UNAVAILABLE"

    def is_available(self) -> bool:
        return self.status == "AVAILABLE"

    def listen(self, duration_seconds: float = 5.0) -> Dict[str, Any]:
        return {
            "success": False,
            "status": self.status,
            "text": "",
            "error": "No safe lightweight speech-input backend loaded. Speech input is UNAVAILABLE."
        }


default_speech_input = SpeechInputProvider()
default_voice = VoiceManager()

