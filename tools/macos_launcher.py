"""Own the local Streamlit process for the macOS Dock app."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.request import ProxyHandler, build_opener


class LaunchError(RuntimeError):
    pass


def server_command(project_root, port):
    return [str(project_root / ".venv/bin/python"), "-m", "streamlit", "run",
            str(project_root / "frontend/demo_light/storm.py"),
            "--server.address", "127.0.0.1", "--server.port", str(port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false"]


def find_codex():
    configured = os.getenv("STORM_CODEX_COMMAND")
    candidates = ([configured] if configured else [
        shutil.which("codex"),
        str(Path.home() / ".codex/ssh-remote/bin/codex"),
        "/opt/homebrew/bin/codex", "/usr/local/bin/codex",
        "/Applications/ChatGPT.app/Contents/Resources/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
    ])
    for candidate in candidates:
        resolved = shutil.which(candidate) if candidate else None
        if resolved:
            return resolved
    raise LaunchError("找不到 Codex CLI。請完成安裝與 codex login，或設定 STORM_CODEX_COMMAND。")


def kill_process_group(pid, sig):
    os.killpg(pid, sig)


def process_group_exists(pid):
    try:
        kill_process_group(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        # Darwin can report EPERM for a group with only a terminating zombie.
        # An inaccessible group must never be signaled as one we own.
        return False


class ServerSession:
    def __init__(self, project_root):
        self.project_root = project_root.resolve()
        self.runtime_dir = self.project_root / "local/macos-launcher"
        self.log_file = self.runtime_dir / "streamlit.log"
        self.process = None
        self.log = None
        self.url = None

    def start(self):
        if not (self.project_root / ".venv/bin/python").is_file():
            raise LaunchError("尚未準備好 Python 環境，請先執行 tools/install_macos_launcher.py。")
        if not (self.project_root / "frontend/demo_light/storm.py").is_file():
            raise LaunchError("找不到 STORM 專案，請重新安裝啟動器。")
        codex = find_codex()
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        self.log = self.log_file.open("a", encoding="utf-8")
        env = dict(os.environ, STORM_PROVIDER="codex", STORM_CODEX_COMMAND=codex)
        # Finder/Dock does not inherit a terminal's Homebrew PATH.
        env["PATH"] = os.pathsep.join([str(Path(codex).parent), "/opt/homebrew/bin",
                                       "/usr/local/bin", env.get("PATH", "/usr/bin:/bin")])
        try:
            self.process = subprocess.Popen(
                server_command(self.project_root, port), cwd=self.project_root, env=env,
                stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True, shell=False,
            )
        except OSError as exc:
            self.log.close()
            raise LaunchError(f"無法啟動 STORM，請查看 {self.log_file}") from exc
        self.url = f"http://127.0.0.1:{port}"

    def wait_ready(self, timeout=180, stopped=None):
        stopped = stopped or threading.Event()
        deadline = time.monotonic() + timeout
        opener = build_opener(ProxyHandler({}))
        while time.monotonic() < deadline:
            if stopped.is_set():
                raise LaunchError("啟動已取消。")
            if self.process.poll() is not None:
                raise LaunchError(f"STORM 啟動失敗，請查看 {self.log_file}")
            try:
                with opener.open(self.url + "/_stcore/health", timeout=1) as response:
                    if response.status == 200 and response.read() == b"ok" and self.process.poll() is None:
                        return
            except OSError:
                pass
            stopped.wait(0.2)
        raise LaunchError(f"STORM 啟動逾時，請查看 {self.log_file}")

    def stop(self):
        # Consume this session's ownership once, including after a server crash.
        # Never reconstruct a process/group handle from a PID stored on disk.
        process, self.process = self.process, None
        if process is not None:
            try:
                kill_process_group(process.pid, signal.SIGTERM)
                deadline = time.monotonic() + 5
                while process_group_exists(process.pid) and time.monotonic() < deadline:
                    process.poll()  # Reap the leader without overlooking descendants.
                    time.sleep(0.05)
                if process_group_exists(process.pid):
                    kill_process_group(process.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            process.wait(timeout=5)
        if self.log is not None:
            self.log.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int)
    args = parser.parse_args()
    stopped = threading.Event()
    if args.parent_pid is not None:
        if os.getppid() != args.parent_pid:
            return 0

        def watch_parent():
            while not stopped.wait(0.2):
                if os.getppid() != args.parent_pid:
                    stopped.set()
                    return

        threading.Thread(target=watch_parent, daemon=True).start()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    session = ServerSession(args.project_root)
    try:
        session.start()
        session.wait_ready(stopped=stopped)
        print(json.dumps({"url": session.url}), flush=True)
        while not stopped.wait(0.2):
            if session.process.poll() is not None:
                raise LaunchError(f"STORM 服務已停止，請查看 {session.log_file}")
    except LaunchError as exc:
        if not stopped.is_set():
            print(json.dumps({"error": str(exc)}), flush=True)
            return 1
    finally:
        stopped.set()
        session.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
