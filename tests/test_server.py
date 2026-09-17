"""
Unit tests for backend server and LogHub.
"""
import unittest
from backend.server import LogHub
from backend.log_parser import LogEntry


class TestLogHub(unittest.TestCase):
    def test_loghub_add_and_history(self):
        hub = LogHub(max_buffer_size=10)
        for i in range(15):
            entry = LogEntry(
                id=i + 1,
                raw=f"line {i+1}",
                timestamp="09-17 12:00:00.000",
                pid=1000,
                tid=1000,
                level="I",
                level_name="INFO",
                tag="Test",
                message=f"message {i+1}",
            )
            hub.add_entry(entry)

        # Should respect max_buffer_size = 10
        history = hub.get_history(limit=50)
        self.assertEqual(len(history), 10)
        self.assertEqual(history[0]["id"], 6)
        self.assertEqual(history[-1]["id"], 15)

    def test_client_queue_streaming(self):
        hub = LogHub()
        client_q = hub.register_client()

        entry = LogEntry(
            id=1,
            raw="test line",
            timestamp="09-17 12:00:00.000",
            pid=200,
            tid=200,
            level="E",
            level_name="ERROR",
            tag="Test",
            message="Error happened",
            is_crash=True,
        )
        hub.add_entry(entry)

        item = client_q.get(timeout=1.0)
        self.assertEqual(item["id"], 1)
        self.assertEqual(item["level"], "E")
        self.assertTrue(item["is_crash"])

        hub.unregister_client(client_q)


if __name__ == "__main__":
    unittest.main()
