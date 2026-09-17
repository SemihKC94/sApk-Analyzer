<div align="center">

# ⚡ sApkAnalyzer

**Real-time Android Logcat & Crash Analyzer for Developers and QA Engineers**

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)](#)
[![Zero Build](https://img.shields.io/badge/dependencies-0%20(Pure%20Standard%20Lib)-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*A zero-build, cross-platform desktop web tool to inspect, filter, and analyze real-time Android logcat streams with automated application PID mapping and crash stack trace diagnostics.*

</div>

---

## 🌟 Highlights

- 🚀 **Zero Build & Zero Dependencies**: Runs directly with Python's standard library. No `pip install`, `npm build`, or native compiler setup required.
- 📱 **Smart App & Game Filtering**: Automatically detects installed third-party apps and games (`pm list packages -3`) and dynamically maps running process IDs (`ps -A`). Even if the game crashes or restarts, log filtering continues uninterrupted.
- 💥 **Dedicated Crash & Fatal Exception Analyzer**: Instantly flags `FATAL EXCEPTION`, `NullPointerException`, `SIGSEGV`, `ANR`, and Unity/Unreal Engine errors with a live crash counter and one-click stack trace inspection.
- ⚡ **High-Density Telemetry Stream**: Monospaced, high-performance log table built on Server-Sent Events (SSE) with micro-batching to ensure smooth 60fps streaming without browser lag.
- 🎨 **Terminal Slate Design**: Eye-friendly, minimalist dark theme inspired by modern observability platforms (Linear, Datadog, Raycast) designed for long debugging sessions.
- 🔍 **Omnibar Search**: Real-time log search supporting regular expressions (`.*`), case-sensitivity toggles (`Aa`), and inverted matching.
- 📶 **Wi-Fi ADB Integration**: Connect and disconnect wireless debugging sessions directly from the UI.
- 💾 **Instant Export**: Export filtered or raw logs to `.txt` or structured `.json` with one click.

---

## 📋 Prerequisites

1. **Python 3.8+** (Pre-installed on macOS/Linux or downloadable from [python.org](https://www.python.org/))
2. **Android Debug Bridge (`adb`)**:
   - macOS: `brew install android-platform-tools`
   - Windows: Included with Android Studio or standalone Platform Tools.
3. **Android Device or Emulator** with **USB Debugging** enabled.

---

## 🚀 Quick Start

### macOS & Linux
```bash
./run.sh
# or
python3 main.py
```

### Windows
Double-click `run.bat` or run in Command Prompt / PowerShell:
```cmd
run.bat
```

> **Note**: Upon launch, sApkAnalyzer automatically detects `adb`, scans for connected devices, and opens `http://127.0.0.1:8765` in your default browser.

---

## ⚙️ Command-Line Arguments

You can customize the server port, host binding, or specify a custom `adb` path:

```bash
python3 main.py --help
```

| Argument | Type | Default | Description |
|---|---|---|---|
| `--port` | `int` | `8765` | Web server port (auto-increments if port is busy) |
| `--host` | `str` | `127.0.0.1` | Host interface to bind |
| `--no-browser` | `flag` | `False` | Start without automatically launching the browser |
| `--adb` | `str` | `None` | Path to custom `adb` binary executable |

---

## 📐 Project Architecture

```
sApkAnalyzer/
├── main.py                     # CLI launcher & server initiator
├── run.sh                      # One-click script for macOS & Linux
├── run.bat                     # One-click script for Windows
├── requirements.txt            # Zero external dependencies notice
├── .gitignore                  # Git exclusions for Python/OS/IDE
├── LICENSE                     # MIT License
├── backend/
│   ├── __init__.py
│   ├── adb_manager.py          # ADB execution, device discovery, PID tracking & logcat stream
│   ├── log_parser.py           # Threadtime parser & crash detection engine
│   └── server.py               # Zero-dependency multi-threaded HTTP + SSE server
├── frontend/
│   ├── index.html              # Modern Terminal Slate UI
│   └── js/
│       └── app.js              # SSE client, real-time filters & inspector drawer controller
└── tests/
    ├── test_adb_manager.py     # Unit tests for device & package parsing
    ├── test_log_parser.py      # Unit tests for log parsing & crash recognition
    └── test_server.py          # Unit tests for LogHub buffer & event queues
```

---

## 📡 REST API & SSE Endpoints

sApkAnalyzer exposes a lightweight REST API for automation and custom integrations:

- `GET /api/devices`: Returns connected devices, status, and active selection.
- `POST /api/device/select`: Switches active device (`{"serial": "emulator-5554"}`).
- `GET /api/packages`: Returns installed apps, package names, and running PIDs.
- `GET /api/stream`: Real-time Server-Sent Events (SSE) logcat stream.
- `POST /api/logs/clear`: Clears in-memory buffer and device logcat buffer (`adb logcat -c`).
- `POST /api/adb/connect`: Connects to wireless device (`{"address": "192.168.1.50:5555"}`).
- `POST /api/adb/disconnect`: Disconnects wireless device (`{"address": "192.168.1.50:5555"}`).

---

## 🧪 Running Unit Tests

To run the complete test suite:

```bash
python3 -m unittest discover tests/
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
