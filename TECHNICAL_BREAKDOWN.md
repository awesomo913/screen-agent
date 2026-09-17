# Screen Agent v1 — Technical Breakdown

## Overview

Screen Agent is a 3,137-line Python desktop application that provides AI-powered screen automation via Ollama vision models, a 3,158-function toolkit, and an integrated launcher for 10 external coding tools. It runs on Windows 10/11 with Python 3.11.

---

## Architecture

```
screen_agent/
├── screen_agent.py          # 3,137 lines — GUI, agent loop, all tabs
├── requirements.txt         # 5 core deps: customtkinter, pyautogui, Pillow, ollama, mss
├── test_all_tools.py        # Automated test runner (timeout-guarded, skip-safe)
├── reference_screen_control.py
└── toolkit/                 # 233 Python modules
    ├── __init__.py           # Exposes get_registry()
    ├── registry.py           # Auto-discovery, category mapping, call_tool() API
    ├── clipboard_image_tools.py  # 17 funcs — in-place clipboard image editing
    ├── desktop_control.py        # 11 funcs — wallpaper, dark mode, taskbar, icons
    ├── display_gamma.py          # 5 funcs  — GDI gamma ramp brightness/color temp
    ├── wifi_tools.py             # 8 funcs  — WiFi passwords, profiles, scanning
    ├── print_queue.py            # 10 funcs — print jobs, spooler, queue management
    ├── toolkit_01..toolkit_134   # 130+ auto-discovered tool modules
    └── [70+ action modules]      # clipboard, audio, file, network, etc.
```

### Single-File GUI (screen_agent.py)

The entire GUI is one CTk (CustomTkinter) application — no framework split across files. This is a deliberate design choice: the agent loop, tool registry integration, tab builders, and subprocess launchers are all co-located for fast iteration. The tradeoff is a large single file that becomes harder to navigate as features grow.

**Class: `ScreenAgent`**
- `__init__()` — window setup (800x960, always-on-top), state variables, saved tasks
- `_build_gui()` — input bar, 7-tab tabview, status indicator
- `_build_main_tab()` — model selection, options, 36+ automations, chat log
- `_build_tools_tab()` — 22-category tool browser with search
- `_build_coder_tab()` — AI Coder launcher (10 tools, 7 quick start options)
- `_build_clipboard_tab()` — 17-function clipboard image editor
- `_build_history_tab()` — past task log with reuse
- `_build_saved_tab()` — saved prompts
- `_build_settings_tab()` — theme, font, tutorials
- `_agent_loop()` — screenshot capture → LLM inference → action parsing → execution

---

## Core Systems

### 1. Agent Loop (`_agent_loop`, ~200 lines)

The main automation engine:

1. **Screenshot** — `mss.grab()` captures the screen, compresses to JPEG for LLM
2. **Context Build** — last 10 action history + last tool result + helpful hints
3. **LLM Call** — `ollama.chat()` with vision model (llava:7b/13b), 120s timeout, 3 retries
4. **Action Parse** — extracts JSON from response: `{action, x, y, text, reason}`
5. **Stuck Detection** — if last 3 actions identical, forces "done"
6. **Execute** — dispatches to pyautogui (click/type/key/scroll) or toolkit (tool_call)
7. **Loop** — repeats up to max_steps with configurable delay

**Supported Actions:**
| Action | Handler | What it does |
|--------|---------|-------------|
| click, double_click, right_click | pyautogui | Mouse input at (x,y) |
| type | pyautogui.write | Keyboard text entry |
| key, hotkey | pyautogui.press/hotkey | Key combos (ctrl+c, etc.) |
| scroll | pyautogui.scroll | Mouse wheel |
| move | pyautogui.moveTo | Cursor positioning |
| wait | time.sleep | Pause N seconds |
| tool_call | registry.call_tool | Invoke any of 3,158 toolkit functions |
| think | display only | Agent reasoning (shown in chat) |
| done | stop loop | Task completed |

### 2. Toolkit Registry (`toolkit/registry.py`, 412 lines)

Auto-discovery engine that loads all `.py` files in `toolkit/` at startup:

- **Imports** every module, skipping gracefully on missing deps
- **Inspects** all public functions via `inspect.getmembers()`
- **Maps** each to a category (22 categories defined in `MODULE_CATEGORIES`)
- **Provides**: `list_tools()`, `search_tools()`, `call_tool()`, `get_tool_info()`
- **Standard return**: every tool returns `{"success": bool, "data": any, "error": str}`

**Registry Stats:**
| Metric | Value |
|--------|-------|
| Loaded modules | 207 |
| Total functions | 3,158 |
| Categories | 22 |
| Failed imports | 26 (missing optional deps) |

