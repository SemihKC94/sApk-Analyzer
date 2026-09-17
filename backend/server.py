"""
Lightweight, Zero-Dependency HTTP & Real-time SSE Server for sApkAnalyzer.
Serves frontend static assets and exposes REST API + SSE stream for logcat.
"""

import json
import mimetypes
import os
import queue
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs

from backend.adb_manager import AdbManager
from backend.log_parser import LogParser, LogEntry


class LogHub:
    """Central hub for accumulating logs, managing buffers, and dispatching to SSE clients."""

    def __init__(self, max_buffer_size: int = 10000):
        self.max_buffer_size = max_buffer_size
        self._buffer: List[Dict[str, Any]] = []
        self._clients: List[queue.Queue] = []
        self._lock = threading.Lock()

    def add_entry(self, entry: LogEntry):
        data = entry.to_dict()
        with self._lock:
            self._buffer.append(data)
            if len(self._buffer) > self.max_buffer_size:
                self._buffer.pop(0)

            for client_q in list(self._clients):
                try:
                    client_q.put_nowait(data)
                except queue.Full:
                    pass

    def get_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._buffer[-limit:])

    def clear(self):
        with self._lock:
            self._buffer.clear()

    def register_client(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=2000)
        with self._lock:
            self._clients.append(q)
        return q

    def unregister_client(self, q: queue.Queue):
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)


class AppState:
    """Global shared state accessible by HTTP request handlers."""

    def __init__(self, frontend_dir: str, custom_adb: Optional[str] = None):
        self.frontend_dir = frontend_dir
        self.adb = AdbManager(custom_adb)
        self.parser = LogParser()
        self.hub = LogHub()
        self._streaming_active = False

    def on_raw_log_line(self, raw_line: str):
        pid_map = self.adb.get_pid_mapping()
        entry = self.parser.parse_line(raw_line, pid_to_package=pid_map)
        self.hub.add_entry(entry)

    def ensure_streaming(self):
        if not self._streaming_active and self.adb.selected_device:
            self.adb.start_streaming(self.on_raw_log_line)
            self._streaming_active = True

    def switch_device(self, serial: str):
        self.adb.stop_streaming()
        self._streaming_active = False
        self.adb.selected_device = serial
        self.parser.reset()
        self.hub.clear()
        self.ensure_streaming()


def create_handler(state: AppState):
    class ApkAnalyzerHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Suppress default stdout log spam for each static file request
            pass

        def _send_json(self, status: int, data: Any):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: int, message: str):
            self._send_json(status, {"error": message})

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/devices":
                devices = state.adb.get_devices()
                state.ensure_streaming()
                self._send_json(200, {
                    "devices": devices,
                    "selected": state.adb.selected_device,
                })
                return

            if path == "/api/packages":
                query = parse_qs(parsed.query)
                third_party = query.get("all", ["false"])[0].lower() != "true"
                packages = state.adb.get_installed_packages(third_party_only=third_party)
                pid_map = state.adb.get_pid_mapping()

                # Mark running apps
                for pkg in packages:
                    pkg_name = pkg["package"]
                    pkg["pids"] = state.adb.get_package_pids(pkg_name)
                    pkg["is_running"] = len(pkg["pids"]) > 0

                self._send_json(200, {
                    "packages": packages,
                    "running_count": sum(1 for p in packages if p["is_running"]),
                })
                return

            if path == "/api/logs/history":
                history = state.hub.get_history(limit=500)
                self._send_json(200, {"logs": history})
                return

            if path == "/api/stream":
                # Server-Sent Events (SSE)
                state.ensure_streaming()
                client_q = state.hub.register_client()

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                try:
                    # Flush initial history
                    initial_logs = state.hub.get_history(limit=100)
                    if initial_logs:
                        payload = f"data: {json.dumps({'batch': initial_logs})}\n\n"
                        self.wfile.write(payload.encode("utf-8"))
                        self.wfile.flush()

                    # Stream real-time logs in micro-batches
                    while True:
                        batch = []
                        # Wait for at least one log
                        try:
                            item = client_q.get(timeout=1.0)
                            batch.append(item)
                        except queue.Empty:
                            # Send heartbeat comment to keep connection alive
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                            continue

                        # Drain additional queued logs up to 100 per batch
                        while len(batch) < 100:
                            try:
                                batch.append(client_q.get_nowait())
                            except queue.Empty:
                                break

                        payload = f"data: {json.dumps({'batch': batch})}\n\n"
                        self.wfile.write(payload.encode("utf-8"))
                        self.wfile.flush()

                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    state.hub.unregister_client(client_q)
                return

            # Static File Serving
            self._serve_static(path)

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(length) if length > 0 else b""
            body = {}
            if body_bytes:
                try:
                    body = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    pass

            if path == "/api/device/select":
                serial = body.get("serial")
                if not serial:
                    self._send_error(400, "Device serial is required")
                    return
                state.switch_device(serial)
                self._send_json(200, {"success": True, "selected": serial})
                return

            if path == "/api/logs/clear":
                state.hub.clear()
                state.parser.reset()
                device_cleared = state.adb.clear_device_logcat()
                self._send_json(200, {"success": True, "device_cleared": device_cleared})
                return

            if path == "/api/adb/connect":
                address = body.get("address", "").strip()
                if not address:
                    self._send_error(400, "Wi-Fi address is required (e.g. 192.168.1.50:5555)")
                    return
                res = state.adb.connect_wifi(address)
                self._send_json(200, res)
                return

            if path == "/api/adb/disconnect":
                address = body.get("address", "").strip()
                if not address:
                    self._send_error(400, "Address is required")
                    return
                res = state.adb.disconnect_wifi(address)
                self._send_json(200, res)
                return

            self._send_error(404, "Endpoint not found")

        def _serve_static(self, req_path: str):
            clean_path = req_path.lstrip("/")
            if not clean_path or clean_path == "":
                clean_path = "index.html"

            file_path = os.path.join(state.frontend_dir, clean_path)
            real_file_path = os.path.realpath(file_path)
            real_frontend_dir = os.path.realpath(state.frontend_dir)

            # Path traversal prevention
            if not real_file_path.startswith(real_frontend_dir) or not os.path.isfile(real_file_path):
                # Fallback to index.html for SPA routes
                real_file_path = os.path.join(real_frontend_dir, "index.html")
                if not os.path.isfile(real_file_path):
                    self.send_error(404, "File Not Found")
                    return

            mime_type, _ = mimetypes.guess_type(real_file_path)
            mime_type = mime_type or "application/octet-stream"

            try:
                with open(real_file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error reading file: {e}")

    return ApkAnalyzerHandler


class ThreadedHTTPServer(HTTPServer):
    """Multi-threaded HTTP server to handle simultaneous SSE connections and REST calls."""
    daemon_threads = True

    def process_request(self, request, client_address):
        t = threading.Thread(target=self.process_request_thread, args=(request, client_address))
        t.daemon = True
        t.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)
