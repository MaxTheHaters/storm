"""Windows launcher for the local STORM Web UI. Only manages its own server."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
import webbrowser


class LaunchError(RuntimeError):
    pass


def is_local_url(url):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                and parsed.port is not None and not parsed.username and not parsed.password
                and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment)
    except (TypeError, ValueError):
        return False


def server_command(project_root, port):
    return [str(project_root / ".venv/Scripts/python.exe"), "-m", "streamlit", "run",
            str(project_root / "frontend/demo_light/storm.py"),
            "--server.address", "127.0.0.1", "--server.port", str(port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false"]


def find_codex():
    configured = os.getenv("STORM_CODEX_COMMAND")
    found = shutil.which(configured or "codex")
    if found:
        return found
    # The desktop app's CLI may be available only in its own terminal PATH.
    candidates = list((Path.home() / "AppData/Local/OpenAI/Codex/bin").glob("*/codex.exe"))
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    raise LaunchError("找不到 Codex。請安裝 Codex CLI、完成 codex login，或設定 STORM_CODEX_COMMAND。")


def open_app_window(url):
    if not is_local_url(url):
        raise LaunchError("無法開啟無效的本機服務網址。")
    candidates = [
        Path(os.getenv("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.getenv("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.getenv("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
    ]
    browser = next((path for path in candidates if path.is_file()), None)
    if browser:
        subprocess.Popen([str(browser), f"--app={url}"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        webbrowser.open(url)


class ServerSession:
    def __init__(self, project_root):
        self.project_root = project_root.resolve()
        self.runtime_dir = self.project_root / "local/launcher"
        self.state_file = self.runtime_dir / "session.json"
        self.log_file = self.runtime_dir / "streamlit.log"
        self.process = None
        self.log = None
        self.url = None
        self.stop_lock = threading.Lock()

    def start(self):
        python = self.project_root / ".venv/Scripts/python.exe"
        app = self.project_root / "frontend/demo_light/storm.py"
        if not python.is_file() or not app.is_file():
            raise LaunchError("尚未準備好專案環境，請先執行 tools/install_windows_launcher.ps1。")
        codex = find_codex()
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.unlink(missing_ok=True)
        with socket.socket() as port_check:
            port_check.bind(("127.0.0.1", 0))
            port = port_check.getsockname()[1]
        env = dict(os.environ, STORM_PROVIDER="codex", STORM_CODEX_COMMAND=codex)
        self.log = self.log_file.open("w", encoding="utf-8")
        try:
            self.process = subprocess.Popen(
                server_command(self.project_root, port), cwd=self.project_root, env=env,
                stdout=self.log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), shell=False,
            )
        except OSError as exc:
            self.log.close()
            raise LaunchError(f"無法啟動服務，請查看 {self.log_file}") from exc
        self.url = f"http://127.0.0.1:{port}"

    def wait_ready(self, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise LaunchError(f"STORM 啟動失敗，請查看 {self.log_file}")
            try:
                with urlopen(self.url + "/_stcore/health", timeout=1) as response:
                    if response.status == 200 and response.read() == b"ok" and self.process.poll() is None:
                        self.state_file.write_text(json.dumps({"url": self.url}), encoding="utf-8")
                        return
            except OSError:
                pass
            time.sleep(0.2)
        raise LaunchError(f"STORM 啟動逾時，請查看 {self.log_file}")

    def stop(self):
        with self.stop_lock:
            self._stop_owned_server()

    def _stop_owned_server(self):
        # Never trust a PID from disk. Only terminate the Popen tree we created.
        if self.process is not None and self.process.poll() is None:
            subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                           timeout=15, check=False, shell=False)
            self.process.wait(timeout=15)
        if self.log is not None:
            self.log.close()
        self.state_file.unlink(missing_ok=True)


class SingleInstance:
    def __init__(self, project_root):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel = kernel
        identity = hashlib.sha256(str(project_root.resolve()).lower().encode("utf-8")).hexdigest()
        self.handle = kernel.CreateMutexW(None, False, "Local\\STORM-" + identity)
        self.already_running = ctypes.get_last_error() == 183
        if not self.handle:
            raise LaunchError("無法建立 STORM 啟動器。")

    def close(self):
        self.kernel.CloseHandle(self.handle)


def main():
    import tkinter as tk
    from tkinter import messagebox, ttk

    parser = argparse.ArgumentParser()
    default_root = Path(__file__).resolve().parents[1]
    if getattr(sys, "frozen", False):
        config = Path(sys.executable).with_name("project-root.txt")
        if config.exists():
            default_root = Path(config.read_text(encoding="utf-8").strip())
    parser.add_argument("--project-root", type=Path, default=default_root)
    args = parser.parse_args()
    session = ServerSession(args.project_root)
    guard = SingleInstance(args.project_root)
    if guard.already_running:
        try:
            for _ in range(450):
                if session.state_file.exists():
                    url = json.loads(session.state_file.read_text(encoding="utf-8")).get("url")
                    if is_local_url(url):
                        open_app_window(url)
                        return
                time.sleep(0.2)
            raise LaunchError("STORM 仍在啟動中，請稍後再按一次。")
        except (OSError, ValueError, LaunchError) as exc:
            messagebox.showerror("STORM", str(exc))
        finally:
            guard.close()
        return

    root = tk.Tk()
    root.title("STORM")
    root.geometry("440x220")
    root.resizable(False, False)
    icon = session.runtime_dir / "storm.ico"
    if icon.exists():
        root.iconbitmap(str(icon))
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="STORM", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    status = tk.StringVar(value="正在啟動研究介面…")
    ttk.Label(frame, textvariable=status, wraplength=390).pack(anchor="w", pady=(8, 14))
    open_button = ttk.Button(frame, text="開啟 STORM", state="disabled", command=lambda: open_app_window(session.url))
    open_button.pack(side="left")
    closed = threading.Event()
    result = {}

    def start_server():
        try:
            if closed.is_set():
                return
            session.start()
            if closed.is_set():
                return
            session.wait_ready()
            result["ready"] = True
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            if closed.is_set():
                session.stop()

    worker = threading.Thread(target=start_server)
    worker.start()

    def close():
        if closed.is_set():
            return
        closed.set()
        root.withdraw()
        worker.join(timeout=2)
        try:
            session.stop()
        finally:
            guard.close()
            root.destroy()

    ttk.Button(frame, text="結束 STORM", command=close).pack(side="right")
    root.protocol("WM_DELETE_WINDOW", close)

    def update():
        if closed.is_set():
            return
        if "error" in result:
            status.set(result["error"])
        elif result.get("ready"):
            status.set("服務已啟動。關閉此啟動器會停止服務。")
            open_button.configure(state="normal")
            open_app_window(session.url)
            root.iconify()
            return
        else:
            root.after(200, update)

    root.after(200, update)
    root.mainloop()


if __name__ == "__main__":
    main()
