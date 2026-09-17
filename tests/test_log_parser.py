"""
Unit tests for LogParser
"""
import unittest
from backend.log_parser import LogParser


class TestLogParser(unittest.TestCase):
    def setUp(self):
        self.parser = LogParser()

    def test_parse_threadtime_format(self):
        line = "09-17 13:45:22.139  3143  3874 I Unity   : Starting scene loaded"
        entry = self.parser.parse_line(line, pid_to_package={3143: "com.example.game"})

        self.assertEqual(entry.id, 1)
        self.assertEqual(entry.timestamp, "09-17 13:45:22.139")
        self.assertEqual(entry.pid, 3143)
        self.assertEqual(entry.tid, 3874)
        self.assertEqual(entry.level, "I")
        self.assertEqual(entry.level_name, "INFO")
        self.assertEqual(entry.tag, "Unity")
        self.assertEqual(entry.message, "Starting scene loaded")
        self.assertEqual(entry.package, "com.example.game")
        self.assertFalse(entry.is_crash)

    def test_parse_crash_fatal_exception(self):
        header = "09-17 13:45:22.139  1200  1200 E AndroidRuntime: FATAL EXCEPTION: main"
        stack_line = "\tat com.example.game.MainActivity.onCreate(MainActivity.java:42)"

        entry1 = self.parser.parse_line(header, pid_to_package={1200: "com.example.game"})
        self.assertTrue(entry1.is_crash)
        self.assertEqual(entry1.level, "E")

        entry2 = self.parser.parse_line(stack_line)
        self.assertTrue(entry2.is_crash)
        self.assertEqual(entry2.pid, 1200)
        self.assertEqual(entry2.package, "com.example.game")
        self.assertIn("MainActivity.onCreate", entry2.message)

    def test_parse_sigsegv(self):
        line = "09-17 13:45:22.139  5000  5000 F libc    : Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR)"
        entry = self.parser.parse_line(line)
        self.assertTrue(entry.is_crash)
        self.assertEqual(entry.level, "F")
        self.assertEqual(entry.level_name, "FATAL")


if __name__ == "__main__":
    unittest.main()
