# macOS Dock launcher

Goal: install STORM on the user's SSH Mac (`codex-macbook`) and provide a Dock app that opens the local research UI without a terminal.

Architecture: a small AppKit app owns a project-Python supervisor and opens the research UI in the default browser. The supervisor starts Streamlit on a dynamically selected loopback port, waits for health, and reports the URL over stdout. Quitting the native app terminates the supervisor and its owned server process group. No PID from disk is used to stop a process. Project dependencies remain in `.venv`.

- Add Python supervisor and tests for safe binding, startup failure, Codex environment and owned-process cleanup.
- Add native Swift app and a macOS installer that compiles a `.app` into `~/Applications` without replacing unrelated apps.
- Clone the existing feature branch on the SSH Mac, prepare its environment and test native compilation and launch.
- Add STORM to the user's Dock after launch verification; document window-close versus Quit behavior.
- Publish only macOS-related changes to the existing Draft PR. Preserve the separate uncommitted Windows launcher work.

Verification: offline tests, Swift compilation on macOS, local health endpoint and startup logs, app lifecycle cleanup, Dock preference entry. Do not claim an entire research run was tested unless one is executed.
