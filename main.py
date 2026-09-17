#!/usr/bin/env python3
"""
sApkAnalyzer - Android Logcat & Crash Analyzer
Runs cross-platform on macOS and Windows without requiring any build or compilation.
"""

import argparse
import os
import socket
import sys
import time
import webbrowser

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.server import AppState, create_handler, ThreadedHTTPServer


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


def find_available_port(start_port: int = 8765, host: str = "127.0.0.1") -> int:
    port = start_port
    while port < start_port + 100:
        if not is_port_in_use(port, host):
            return port
        port += 1
    return start_port


def main():
    parser = argparse.ArgumentParser(
        description="sApkAnalyzer - Real-time Android Logcat & Crash Analyzer"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to run the web server on (default: 8765)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open browser automatically",
    )
    parser.add_argument(
        "--adb",
        type=str,
        default=None,
        help="Path to custom adb executable",
    )

    args = parser.parse_args()

    port = find_available_port(args.port, args.host)
    frontend_dir = os.path.join(PROJECT_ROOT, "frontend")

    state = AppState(frontend_dir=frontend_dir, custom_adb=args.adb)
    handler_class = create_handler(state)

    print("=" * 60)
    print(" 🚀 sApkAnalyzer - Android Logcat & Crash Analyzer")
    print("=" * 60)
    print(f" • ADB Path   : {state.adb.adb_path}")
    print(f" • Web Server : http://{args.host}:{port}")
    print("=" * 60)

    devices = state.adb.get_devices()
    if devices:
        active = [d for d in devices if d['status'] == 'device']
        print(f" 📱 Discovered Devices: {len(devices)} (Active: {len(active)})")
        for d in devices:
            print(f"    - [{d['status'].upper()}] {d['serial']} ({d['model']})")
        if state.adb.selected_device:
            print(f" 🎯 Selected Device: {state.adb.selected_device}")
    else:
        print(" ⚠️  No devices found. Please enable USB debugging and connect your device.")
    print("=" * 60)

    server = ThreadedHTTPServer((args.host, port), handler_class)

    url = f"http://{args.host}:{port}"

    if not args.no_browser:
        def open_browser():
            time.sleep(0.5)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        import threading
        threading.Thread(target=open_browser, daemon=True).start()

    print(f"\nApp is ready! Open in your browser: {url}")
    print("Press Ctrl + C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        state.adb.stop_streaming()
        server.server_close()
        print("sApkAnalyzer stopped.")


if __name__ == "__main__":
    main()
