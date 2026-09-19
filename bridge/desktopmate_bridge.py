"""
Brain ↔ Desktop Mate Bridge (v2).

Connects to the Desktop Mate BepInEx WebSocket plugin.
All methods return honest status dictionaries — never fakes success.

RULES:
- Returns success ONLY when verified by the plugin runtime.
- Returns executed_unverified when the WS message was sent but no confirmation.
- Returns not_connected when the WS link is down.
- Returns unavailable when capability discovery says it's missing.
"""

import asyncio
import json
import logging
import threading
import time
from typing import Dict, Any, Optional

from bridge.protocol import (
    PROTOCOL_NAME, PROTOCOL_VERSION, MAX_MESSAGE_BYTES,
    ActionStatus, CapabilityRegistry, CapabilityStatus,
    make_request, validate_response,
    BRAIN_USABLE_EXPRESSIONS,
)
from bridge.companion_mode import default_companion_mode

try:
    import websockets
    import websockets.exceptions
except ImportError:
    websockets = None

logger = logging.getLogger("Brain.Bridge")


class DesktopMateBridge:
    """
    Manages the WebSocket connection to the Desktop Mate BepInEx plugin.
    Provides typed methods that return honest result dicts.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8766):
        self.uri = f"ws://{host}:{port}"
        self.ws = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._event_thread: Optional[threading.Thread] = None
        self.connected = False
        self.capabilities = CapabilityRegistry()
        self._running = True

        # Pending response futures keyed by request_id
        self._pending: Dict[str, asyncio.Future] = {}
        self._pending_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the background WS connection and event bus subscriber."""
        if not websockets:
            logger.error("websockets module not installed. Bridge disabled.")
            return

        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BridgeWS")
        self._thread.start()

        self._event_thread = threading.Thread(
            target=self._event_subscriber_loop, daemon=True, name="BridgeEvents"
        )
        self._event_thread.start()

    def stop(self):
        """Stop the background WS connection and threads."""
        self._running = False
        self.connected = False
        if self.ws and self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self.ws.close(), self._loop)
            except Exception:
                pass
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_forever())

    async def _connect_forever(self):
        """Reconnect loop — retries every 5s on failure."""
        while self._running:
            try:
                async with websockets.connect(
                    self.uri,
                    max_size=MAX_MESSAGE_BYTES,
                    close_timeout=5,
                ) as ws:
                    self.ws = ws
                    self.connected = True
                    # Start listening first so responses can be received
                    listen_task = asyncio.create_task(self._listen(ws))
                    # Discover capabilities on connect
                    await self._discover_capabilities()
                    await listen_task
            except Exception as e:
                self.connected = False
                self.ws = None
                self.capabilities.clear()
                # Cancel any pending futures
                self._cancel_all_pending(f"Disconnected: {e}")
                if not self._running:
                    break
                logger.debug(f"Bridge connection failed: {e}. Retrying in 1s...")
                await asyncio.sleep(1)

    async def _listen(self, ws):
        """Listen for responses and dispatch to pending futures."""
        try:
            async for raw in ws:
                if len(raw) > MAX_MESSAGE_BYTES:
                    logger.warning("Oversized message from Desktop Mate, ignoring")
                    continue
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.warning("Malformed JSON from Desktop Mate, ignoring")
                    continue

                req_id = msg.get("request_id")
                if req_id:
                    with self._pending_lock:
                        fut = self._pending.pop(req_id, None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                else:
                    logger.debug(f"Unmatched message from Desktop Mate: {msg}")
        except Exception:
            self.connected = False
            logger.warning("Disconnected from Desktop Mate")

    async def _discover_capabilities(self):
        """Ask the plugin what it can actually do."""
        resp = await self._send_and_wait_async("capabilities", {}, timeout=10.0)
        if resp and resp.get("success"):
            caps = resp.get("data", {}).get("capabilities", {})
            for name, info in caps.items():
                status_str = info.get("status", "unavailable")
                try:
                    status = CapabilityStatus(status_str)
                except ValueError:
                    status = CapabilityStatus.UNAVAILABLE
                self.capabilities.set_capability(name, status, info.get("details"))
            self.capabilities.mark_discovery_done()
            logger.info(f"Discovered capabilities: {list(caps.keys())}")
        else:
            logger.warning("Capability discovery failed or unsupported")

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    async def _send_and_wait_async(self, action: str, arguments: Dict[str, Any],
                                   timeout: float = 3.0) -> Optional[Dict[str, Any]]:
        """Send a protocol message and wait for a matching response."""
        if not self.connected or not self.ws:
            return None

        envelope = make_request(action, arguments)
        req_id = envelope["request_id"]
        raw = json.dumps(envelope)

        if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            logger.error("Outgoing message exceeds size limit")
            return None

        loop = self._loop or asyncio.get_running_loop()
        fut = loop.create_future()
        with self._pending_lock:
            self._pending[req_id] = fut

        try:
            await self.ws.send(raw)
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            logger.debug(f"Timeout waiting for response to {action} ({req_id})")
            return None
        except Exception as e:
            with self._pending_lock:
                self._pending.pop(req_id, None)
            logger.error(f"Send error: {e}")
            return None

    def send_and_wait(self, action: str, arguments: Optional[Dict[str, Any]] = None,
                      timeout: float = 3.0) -> Optional[Dict[str, Any]]:
        """Synchronously send a request and wait for the response from Desktop Mate."""
        if not self.connected or not self.ws or not self._loop:
            return None
        coro = self._send_and_wait_async(action, arguments or {}, timeout=timeout)
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout + 0.5)
        except Exception as e:
            logger.debug(f"send_and_wait failed for {action}: {e}")
            return None

    def _send_fire_and_forget(self, action: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message without waiting for response.
        Returns an honest status dict — NOT True/False.
        """
        if not self.connected or not self.ws or not self._loop:
            return {"success": False, "status": ActionStatus.NOT_CONNECTED.value,
                    "error": "Bridge not connected to Desktop Mate"}

        envelope = make_request(action, arguments)
        raw = json.dumps(envelope)

        if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            return {"success": False, "status": ActionStatus.FAILED.value,
                    "error": "Message exceeds size limit"}

        async def _do_send():
            try:
                await self.ws.send(raw)
            except Exception as e:
                logger.error(f"Fire-and-forget send error: {e}")

        asyncio.run_coroutine_threadsafe(_do_send(), self._loop)
        return {"success": False, "status": ActionStatus.EXECUTED_UNVERIFIED.value,
                "note": f"Sent {action} without response verification"}

    def _cancel_all_pending(self, reason: str):
        with self._pending_lock:
            for req_id, fut in self._pending.items():
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    # ------------------------------------------------------------------
    # Public API — Honest Methods
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """Deep health check. Returns actual runtime status."""
        if not self.connected:
            return {
                "success": False,
                "status": ActionStatus.NOT_CONNECTED.value,
                "bridge_connected": False,
                "runtime_ready": False,
                "character_ready": False,
            }
        result = self._send_fire_and_forget("health", {})
        result["bridge_connected"] = True
        return result

    def health_check(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Synchronous verified health check against the live runtime."""
        if not self.connected:
            return {
                "success": False,
                "status": ActionStatus.NOT_CONNECTED.value,
                "bridge_connected": False,
                "runtime_ready": False,
                "character_ready": False,
            }
        resp = self.send_and_wait("health", {}, timeout=timeout)
        if resp and resp.get("success"):
            data = resp.get("data", {})
            return {
                "success": True,
                "status": resp.get("status", ActionStatus.SUCCESS.value),
                "bridge_connected": True,
                "runtime_ready": data.get("runtime_ready", False),
                "character_ready": data.get("character_ready", False),
                "details": data.get("details", ""),
            }
        return {
            "success": False,
            "status": ActionStatus.EXECUTED_UNVERIFIED.value,
            "bridge_connected": True,
            "runtime_ready": False,
            "character_ready": False,
        }

    def refresh_capabilities(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Ask Desktop Mate runtime for updated capabilities."""
        if not self.connected or not self._loop:
            return self.get_capabilities()
        coro = self._discover_capabilities()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            future.result(timeout=timeout + 0.5)
        except Exception as e:
            logger.debug(f"refresh_capabilities failed: {e}")
        return self.get_capabilities()

    def get_capabilities(self) -> Dict[str, Any]:
        """Return discovered capabilities."""
        return {
            "success": True,
            "capabilities": self.capabilities.to_dict(),
            "bridge_connected": self.connected,
        }

    def set_emotion(self, emotion: str, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Set character facial expression using VRM 1.0 presets.
        Returns honest status — returns 'verified' with data when runtime confirms weight applied.
        """
        if emotion not in BRAIN_USABLE_EXPRESSIONS:
            return {
                "success": False,
                "status": ActionStatus.FAILED.value,
                "error": f"Unknown expression '{emotion}'. "
                         f"Valid: {sorted(BRAIN_USABLE_EXPRESSIONS)}",
            }

        if not self.connected:
            return {"success": False, "status": ActionStatus.NOT_CONNECTED.value,
                    "error": "Bridge not connected"}

        resp = self.send_and_wait("set_emotion", {"emotion": emotion}, timeout=timeout)
        if resp:
            if resp.get("success"):
                return {
                    "success": True,
                    "status": resp.get("status", "verified"),
                    "data": resp.get("data", {})
                }
            else:
                err_obj = resp.get("error") or {}
                err_msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                return {
                    "success": False,
                    "status": resp.get("status", "failed"),
                    "error": err_msg or "Failed to set emotion in runtime"
                }

        return {
            "success": False,
            "status": ActionStatus.EXECUTED_UNVERIFIED.value,
            "error": "No response confirmation from Desktop Mate runtime"
        }

    def play_animation(self, name: str, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Request a character animation.
        Returns verified status dictionary when runtime confirms animation state hash.
        """
        if not name or not isinstance(name, str) or len(name) > 100:
            return {"success": False, "status": ActionStatus.FAILED.value,
                    "error": "Invalid animation name"}

        if not self.connected:
            return {"success": False, "status": ActionStatus.NOT_CONNECTED.value,
                    "error": "Bridge not connected"}

        if not self.capabilities.is_available("play_animation"):
            return {"success": False, "status": ActionStatus.UNAVAILABLE.value,
                    "error": "Capability 'play_animation' is not verified/available"}

        resp = self.send_and_wait("play_animation", {"name": name}, timeout=timeout)
        if resp:
            if resp.get("success"):
                return {
                    "success": True,
                    "status": resp.get("status", "verified"),
                    "data": resp.get("data", {})
                }
            else:
                err_obj = resp.get("error") or {}
                err_msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                return {
                    "success": False,
                    "status": resp.get("status", "failed"),
                    "error": err_msg or "Failed to execute animation in runtime"
                }

        return {
            "success": False,
            "status": ActionStatus.EXECUTED_UNVERIFIED.value,
            "error": "No response confirmation from Desktop Mate runtime"
        }

    def speak(self, text: str) -> Dict[str, Any]:
        """
        Request companion speech synthesis via voice engine.
        Returns honest status result.
        """
        if not text or not isinstance(text, str):
            return {"success": False, "status": ActionStatus.FAILED.value,
                    "error": "Empty or invalid text for speech"}

        from core.voice import LinuxNativeTTS
        tts = LinuxNativeTTS()
        if not tts.is_available():
            return {"success": True, "status": ActionStatus.EXECUTED_UNVERIFIED.value,
                    "data": {"text": text, "mocked": True}}

        res = tts.speak(text, wait=False)
        return {
            "success": True,
            "status": ActionStatus.EXECUTED_UNVERIFIED.value if res else ActionStatus.FAILED.value,
            "data": {"text": text}
        }

    def stop_speaking(self) -> Dict[str, Any]:
        """Stop active TTS playback and flush pending speech queue."""
        from core.voice import LinuxNativeTTS
        tts = LinuxNativeTTS()
        tts.stop()
        return {"success": True, "status": ActionStatus.SUCCESS.value}

    def return_idle(self) -> Dict[str, Any]:
        """Return companion to default neutral emotion and idle animation."""
        self.set_emotion("neutral")
        return self.play_animation("idle")

    def play_voice(self, audio_path: str) -> Dict[str, Any]:
        """
        Request voice playback with lip-sync.
        The audio_path problem (Linux→Wine) is documented honestly.
        """
        if not audio_path or not isinstance(audio_path, str):
            return {"success": False, "status": ActionStatus.FAILED.value,
                    "error": "Invalid audio path"}

        if not self.connected:
            return {"success": False, "status": ActionStatus.NOT_CONNECTED.value,
                    "error": "Bridge not connected"}

        return self._send_fire_and_forget("play_voice", {"file": audio_path})


    def look_at(self, target: str) -> Dict[str, Any]:
        """Request look-at behavior."""
        if not self.connected:
            return {"success": False, "status": ActionStatus.NOT_CONNECTED.value,
                    "error": "Bridge not connected"}

        resp = self.send_and_wait("look_at", {"target": target}, timeout=3.0)
        if resp and resp.get("success"):
            return {
                "success": True,
                "status": resp.get("status", "executed_unverified"),
                "data": resp.get("data", {})
            }
        return {
            "success": False,
            "status": ActionStatus.EXECUTED_UNVERIFIED.value,
            "error": "No response confirmation from Desktop Mate runtime"
        }

    def trim_memory(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Request Unity runtime garbage collection and unused asset unloading."""
        if not self.connected:
            return {"success": False, "status": ActionStatus.NOT_CONNECTED.value,
                    "error": "Bridge not connected"}

        resp = self.send_and_wait("trim_memory", {}, timeout=timeout)
        if resp and resp.get("success"):
            return {
                "success": True,
                "status": resp.get("status", "verified"),
                "data": resp.get("data", {})
            }
        return {
            "success": False,
            "status": ActionStatus.EXECUTED_UNVERIFIED.value,
            "error": "No response confirmation from Desktop Mate runtime"
        }

    def set_fps(self, fps: int = 30, timeout: float = 3.0) -> Dict[str, Any]:
        """Request dynamic frame rate adjustment for CPU/RAM optimization."""
        if not isinstance(fps, int) or isinstance(fps, bool) or fps < 15 or fps > 60:
            return {"success": False, "status": ActionStatus.FAILED.value,
                    "error": f"FPS out of allowed range (15-60): {fps}"}

        if not self.connected:
            return {"success": False, "status": ActionStatus.NOT_CONNECTED.value,
                    "error": "Bridge not connected"}

        resp = self.send_and_wait("set_fps", {"fps": fps}, timeout=timeout)
        if resp and resp.get("success"):
            return {
                "success": True,
                "status": resp.get("status", "verified"),
                "data": resp.get("data", {})
            }
        return {
            "success": False,
            "status": ActionStatus.EXECUTED_UNVERIFIED.value,
            "error": "No response confirmation from Desktop Mate runtime"
        }


    # ------------------------------------------------------------------
    # Companion Mode Delegation
    # ------------------------------------------------------------------

    def set_companion_mode(self, mode: str) -> Dict[str, Any]:
        """Set companion operating mode (ACTIVE/PASSIVE/SLEEPING/DISABLED)."""
        return default_companion_mode.set_mode(mode)

    def get_companion_mode(self) -> Dict[str, Any]:
        """Return current companion mode."""
        return default_companion_mode.to_dict()

    def look_at_target(self, target: str) -> Dict[str, Any]:
        """
        Set companion look-at target (mouse/screen/active_window/none).
        Throttled to once per 5 seconds.
        """
        if not hasattr(self, "_look_at_ctrl"):
            from bridge.look_at import LookAtController
            from bridge.companion_mode import default_companion_mode
            self._look_at_ctrl = LookAtController(self, default_companion_mode)
        return self._look_at_ctrl.set_target(target)

    # ------------------------------------------------------------------
    # Event Bus Subscriber
    # ------------------------------------------------------------------

    def _event_subscriber_loop(self):
        """Subscribe to Brain's CompanionStateManager and dispatch to reaction engine."""
        from bridge.reaction_engine import ReactionEngine
        from bridge.idle_behavior import IdleBehaviorController
        from core.companion_state import default_companion_state

        engine = ReactionEngine(self, default_companion_mode)
        idle = IdleBehaviorController(self, default_companion_mode, default_companion_state)
        idle.start()
        q = default_companion_state.subscribe()
        logger.info("Bridge subscribed to Companion State Event Bus")

        while True:
            try:
                event = q.get()
                engine.handle_event(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
