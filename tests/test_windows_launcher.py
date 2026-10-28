import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]


def launcher():
    spec = importlib.util.spec_from_file_location("storm_launcher", ROOT / "tools/storm_launcher.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LauncherTests(unittest.TestCase):
    def test_server_binds_only_to_loopback_and_handles_spaces(self):
        m = launcher()
        args = m.server_command(Path("C:/My Project/storm"), 8512)
        self.assertEqual(args[1:4], ["-m", "streamlit", "run"])
        self.assertIn("127.0.0.1", args)
        self.assertIn("8512", args)
        self.assertEqual(args[4], str(Path("C:/My Project/storm") / "frontend/demo_light/storm.py"))

    def test_saved_url_cannot_open_an_external_site(self):
        m = launcher()
        self.assertTrue(m.is_local_url("http://127.0.0.1:8512"))
        for url in ["https://example.com", "file:///secret", "http://127.0.0.1.evil.test:8512", "http://user:pass@127.0.0.1:8512"]:
            self.assertFalse(m.is_local_url(url))

    def test_missing_project_environment_has_actionable_error(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(m.LaunchError) as error:
                m.ServerSession(Path(folder)).start()
            self.assertIn("install_windows_launcher.ps1", str(error.exception))

    def test_stop_never_terminates_a_process_from_a_saved_pid(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder, patch.object(m.subprocess, "run") as run:
            session = m.ServerSession(Path(folder))
            session.state_file.parent.mkdir(parents=True)
            session.state_file.write_text(json.dumps({"pid": 1234, "url": "http://127.0.0.1:8512"}))
            session.stop()
            run.assert_not_called()

    def test_stop_terminates_only_its_running_server_tree(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder, patch.object(m.subprocess, "run") as run:
            session = m.ServerSession(Path(folder))
            session.process = Mock(pid=2468)
            session.process.poll.return_value = None
            session.stop()
            self.assertEqual(run.call_args.args[0], ["taskkill", "/PID", "2468", "/T", "/F"])
            self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_start_uses_project_python_and_codex_even_with_old_api_settings(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in [".venv/Scripts/python.exe", "frontend/demo_light/storm.py"]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
            process = Mock()
            process.poll.return_value = 0
            with patch.object(m, "find_codex", return_value="C:/Codex/codex.exe"), patch.object(m.subprocess, "Popen", return_value=process) as popen, patch.dict(os.environ, {"STORM_PROVIDER": "openai"}):
                session = m.ServerSession(root)
                session.start()
                session.stop()
            self.assertEqual(popen.call_args.kwargs["env"]["STORM_PROVIDER"], "codex")
            self.assertEqual(Path(popen.call_args.args[0][0]), root.resolve() / ".venv/Scripts/python.exe")


if __name__ == "__main__":
    unittest.main()
