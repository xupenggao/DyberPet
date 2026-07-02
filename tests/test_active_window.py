import unittest
from types import SimpleNamespace
from unittest.mock import patch

from DyberPet.active_window import ActiveWindowTracker, _surface_from_macos_window_info


class ActiveWindowTrackerMacTests(unittest.TestCase):
    def test_macos_quartz_window_info_uses_layer_zero_non_self_window(self):
        surface = _surface_from_macos_window_info(
            {
                "kCGWindowLayer": 0,
                "kCGWindowOwnerPID": 123,
                "kCGWindowOwnerName": "Code",
                "kCGWindowBounds": {"X": 10, "Y": 38, "Width": 800, "Height": 600},
            },
            current_pid=456,
        )

        self.assertIsNotNone(surface)
        self.assertEqual(surface.left, 10)
        self.assertEqual(surface.top, 38)
        self.assertEqual(surface.right, 810)
        self.assertEqual(surface.bottom, 638)
        self.assertEqual(surface.handle, "Code")

    def test_macos_quartz_window_info_ignores_self_window(self):
        surface = _surface_from_macos_window_info(
            {
                "kCGWindowLayer": 0,
                "kCGWindowOwnerPID": 456,
                "kCGWindowOwnerName": "DyberPet",
                "kCGWindowBounds": {"X": 10, "Y": 38, "Width": 800, "Height": 600},
            },
            current_pid=456,
        )

        self.assertIsNone(surface)

    def test_get_surface_parses_macos_window_bounds(self):
        tracker = ActiveWindowTracker()
        result = SimpleNamespace(
            returncode=0,
            stdout="Code\tDyberPet\t10\t38\t800\t600\n",
            stderr="",
        )

        with patch("DyberPet.active_window.platform", "darwin"), \
                patch.object(ActiveWindowTracker, "_get_macos_surface_quartz", side_effect=ImportError), \
                patch("DyberPet.active_window.subprocess.run", return_value=result):
            surface = tracker.get_surface()

        self.assertIsNotNone(surface)
        self.assertEqual(surface.left, 10)
        self.assertEqual(surface.top, 38)
        self.assertEqual(surface.right, 810)
        self.assertEqual(surface.bottom, 638)
        self.assertEqual(surface.handle, "Code")
        self.assertFalse(tracker.has_permission_error())

    def test_get_surface_decodes_macos_utf8_window_title(self):
        tracker = ActiveWindowTracker()
        result = SimpleNamespace(
            returncode=0,
            stdout="Code\tDyberPet - 巡游.md\t10\t38\t800\t600\n".encode("utf-8"),
            stderr=b"",
        )

        with patch("DyberPet.active_window.platform", "darwin"), \
                patch.object(ActiveWindowTracker, "_get_macos_surface_quartz", side_effect=ImportError), \
                patch("DyberPet.active_window.subprocess.run", return_value=result):
            surface = tracker.get_surface()

        self.assertIsNotNone(surface)
        self.assertEqual(surface.left, 10)
        self.assertEqual(surface.top, 38)
        self.assertEqual(surface.right, 810)
        self.assertEqual(surface.bottom, 638)
        self.assertEqual(surface.handle, "Code")
        self.assertFalse(tracker.has_permission_error())

    def test_get_surface_records_macos_permission_error(self):
        tracker = ActiveWindowTracker()
        result = SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="System Events got an error: osascript is not allowed assistive access. (-1719)\n",
        )

        with patch("DyberPet.active_window.platform", "darwin"), \
                patch.object(ActiveWindowTracker, "_get_macos_surface_quartz", side_effect=ImportError), \
                patch("DyberPet.active_window.subprocess.run", return_value=result):
            surface = tracker.get_surface()

        self.assertIsNone(surface)
        self.assertIn("assistive access", tracker.last_error)
        self.assertTrue(tracker.has_permission_error())


if __name__ == "__main__":
    unittest.main()
