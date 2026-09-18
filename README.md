# Screen Agent

> A desktop automation agent with a 233-module action toolkit and a SQLite job queue behind a Tkinter GUI.

Screen Agent is an AI-drivable desktop automation tool: it exposes a huge library of discrete "action" modules (screen OCR, clipboard tools, file organizing, browser control, git actions, SSH, registry edits, screenshot/macro recording, and far more) that a dispatcher can queue and run, all behind a documented CustomTkinter GUI. It's built to let an AI (or a script) drive real desktop tasks through a consistent, testable interface rather than raw pixel-clicking.

## Features
- **233+ toolkit modules** in `toolkit/` — screen OCR, clipboard sync, file organizing/renaming, browser control, git/SSH/docker actions, registry tools, macro recording, template matching, and much more.
- SQLite-backed job dispatcher (`job_dispatcher.py`) for queuing and tracking automation jobs.
- CustomTkinter desktop GUI (`screen_agent.py`), documented in a 3,000+ line technical breakdown.
- Consistent per-tool return contract (`{success, data, error}`) across the whole toolkit for reliable chaining.
- Full test runner (`test_all_tools.py`) exercising the toolkit.
- Packaged as a standalone Windows executable via PyInstaller (`ScreenAgent.spec`).

## Stack
Python · CustomTkinter · pyautogui, mss, pywinauto (desktop/screen control) · Ollama (local AI) · PyInstaller.

## Getting started
**Requirements**
- Python 3.11+, Windows (uses pywinauto/registry-oriented tooling).

**Run**
```bash
pip install -r requirements.txt
python screen_agent.py
# or build the Windows exe per ScreenAgent.spec (PyInstaller)
```

## Status
**Unmaintained / archived** (last touched 2026-06-17). Published as-is — fork it, adapt it. No support or guarantees.

## License
[MIT](LICENSE) — free to use, fork, and build on.
