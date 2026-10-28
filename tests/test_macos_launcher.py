import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def launcher():
    spec = importlib.util.spec_from_file_location("macos_launcher", ROOT / "tools/macos_launcher.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MacLauncherTests(unittest.TestCase):
    def test_server_uses_project_python_and_loopback(self):
        m = launcher()
        root = Path("/Users/test/My Project/storm")
        args = m.server_command(root, 8518)
        self.assertEqual(args[0], str(root / ".venv/bin/python"))
        self.assertEqual(args[4], str(root / "frontend/demo_light/storm.py"))
        self.assertIn("127.0.0.1", args)
        self.assertIn("8518", args)

    def test_start_forces_codex_and_creates_owned_process_group(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in [".venv/bin/python", "frontend/demo_light/storm.py"]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            process = Mock()
            process.poll.return_value = 0
            with patch.object(m, "find_codex", return_value="/Applications/ChatGPT.app/codex"), patch.object(m.subprocess, "Popen", return_value=process) as popen, patch.object(m, "kill_process_group"), patch.object(m, "process_group_exists", return_value=False), patch.dict(os.environ, {"STORM_PROVIDER": "openai"}):
                session = m.ServerSession(root)
                session.start()
                session.stop()
            options = popen.call_args.kwargs
            self.assertTrue(options["start_new_session"])
            self.assertEqual(options["env"]["STORM_PROVIDER"], "codex")
            self.assertFalse(options["shell"])

    def test_missing_environment_has_setup_instructions(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(m.LaunchError) as error:
                m.ServerSession(Path(folder)).start()
            self.assertIn("install_macos_launcher", str(error.exception))

    def test_stop_does_not_kill_a_pid_from_disk(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder, patch.object(m, "kill_process_group") as kill, patch.object(m, "process_group_exists", return_value=False):
            session = m.ServerSession(Path(folder))
            session.stop()
            kill.assert_not_called()

    def test_stop_terminates_only_its_owned_running_group(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder, patch.object(m, "kill_process_group") as kill, patch.object(m, "process_group_exists", return_value=False):
            session = m.ServerSession(Path(folder))
            session.process = Mock(pid=2468)
            session.process.poll.return_value = None
            session.stop()
            kill.assert_called_once_with(2468, signal.SIGTERM)
            session.stop()
            kill.assert_called_once_with(2468, signal.SIGTERM)

    def test_failed_server_never_reports_ready(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder:
            session = m.ServerSession(Path(folder))
            session.process = Mock()
            session.process.poll.return_value = 1
            session.url = "http://127.0.0.1:8518"
            with self.assertRaises(m.LaunchError):
                session.wait_ready(timeout=0.5)

    @unittest.skipUnless(os.name == "posix", "POSIX process groups require macOS/Linux")
    def test_real_owned_process_is_stopped(self):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder:
            session = m.ServerSession(Path(folder))
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
            session.process = child
            try:
                session.stop()
                self.assertIsNotNone(child.poll())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()

    def check_descendant_cleanup(self, leader_exits, ignore_term):
        m = launcher()
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / "descendant.pid"
            code = """
import os, signal, sys, time
from pathlib import Path
marker = Path(sys.argv[1])
if os.fork() == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN if sys.argv[3] == 'True' else signal.SIG_DFL)
    marker.write_text(str(os.getpid()))
else:
    while not marker.exists(): time.sleep(0.01)
    if sys.argv[2] == 'True': sys.exit(0)
while True: time.sleep(1)
"""
            child = subprocess.Popen([sys.executable, "-c", code, str(marker),
                                      str(leader_exits), str(ignore_term)], start_new_session=True)
            session = m.ServerSession(Path(folder))
            session.process = child
            try:
                deadline = time.monotonic() + 5
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists(), "descendant did not start")
                if leader_exits:
                    child.wait(timeout=5)
                session.stop()
                descendant = int(marker.read_text())
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    state = subprocess.run(["ps", "-o", "stat=", "-p", str(descendant)],
                                           capture_output=True, text=True).stdout.strip()
                    if not state or state.startswith("Z"):
                        break
                    time.sleep(0.05)
                self.assertTrue(not state or state.startswith("Z"), "owned descendant is still running")
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=5)

    @unittest.skipUnless(os.name == "posix", "POSIX process groups require macOS/Linux")
    def test_descendant_stopped_after_leader_exits(self):
        self.check_descendant_cleanup(leader_exits=True, ignore_term=False)

    @unittest.skipUnless(os.name == "posix", "POSIX process groups require macOS/Linux")
    def test_term_resistant_descendant_is_killed(self):
        self.check_descendant_cleanup(leader_exits=False, ignore_term=True)


if __name__ == "__main__":
    unittest.main()
