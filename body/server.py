"""
Brain Desktop Companion Avatar Server (Phase 19 Companion Evolution).
Lightweight HTTP/SSE server streaming live Brain agent states (IDLE, THINKING,
SEARCHING, WORKING, BROWSING, ERROR, SUCCESS, SPEAKING) to the desktop avatar window.
"""

import os
import json
import time
import threading
from queue import Empty
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from typing import Dict, Any, Optional

from core.companion_state import default_companion_state
from core.config import default_config

BODY_DIR = os.path.dirname(os.path.abspath(__file__))


def set_companion_state(state: str, status_text: str = "", action: Optional[str] = None, result: Optional[str] = None):
    """Thread-safe update of live companion avatar state."""
    return default_companion_state.set_state(
        activity=state,
        status_text=status_text,
        action=action,
        result=result
    )


def get_companion_state() -> Dict[str, Any]:
    """Returns a snapshot of the current unified companion state."""
    return default_companion_state.get_state()


class CompanionHTTPHandler(SimpleHTTPRequestHandler):
    """Custom request handler serving avatar static assets and live state/event APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BODY_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        # 1. State Snapshot API
        if parsed.path == "/api/state":
            state_data = get_companion_state()
            payload = json.dumps(state_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
            return

        # 2. Server-Sent Events (SSE) Live Stream
        if parsed.path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            # Emit initial full state snapshot
            init_payload = json.dumps({"type": "STATE_CHANGE", "data": get_companion_state()})
            try:
                self.wfile.write(f"data: {init_payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            except Exception:
                return

            sub_queue = default_companion_state.subscribe()
            try:
                while True:
                    try:
                        msg = sub_queue.get(timeout=15.0)
                        from core.companion_state import CompanionEvent
                        if isinstance(msg, CompanionEvent):
                            if isinstance(msg.data, dict):
                                payload = json.dumps({"type": msg.event_type, **msg.data})
                            else:
                                payload = json.dumps({"type": msg.event_type, "data": msg.data})
                        elif isinstance(msg, str):
                            payload = msg
                        else:
                            payload = json.dumps(msg)
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except Empty:
                        # Keep-alive heartbeat comment
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                default_companion_state.unsubscribe(sub_queue)
            return

        # 3. Settings / Config API
        if parsed.path == "/api/config":
            cfg_data = default_config.get("avatar")
            payload = json.dumps(cfg_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
            return

        # 4. Companion status API (DM process, mode, memory, bridge)
        if parsed.path == "/api/companion":
            try:
                from core.desktop_presence import DesktopPresenceManager
                from bridge.companion_mode import default_companion_mode
                mgr = DesktopPresenceManager()
                proc = mgr.is_process_running()
                rss = mgr.get_memory_usage_mb() if proc else 0.0
                companion_data = {
                    "process_running": proc,
                    "rss_memory_mb": rss,
                    "companion_mode": default_companion_mode.get_mode(),
                }
            except Exception as e:
                companion_data = {"error": str(e)}
            payload = json.dumps(companion_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/command":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(post_body)
                cmd_text = data.get("command", "").strip()
                if cmd_text:
                    set_companion_state("THINKING", f"Processing: {cmd_text[:25]}...")
                    # Run via Brain planner
                    from brain import run_planner_task
                    set_companion_state("WORKING", "Executing action...")
                    res = run_planner_task(cmd_text)
                    set_companion_state("SUCCESS", "Task finished", result=res[:60])
                    # Reset to IDLE after 4 seconds
                    threading.Timer(4.0, lambda: set_companion_state("IDLE", "Standing by")).start()
                    resp_payload = json.dumps({"success": True, "result": res}).encode("utf-8")
                else:
                    resp_payload = json.dumps({"success": False, "error": "Empty command"}).encode("utf-8")
            except Exception as e:
                set_companion_state("ERROR", str(e)[:30])
                resp_payload = json.dumps({"success": False, "error": str(e)}).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp_payload)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress noisy HTTP request logging


def start_companion_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Starts companion server in background thread."""
    server = ThreadingHTTPServer((host, port), CompanionHTTPHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


def launch_companion_window(host: str = "127.0.0.1", port: int = 8765):
    """Launches chromeless desktop window using Brave app mode."""
    url = f"http://{host}:{port}/"
    import subprocess
    cmd = [
        "brave-browser",
        f"--app={url}",
        "--window-size=320,440",
        "--window-position=1580,580"
    ]
    try:
        subprocess.Popen(cmd)
    except Exception:
        pass


if __name__ == "__main__":
    print("Starting Brain Companion Server on http://127.0.0.1:8765...")
    srv = start_companion_server()
    launch_companion_window()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping Companion Server.")
        srv.shutdown()
