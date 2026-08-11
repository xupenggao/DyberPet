import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ThreadLifecycleSourceTests(unittest.TestCase):
    def test_scheduler_worker_uses_scheduler_thread(self):
        source = (ROOT / "DyberPet" / "DyberPet.py").read_text(encoding="utf-8")

        self.assertIn(
            "self.workers['Scheduler'].moveToThread(self.threads['Scheduler'])",
            source,
        )
        self.assertNotIn(
            "self.workers['Scheduler'].moveToThread(self.threads['Interaction'])",
            source,
        )

    def test_pet_widget_has_idempotent_shutdown(self):
        source = (ROOT / "DyberPet" / "DyberPet.py").read_text(encoding="utf-8")

        self.assertIn("def shutdown(self)", source)
        self.assertIn("self._shutting_down", source)

    def test_app_shutdown_runs_on_about_to_quit(self):
        source = (ROOT / "run_DyberPet.py").read_text(encoding="utf-8-sig")

        self.assertIn("def shutdown(self)", source)
        self.assertIn("self.aboutToQuit.connect(self.shutdown)", source)


if __name__ == "__main__":
    unittest.main()