### 3. AI Coder Tab (10 integrated tools)

Launcher hub for all coding tools in the workspace:

| Tool | Model | Category | Launch Command |
|------|-------|----------|----------------|
| Gemini Coder | Google Gemini | Code Generation | `pythonw gemini_coder/launch.pyw` |
| PhantomForge | Ollama (Deepseek/Qwen/CodeLlama) | Code Generation | `pythonw -m phantom_forge --mode gui` |
| Vibe Coder | Ollama (multi-agent) | Code Generation | `streamlit run vibe_coder/app.py` |
| GUI Builder | Google Gemini | GUI & UI Building | `python -m gui_builder` |
| Autocoder (Web) | Any web AI via CDP | Browser AI Orchestration | `pythonw gemini_coder_web/launch.pyw` |
| Prompt Architect | Framework-agnostic | Prompt Engineering | `python prompt_architect.py` |
| Local Hub | Ollama MoE router | Local Model Infrastructure | `streamlit run local_hub/app.py` |
| Local Relay | Qwen 2.5 + Claude | Local Model Infrastructure | `python local_relay/local_relay.py` |
| Gemini Analyzer | Gemini exports | Analysis & Extraction | `python gemini_analyzer/main.py` |
| Claude Token Saver | Claude / any LLM | Context & Token Management | `python -m claude_backend.gui` |

Each tool launches as a **detached subprocess** — independent process that doesn't block Screen Agent.

### 4. Clipboard Image Tools (17 functions)

In-place Windows clipboard image manipulation using PIL + win32clipboard:
- **Read**: has_image, get_size, get_base64, get_average_color
- **Write**: create_blank, load_from_file, set_from_base64
- **Transform**: resize, crop, rotate, flip_h, flip_v, blur, grayscale, invert, add_border
- **Export**: save_to_file

All functions operate directly on the clipboard DIB — no temp files needed.

### 5. Desktop Control Module (11 functions)

Zero-dependency Windows system manipulation:
- **Wallpaper**: set/get via `user32.SystemParametersInfoW` (persists across reboots)
- **Theme**: dark/light mode toggle via registry + `WM_SETTINGCHANGE` broadcast
- **Taskbar**: position (left/top/right/bottom) and auto-hide via `StuckRects3` binary parsing
- **Desktop icons**: show/hide via `HideIcons` DWORD

### 6. Display Gamma (5 functions)

Software brightness via `gdi32.dll` gamma ramps — works on ALL displays including external monitors:
- Brightness 0-100%
- Color temperature 1000-10000K (warm/cool)
- Per-channel RGB gamma multipliers
- Reset to linear default

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| GUI Framework | CustomTkinter (ctk) | Dark-themed desktop UI |
| Vision Model | Ollama (llava:7b/13b) | Screen understanding |
| Screen Capture | mss | Fast multi-monitor screenshots |
| Input Control | pyautogui | Mouse/keyboard automation |
| Image Processing | Pillow (PIL) | Image manipulation, clipboard ops |
| Win32 APIs | ctypes (user32, gdi32, kernel32) | Wallpaper, gamma, display control |
| Registry | winreg | Theme, taskbar, desktop icons |
| Shell Commands | subprocess + PowerShell | System admin, network, printers |
| Data Persistence | JSON files | Tasks, history, settings |

**Python Version:** 3.11
**Platform:** Windows 10/11 only (heavy use of win32 APIs)
**Required Dependencies (pip):** customtkinter>=5.2, pyautogui>=0.9.54, Pillow>=10.0, ollama>=0.4, mss>=10.0

---

## Evaluation Criteria for AI Model Review

### Strengths

1. **Massive tool surface area** — 3,158 callable functions across 22 categories gives the agent enormous capability without external services.

2. **Graceful degradation** — 26 modules fail to import due to missing optional deps, but the registry loads the remaining 207 cleanly. No hard crashes.

3. **Standardized tool interface** — every function returns `{"success": bool, "data": any, "error": str}`, making LLM parsing deterministic.

4. **Zero-dependency system modules** — desktop_control, display_gamma, wifi_tools, print_queue all use only stdlib + ctypes. No pip install fragility.

5. **Self-contained agent loop** — screenshot → LLM → parse → execute pipeline with stuck detection, retry logic, and step limits.

6. **Integrated ecosystem** — AI Coder tab provides one-click access to 10 coding tools spanning cloud (Gemini), local (Ollama), and browser (CDP) paradigms.

### Weaknesses & Improvement Areas

