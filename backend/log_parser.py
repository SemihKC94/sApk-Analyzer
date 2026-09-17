"""
Logcat Parser and Crash Detection Engine for sApkAnalyzer.
Parses standard Android logcat formats (threadtime, brief) and detects crash/error patterns.
"""

import re
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

LOGCAT_THREADTIME_PATTERN = re.compile(
    r"^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEFA])\s+([^:]*?)\s*:\s*(.*)$"
)

# Alternative brief format: "I/Tag( 1234): message"
LOGCAT_BRIEF_PATTERN = re.compile(
    r"^([VDIWEFA])/([^(]+)\(\s*(\d+)\):\s*(.*)$"
)

LEVEL_MAP = {
    "V": "VERBOSE",
    "D": "DEBUG",
    "I": "INFO",
    "W": "WARNING",
    "E": "ERROR",
    "F": "FATAL",
    "A": "ASSERT",
}

LEVEL_SEVERITY = {
    "V": 1,
    "D": 2,
    "I": 3,
    "W": 4,
    "E": 5,
    "F": 6,
    "A": 6,
}

CRASH_TAGS = {
    "androidruntime",
    "debug",
    "crashlytics",
    "libc",
    "tombstoned",
    "appcrash",
}

CRASH_PATTERNS = [
    re.compile(r"FATAL EXCEPTION", re.IGNORECASE),
    re.compile(r"signal \d+ \(SIG\w+\)", re.IGNORECASE),
    re.compile(r"fatal signal", re.IGNORECASE),
    re.compile(r"NullPointerException", re.IGNORECASE),
    re.compile(r"UncaughtException", re.IGNORECASE),
    re.compile(r"ANR in\s+", re.IGNORECASE),
    re.compile(r"backtrace:\s*$", re.IGNORECASE),
    re.compile(r"\s+at\s+[\w\.\$]+\([\w\.\$]+:\d+\)"),  # Java stack trace line
    re.compile(r"abort\(\) called", re.IGNORECASE),
    re.compile(r"Unity\s*:\s*Exception", re.IGNORECASE),
]


@dataclass
class LogEntry:
    id: int
    raw: str
    timestamp: str
    pid: Optional[int]
    tid: Optional[int]
    level: str
    level_name: str
    tag: str
    message: str
    package: Optional[str] = None
    is_crash: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LogParser:
    def __init__(self):
        self._current_id = 0
        self._last_entry: Optional[LogEntry] = None

    def reset(self):
        self._current_id = 0
        self._last_entry = None

    def parse_line(self, line: str, pid_to_package: Optional[Dict[int, str]] = None) -> LogEntry:
        """
        Parses a single line of logcat output.
        Handles threadtime format, fallback formats, and continuation lines (e.g. stack traces).
        """
        line_clean = line.rstrip("\r\n")
        self._current_id += 1

        match = LOGCAT_THREADTIME_PATTERN.match(line_clean)
        if match:
            timestamp, pid_s, tid_s, level_char, tag, message = match.groups()
            pid = int(pid_s)
            tid = int(tid_s)
            level = level_char.upper()
            tag_clean = tag.strip()

            package = None
            if pid_to_package and pid in pid_to_package:
                package = pid_to_package[pid]

            is_crash = self._is_crash_line(level, tag_clean, message)

            entry = LogEntry(
                id=self._current_id,
                raw=line_clean,
                timestamp=timestamp,
                pid=pid,
                tid=tid,
                level=level,
                level_name=LEVEL_MAP.get(level, level),
                tag=tag_clean,
                message=message,
                package=package,
                is_crash=is_crash,
            )
            self._last_entry = entry
            return entry

        # Check brief format
        match_brief = LOGCAT_BRIEF_PATTERN.match(line_clean)
        if match_brief:
            level_char, tag, pid_s, message = match_brief.groups()
            pid = int(pid_s)
            level = level_char.upper()
            tag_clean = tag.strip()

            package = None
            if pid_to_package and pid in pid_to_package:
                package = pid_to_package[pid]

            is_crash = self._is_crash_line(level, tag_clean, message)

            entry = LogEntry(
                id=self._current_id,
                raw=line_clean,
                timestamp="",
                pid=pid,
                tid=None,
                level=level,
                level_name=LEVEL_MAP.get(level, level),
                tag=tag_clean,
                message=message,
                package=package,
                is_crash=is_crash,
            )
            self._last_entry = entry
            return entry

        # Continuation line (e.g. stack trace line or raw message without header)
        if self._last_entry is not None:
            is_crash = self._last_entry.is_crash or any(p.search(line_clean) for p in CRASH_PATTERNS)
            entry = LogEntry(
                id=self._current_id,
                raw=line_clean,
                timestamp=self._last_entry.timestamp,
                pid=self._last_entry.pid,
                tid=self._last_entry.tid,
                level=self._last_entry.level,
                level_name=self._last_entry.level_name,
                tag=self._last_entry.tag,
                message=line_clean,
                package=self._last_entry.package,
                is_crash=is_crash,
            )
            return entry

        # Unrecognized initial line
        entry = LogEntry(
            id=self._current_id,
            raw=line_clean,
            timestamp="",
            pid=None,
            tid=None,
            level="I",
            level_name="INFO",
            tag="",
            message=line_clean,
            package=None,
            is_crash=any(p.search(line_clean) for p in CRASH_PATTERNS),
        )
        self._last_entry = entry
        return entry

    def _is_crash_line(self, level: str, tag: str, message: str) -> bool:
        """Determines whether a log entry is part of a crash or critical error."""
        if level in ("F", "A"):
            return True
        if tag.lower() in CRASH_TAGS and level in ("E", "W"):
            return True
        for pattern in CRASH_PATTERNS:
            if pattern.search(message):
                return True
        return False
