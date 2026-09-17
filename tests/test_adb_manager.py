"""
Unit tests for AdbManager parsing logic and device handling.
"""
import subprocess
import unittest
from unittest.mock import MagicMock
from backend.adb_manager import AdbManager


class TestAdbManager(unittest.TestCase):
    def setUp(self):
        self.mgr = AdbManager()

    def test_parse_devices_output(self):
        sample_output = (
            "List of devices attached\n"
            "emulator-5554          device product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 device:emu64a transport_id:1\n"
            "RFCW123456            device usb:1-1 product:a52sxq model:SM_A528B device:a52sxq transport_id:2\n"
            "192.168.1.50:5555     device product:pixel7 model:Pixel_7 device:panther transport_id:3\n"
            "OFFLINE123            offline\n"
            "UNAUTH456             unauthorized\n"
        )
        self.mgr.run_cmd = MagicMock(return_value=subprocess.CompletedProcess(
            args=["devices", "-l"], returncode=0, stdout=sample_output, stderr=""
        ))

        devices = self.mgr.get_devices()
        self.assertEqual(len(devices), 5)

        # First device: emulator
        self.assertEqual(devices[0]["serial"], "emulator-5554")
        self.assertEqual(devices[0]["status"], "device")
        self.assertTrue(devices[0]["is_emulator"])
        self.assertFalse(devices[0]["is_wifi"])

        # Second device: USB Samsung
        self.assertEqual(devices[1]["serial"], "RFCW123456")
        self.assertEqual(devices[1]["model"], "SM A528B")

        # Third device: Wi-Fi
        self.assertEqual(devices[2]["serial"], "192.168.1.50:5555")
        self.assertTrue(devices[2]["is_wifi"])
        self.assertEqual(devices[2]["model"], "Pixel 7")

        # Statuses
        self.assertEqual(devices[3]["status"], "offline")
        self.assertEqual(devices[4]["status"], "unauthorized")

        # Auto-selected device should be the first active one
        self.assertEqual(self.mgr.selected_device, "emulator-5554")

    def test_parse_packages_output(self):
        self.mgr.selected_device = "mock-device"
        sample_output = (
            "package:com.supercell.clashroyale\n"
            "package:com.spotify.music\n"
            "package:com.whatsapp\n"
        )
        self.mgr.run_cmd = MagicMock(return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=sample_output, stderr=""
        ))

        packages = self.mgr.get_installed_packages(third_party_only=True)
        self.assertEqual(len(packages), 3)
        self.assertEqual(packages[0]["package"], "com.spotify.music")
        self.assertEqual(packages[0]["name"], "Music")
        self.assertEqual(packages[1]["package"], "com.supercell.clashroyale")
        self.assertEqual(packages[1]["name"], "Clashroyale")

    def test_parse_ps_mapping(self):
        self.mgr.selected_device = "mock-device"
        sample_ps = (
            "PID NAME\n"
            "1 init\n"
            "2045 com.supercell.clashroyale\n"
            "3090 com.spotify.music\n"
        )
        self.mgr.run_cmd = MagicMock(return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=sample_ps, stderr=""
        ))

        mapping = self.mgr.update_running_processes()
        self.assertEqual(mapping[2045], "com.supercell.clashroyale")
        self.assertEqual(mapping[3090], "com.spotify.music")
        self.assertEqual(self.mgr.get_package_pids("com.supercell.clashroyale"), [2045])


if __name__ == "__main__":
    unittest.main()
