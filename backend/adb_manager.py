"""
ADB Manager for sApkAnalyzer.
Handles ADB path discovery, device management, Wi-Fi connections,
installed package enumeration, PID-to-package resolution, and real-time logcat streaming.
"""

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import List, Dict, Optional, Callable, Any


class AdbManager:
    def __init__(self, custom_adb_path: Optional[str] = None):
        self.adb_path = custom_adb_path or self._find_adb()
        self.selected_device: Optional[str] = None
        self._logcat_process: Optional[subprocess.Popen] = None
        self._logcat_thread: Optional[threading.Thread] = None
        self._pid_poll_thread: Optional[threading.Thread] = None
        self._is_streaming = False
        self._pid_to_package: Dict[int, str] = {}
        self._package_to_pids: Dict[str, List[int]] = {}
        self._lock = threading.Lock()
        self._subscribers: List[Callable[[str], None]] = []

    def _find_adb(self) -> str:
        """Locates the adb binary across macOS, Windows, and Linux."""
        found = shutil.which("adb")
        if found:
            return found

        home = os.path.expanduser("~")
        candidates = []

        if sys.platform == "darwin":  # macOS
            candidates = [
                "/opt/homebrew/bin/adb",
                "/usr/local/bin/adb",
                os.path.join(home, "Library/Android/sdk/platform-tools/adb"),
            ]
        elif sys.platform == "win32":  # Windows
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            prog_files = os.environ.get("ProgramFiles", "")
            prog_files_x86 = os.environ.get("ProgramFiles(x86)", "")
            candidates = [
                os.path.join(local_appdata, "Android", "Sdk", "platform-tools", "adb.exe"),
                os.path.join(prog_files, "Android", "platform-tools", "adb.exe"),
                os.path.join(prog_files_x86, "Android", "platform-tools", "adb.exe"),
            ]
        else:  # Linux
            candidates = [
                "/usr/bin/adb",
                "/usr/local/bin/adb",
                os.path.join(home, "Android/Sdk/platform-tools/adb"),
            ]

        for path in candidates:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        return "adb"  # Default fallback to PATH

    def run_cmd(self, args: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
        """Runs an adb command with the configured adb binary."""
        cmd = [self.adb_path] + args
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Command timed out")
        except Exception as e:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=str(e))

    def get_devices(self) -> List[Dict[str, Any]]:
        """
        Enumerates connected Android devices and emulators.
        Parses output of 'adb devices -l'.
        """
        proc = self.run_cmd(["devices", "-l"])
        devices = []
        if proc.returncode != 0:
            return devices

        lines = proc.stdout.strip().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue

            # Format: <serial>  <status>  [usb:...] [product:...] [model:...] [device:...]
            parts = line.split()
            if len(parts) < 2:
                continue

            serial = parts[0]
            status = parts[1]

            model = "Android Device"
            product = ""
            for item in parts[2:]:
                if item.startswith("model:"):
                    model = item.split(":", 1)[1].replace("_", " ")
                elif item.startswith("product:"):
                    product = item.split(":", 1)[1]

            is_wifi = ":" in serial
            is_emulator = serial.startswith("emulator-")

            devices.append({
                "serial": serial,
                "status": status,
                "model": model,
                "product": product,
                "is_wifi": is_wifi,
                "is_emulator": is_emulator,
            })

        # Auto-select the first active device if current selection is invalid
        active_serials = [d["serial"] for d in devices if d["status"] == "device"]
        if self.selected_device not in active_serials:
            self.selected_device = active_serials[0] if active_serials else None

        return devices

    def connect_wifi(self, address: str) -> Dict[str, Any]:
        """Connects to a device via Wi-Fi ADB (e.g. 192.168.1.100:5555)."""
        proc = self.run_cmd(["connect", address], timeout=15)
        success = "connected to" in proc.stdout.lower()
        return {
            "success": success,
            "message": proc.stdout.strip() or proc.stderr.strip(),
        }

    def disconnect_wifi(self, address: str) -> Dict[str, Any]:
        """Disconnects a Wi-Fi device."""
        proc = self.run_cmd(["disconnect", address])
        return {
            "success": proc.returncode == 0,
            "message": proc.stdout.strip() or proc.stderr.strip(),
        }

    def get_installed_packages(self, third_party_only: bool = True) -> List[Dict[str, str]]:
        """
        Retrieves installed packages from the selected device.
        Defaults to third-party user apps and games (-3).
        """
        if not self.selected_device:
            return []

        args = ["-s", self.selected_device, "shell", "pm", "list", "packages"]
        if third_party_only:
            args.append("-3")

        proc = self.run_cmd(args, timeout=15)
        if proc.returncode != 0:
            return []

        packages = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkg_name = line.split(":", 1)[1].strip()
                # Friendly display name
                simple_name = pkg_name.split(".")[-1].capitalize()
                packages.append({
                    "package": pkg_name,
                    "name": simple_name,
                })

        # Sort alphabetically by simple name
        packages.sort(key=lambda x: x["package"])
        return packages

    def update_running_processes(self) -> Dict[int, str]:
        """
        Updates the PID-to-package mapping for the selected device.
        Uses 'ps -A -o PID,NAME' or fallback 'ps'.
        """
        if not self.selected_device:
            return {}

        proc = self.run_cmd(
            ["-s", self.selected_device, "shell", "ps", "-A", "-o", "PID,NAME"],
            timeout=5,
        )

        mapping: Dict[int, str] = {}
        pkg_pids: Dict[str, List[int]] = {}

        if proc.returncode == 0 and proc.stdout.strip():
            lines = proc.stdout.splitlines()
            for line in lines[1:]:  # Skip header
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    pid_s, name = parts
                    if pid_s.isdigit():
                        pid = int(pid_s)
                        name_clean = name.strip()
                        mapping[pid] = name_clean
                        pkg_pids.setdefault(name_clean, []).append(pid)
        else:
            # Fallback to standard ps
            fallback_proc = self.run_cmd(["-s", self.selected_device, "shell", "ps"], timeout=5)
            if fallback_proc.returncode == 0:
                for line in fallback_proc.stdout.splitlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 9 and parts[1].isdigit():
                        pid = int(parts[1])
                        name_clean = parts[-1].strip()
                        mapping[pid] = name_clean
                        pkg_pids.setdefault(name_clean, []).append(pid)

        with self._lock:
            self._pid_to_package = mapping
            self._package_to_pids = pkg_pids

        return mapping

    def get_pid_mapping(self) -> Dict[int, str]:
        """Returns a snapshot of the current PID-to-package mapping."""
        with self._lock:
            return dict(self._pid_to_package)

    def get_package_pids(self, package_name: str) -> List[int]:
        """Returns the list of active PIDs for a given package."""
        with self._lock:
            return list(self._package_to_pids.get(package_name, []))

    def clear_device_logcat(self) -> bool:
        """Clears the logcat buffer on the selected device."""
        if not self.selected_device:
            return False
        proc = self.run_cmd(["-s", self.selected_device, "logcat", "-c"])
        return proc.returncode == 0

    def start_streaming(self, on_line_callback: Callable[[str], None]):
        """Starts real-time logcat streaming in a background thread."""
        self.stop_streaming()

        if not self.selected_device:
            return

        self._subscribers.append(on_line_callback)
        self._is_streaming = True

        # Start PID poller to track newly launched games/apps
        self._pid_poll_thread = threading.Thread(target=self._pid_poll_worker, daemon=True)
        self._pid_poll_thread.start()

        # Start logcat reader thread
        self._logcat_thread = threading.Thread(target=self._logcat_worker, daemon=True)
        self._logcat_thread.start()

    def stop_streaming(self):
        """Stops the active logcat streaming and child processes."""
        self._is_streaming = False
        if self._logcat_process:
            try:
                self._logcat_process.terminate()
                self._logcat_process.wait(timeout=2)
            except Exception:
                try:
                    self._logcat_process.kill()
                except Exception:
                    pass
            self._logcat_process = None

        self._subscribers.clear()

    def _pid_poll_worker(self):
        """Periodically refreshes PID-to-package mapping while streaming."""
        while self._is_streaming and self.selected_device:
            try:
                self.update_running_processes()
            except Exception:
                pass
            time.sleep(3.0)

    def _logcat_worker(self):
        """Executes 'adb logcat -v threadtime' and reads lines continuously."""
        cmd = [self.adb_path, "-s", self.selected_device, "logcat", "-v", "threadtime"]
        try:
            self._logcat_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,  # Line-buffered
            )

            for line in iter(self._logcat_process.stdout.readline, ""):
                if not self._is_streaming:
                    break
                if line:
                    for sub in list(self._subscribers):
                        try:
                            sub(line)
                        except Exception:
                            pass

        except Exception as e:
            err_line = f"00-00 00:00:00.000     0     0 E sApkAnalyzer: Logcat error: {e}"
            for sub in list(self._subscribers):
                try:
                    sub(err_line)
                except Exception:
                    pass
        finally:
            self._is_streaming = False