1. **Single-file monolith** — `screen_agent.py` at 3,137 lines is too large. The 7 tab builders, agent loop, and helpers should be split into separate modules (e.g., `tabs/`, `agent/`, `helpers/`).

2. **No automated test coverage for GUI** — `test_all_tools.py` tests toolkit functions but there are zero tests for the agent loop, tab rendering, or launcher callbacks.

3. **Agent loop is naive** — The vision model receives the full screenshot every step. No region-of-interest cropping, no OCR pre-processing, no action masking. This wastes tokens on unchanged screen regions.

4. **No error recovery in agent loop** — If `ollama.chat()` returns malformed JSON, the loop retries the identical prompt. No prompt mutation, no fallback to text-only mode, no incremental context reduction.

5. **Hardcoded system prompt** — The agent's system prompt is a static string. It doesn't include the full 3,158-tool catalog (only a manually curated subset). The agent can't discover new tools dynamically.

6. **Clipboard image tools lack undo** — All transforms are destructive. There's no clipboard history stack to revert a bad crop/resize.

7. **No authentication/security layer** — Tool calls like `wifi_tools.get_wifi_password()` and `desktop_control.set_dark_mode()` execute without any confirmation gate. An adversarial prompt could invoke destructive operations.

8. **Scroll propagation hack** — `_bind_mousewheel()` manually re-binds events to all children. This is brittle — dynamically added widgets (e.g., log entries) won't get the binding.

9. **26 failed imports reduce capability** — Missing: matplotlib (charts), openpyxl (Excel), pytesseract (OCR), pynput (hotkeys), lxml (HTML/XML). These are commonly needed. A guided dependency installer would improve first-run experience.

10. **No persistent settings** — Theme choice, model selection, always-on-top preference are not saved to disk. Every restart resets to defaults.

11. **Subprocess launchers are fire-and-forget** — No health check, no stderr capture, no "tool crashed" notification. The launch log shows "LAUNCH" but never "FAILED" or "EXITED".

12. **Windows-only** — Heavy use of winreg, ctypes/user32, PowerShell, and win32clipboard makes this completely non-portable. No Linux/macOS path exists.

### Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Startup time | ~3-5s | Registry discovery of 233 modules |
| Toolkit test pass rate | ~92% | From test_all_tools.py runs |
| Agent step latency | 5-30s | Dominated by LLM inference time |
| Memory footprint | ~150-250MB | Depends on model loaded |
| Screenshot capture | <100ms | mss is fast |
| Tool call overhead | <10ms | Pure Python function dispatch |

### Recommended Next Steps (Priority Order)

1. **Split screen_agent.py** into `tabs/`, `agent/`, `core/` modules
2. **Add dependency installer** — detect missing optional deps, offer one-click install
3. **Persist settings** to JSON (theme, model, options)
4. **Add tool catalog to system prompt** — use `get_prompt_summary()` dynamically
5. **Add subprocess monitoring** — poll launched tools, report crashes
6. **Add undo stack** to clipboard image tools
7. **Add OCR preprocessing** to agent loop for text-heavy screens
8. **Add confirmation gate** for destructive toolkit operations

---

## File Manifest

### Core Application
| File | Lines | Purpose |
|------|-------|---------|
| screen_agent.py | 3,137 | Main application (GUI + agent + tabs) |
| test_all_tools.py | 484 | Automated toolkit test runner |
| requirements.txt | 5 | Core pip dependencies |

### New Modules (this session)
| File | Functions | Purpose |
|------|-----------|---------|
| toolkit/clipboard_image_tools.py | 17 | In-place clipboard image editing |
| toolkit/desktop_control.py | 11 | Wallpaper, theme, taskbar, icons |
| toolkit/display_gamma.py | 5 | GDI gamma brightness & color temp |
| toolkit/wifi_tools.py | 8 | WiFi password extraction & profiles |
| toolkit/print_queue.py | 10 | Print job & spooler management |

### Integrated External Tools (launched from AI Coder tab)
| Directory | Files | Purpose |
|-----------|-------|---------|
| gemini_coder/ | 18 | Gemini-powered task coding IDE |
| gemini_coder_web/ | 16 | Multi-browser AI orchestration (CDP) |
| phantom_forge/ | 41 | Local model code generation (Deepseek/Qwen) |
| gui_builder/ | 15 | Natural language → GUI code |
| vibe_coder/ | 7 | 3-agent local pipeline |
| local_hub/ | 5 | MoE model router |
| local_relay/ | 15 | Hybrid local/cloud code analysis |
| gemini_analyzer/ | 8 | Gemini takeout parser |
| claude interaction tool/ | 30+ | Context builder & token saver |
| prompt_architect.py | 1 | Structured prompt engineering |
