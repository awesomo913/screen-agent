"""
dialog_actions.py
Production-ready screen agent toolkit for GUI dialogs using Tkinter.
Fully threaded, type-hinted, error-handled, and returns standardized Dict responses.
"""

import tkinter as tk
from tkinter import messagebox, filedialog, colorchooser, simpledialog, ttk
import threading
import queue
import uuid
import os
import time
from typing import Dict, Any, List, Optional, Tuple, Callable

# -----------------------------------------------------------------------------
# Internal Threading & Tkinter Helpers
# -----------------------------------------------------------------------------

_progress_registry: Dict[str, Dict[str, Any]] = {}
_progress_lock = threading.Lock()

def _format_response(status: str, data: Any = None, message: str = "") -> Dict[str, Any]:
    """Standardize dialog return format."""
    return {"status": status, "data": data, "message": message}

def _run_tk_dialog(func: Callable[..., Any], *args, **kwargs) -> Dict[str, Any]:
    """
    Safely execute a Tkinter dialog in a background thread.
    Handles event loop, root lifecycle, and thread-safe result passing.
    """
    result_queue: queue.Queue[Tuple[str, Any]] = queue.Queue()
    
    def worker():
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            # Inject root as first argument for custom dialogs
            res = func(root, *args, **kwargs)
            result_queue.put(("success", res))
        except tk.TclError:
            # User closed/cancelled dialog
            result_queue.put(("cancelled", None))
        except Exception as e:
            result_queue.put(("error", str(e)))
        finally:
            if root:
                try:
                    root.destroy()
                except Exception:
                    pass

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    
    status, payload = result_queue.get()
    if status == "error":
        return _format_response("error", message=payload)
    if status == "cancelled":
        return _format_response("cancelled", message="Dialog was cancelled or closed.")
    return _format_response("success", data=payload)

def _build_custom_modal(root: tk.Tk, title: str, setup: Callable, result_extractor: Callable) -> Any:
    """Helper to build blocking custom modal dialogs."""
    win = tk.Toplevel(root)
    win.title(title)
    win.grab_set()
    win.transient(root)
    win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), root.destroy()))
    
    # Let caller setup widgets
    result_var = setup(win)
    
    win.resizable(False, False)
    win.attributes("-topmost", True)
    
    # Center window
    win.update_idletasks()
    w = win.winfo_width()
    h = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"+{x}+{y}")
    
    win.wait_window(win)
    return result_extractor(result_var, win)

def _parse_filetypes(ft_list: Optional[List]) -> Tuple[Tuple[str, str], ...]:
    """Convert list of filetypes to tkinter tuple format safely."""
    if not ft_list or not isinstance(ft_list, list):
        return (("All Files", "*.*"),)
    parsed = []
    for f in ft_list:
        if isinstance(f, (list, tuple)) and len(f) >= 2:
            parsed.append((str(f[0]), str(f[1])))
    return tuple(parsed) if parsed else (("All Files", "*.*"),)

# -----------------------------------------------------------------------------
# Core Dialog Functions
# -----------------------------------------------------------------------------

def show_info(title: str, message: str) -> Dict:
    return _run_tk_dialog(lambda r: messagebox.showinfo(title, message))

def show_warning(title: str, message: str) -> Dict:
    return _run_tk_dialog(lambda r: messagebox.showwarning(title, message))

def show_error(title: str, message: str) -> Dict:
    return _run_tk_dialog(lambda r: messagebox.showerror(title, message))

def show_question(title: str, message: str) -> Dict:
    return _run_tk_dialog(lambda r: messagebox.askquestion(title, message))

def show_yes_no(title: str, message: str) -> Dict:
    def _job(r): return messagebox.askyesno(title, message)
    return _run_tk_dialog(_job)

def show_ok_cancel(title: str, message: str) -> Dict:
    def _job(r): return messagebox.askokcancel(title, message)
    return _run_tk_dialog(_job)

def show_retry_cancel(title: str, message: str) -> Dict:
    def _job(r): return messagebox.askretrycancel(title, message)
    return _run_tk_dialog(_job)

def input_text(title: str, prompt: str, default: str = "") -> Dict:
    def _job(r): return simpledialog.askstring(title, prompt, initialvalue=default)
    return _run_tk_dialog(_job)

def input_integer(title: str, prompt: str, min_val: int = 0, max_val: int = 100) -> Dict:
    def _job(r): return simpledialog.askinteger(title, prompt, minvalue=min_val, maxvalue=max_val)
    return _run_tk_dialog(_job)

def input_float(title: str, prompt: str) -> Dict:
    def _job(r): return simpledialog.askfloat(title, prompt)
    return _run_tk_dialog(_job)

def input_password(title: str, prompt: str) -> Dict:
    def _setup(win):
        tk.Label(win, text=prompt).pack(padx=20, pady=(20, 5), anchor="w")
        var = tk.StringVar()
        entry = tk.Entry(win, textvariable=var, show="*")
        entry.pack(padx=20, pady=5, fill="x")
        entry.focus_set()
        tk.Button(win, text="OK", command=win.destroy).pack(pady=(10, 20))
        return var

    def _extract(var, win):
        return var.get()

    return _run_tk_dialog(lambda r: _build_custom_modal(r, title, _setup, _extract))

def open_file_dialog(title: str = "Open", filetypes: list = None, initial_dir: str = "") -> Dict:
    def _job(r):
        return filedialog.askopenfilename(
            title=title,
            filetypes=_parse_filetypes(filetypes),
            initialdir=initial_dir if initial_dir else os.path.expanduser("~")
        )
    return _run_tk_dialog(_job)

def save_file_dialog(title: str = "Save", filetypes: list = None, default_ext: str = "") -> Dict:
    def _job(r):
        init_dir = os.path.expanduser("~")
        default_name = f"untitled{default_ext}" if default_ext else "untitled"
        return filedialog.asksaveasfilename(
            title=title,
            filetypes=_parse_filetypes(filetypes),
            defaultextension=default_ext,
            initialfile=default_name,
            initialdir=init_dir
        )
    return _run_tk_dialog(_job)

def open_directory_dialog(title: str = "Select Folder") -> Dict:
    def _job(r): return filedialog.askdirectory(title=title)
    return _run_tk_dialog(_job)

def open_multiple_files(title: str = "Open Files", filetypes: list = None) -> Dict:
    def _job(r):
        res = filedialog.askopenfilenames(
            title=title,
            filetypes=_parse_filetypes(filetypes),
            initialdir=os.path.expanduser("~")
        )
        return list(res) if res else []
    return _run_tk_dialog(_job)

def color_picker(title: str = "Pick Color", initial_color: str = "#ffffff") -> Dict:
    def _job(r):
        res = colorchooser.askcolor(color=initial_color, title=title)
        if res[0]:
            return {"rgb": res[0], "hex": res[1]}
        return None
    return _run_tk_dialog(_job)

def show_progress(title: str, maximum: int = 100) -> Dict:
    win_id = str(uuid.uuid4())
    def _worker():
        root = tk.Tk()
        root.withdraw()
        win = tk.Toplevel(root)
        win.title(title)
        win.resizable(False, False)
        pb = ttk.Progressbar(win, orient="horizontal", length=300, mode="determinate", maximum=maximum)
        pb.pack(padx=20, pady=20, fill="x")
        lbl = tk.Label(win, text="0%")
        lbl.pack(pady=(0, 20))
        
        def update_val(val):
            current = min(max(0, val), maximum)
            pb["value"] = current
            lbl.config(text=f"{int(current)}%")
            win.update_idletasks()
            
        def close():
            win.destroy()
            root.destroy()
            
        win.protocol("WM_DELETE_WINDOW", close)
        
        with _progress_lock:
            _progress_registry[win_id] = {"root": root, "update": root.after(0, lambda: None), "update_func": update_val, "close_func": close}
            
        root.mainloop()

    threading.Thread(target=_worker, daemon=True).start()
    time.sleep(0.2)  # Allow window to render
    return _format_response("success", data={"progress_id": win_id}, message="Progress dialog active.")

def update_progress(value: int) -> Dict:
    with _progress_lock:
        active = list(_progress_registry.values())
    
    if not active:
        return _format_response("error", message="No active progress dialogs found.")
        
    for prog in active:
        try:
            # Schedule on Tk mainloop thread safely
            prog["root"].after(0, prog["update_func"], value)
        except Exception:
            continue
            
    return _format_response("success", message=f"Updated all active progress dialogs to {value}%.")

def show_listbox(title: str, items: list, multi: bool = False) -> Dict:
    def _setup(win):
        frame = tk.Frame(win)
        frame.pack(padx=20, pady=10, fill="both", expand=True)
        mode = tk.SINGLE if not multi else tk.EXTENDED
        lb = tk.Listbox(frame, selectmode=mode, exportselection=False)
        for i in items: lb.insert(tk.END, str(i))
        scroll = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)
        
        var = tk.IntVar()
        def on_select():
            var.set(1)
            win.destroy()
        tk.Button(win, text="Select", command=on_select).pack(pady=10)
        return {"lb": lb, "var": var}

    def _extract(res, win):
        if not res["var"].get(): return []
        selection = [res["lb"].get(i) for i in res["lb"].curselection()]
        return selection

    return _run_tk_dialog(lambda r: _build_custom_modal(r, title, _setup, _extract))

def show_combobox(title: str, options: list, default: str = "") -> Dict:
    def _setup(win):
        var = tk.StringVar(value=default)
        cb = ttk.Combobox(win, textvariable=var, values=options, state="readonly" if default else "normal")
        cb.pack(padx=20, pady=20, fill="x")
        cb.current(options.index(default) if default in options else -1)
        tk.Button(win, text="Select", command=win.destroy).pack(pady=(0, 20))
        return var

    def _extract(var, win):
        return var.get()

    return _run_tk_dialog(lambda r: _build_custom_modal(r, title, _setup, _extract))

def show_checklist(title: str, items: list, checked: list = None) -> Dict:
    checked_set = set(str(c) for c in (checked or []))
    def _setup(win):
        vars_list = []
        for i, item in enumerate(items):
            v = tk.BooleanVar(value=str(item) in checked_set)
            vars_list.append({"val": item, "var": v})
            tk.Checkbutton(win, text=str(item), variable=v, anchor="w").pack(fill="x", padx=20, pady=2)
        tk.Button(win, text="OK", command=win.destroy).pack(pady=20)
        return vars_list

    def _extract(res, win):
        return [r["val"] for r in res if r["var"].get()]

    return _run_tk_dialog(lambda r: _build_custom_modal(r, title, _setup, _extract))

def show_radio_dialog(title: str, options: list, default: int = 0) -> Dict:
    def _setup(win):
        var = tk.IntVar(value=default)
        for i, opt in enumerate(options):
            tk.Radiobutton(win, text=str(opt), variable=var, value=i, anchor="w").pack(fill="x", padx=20, pady=2)
        tk.Button(win, text="Select", command=win.destroy).pack(pady=20)
        return var

    def _extract(var, win):
        return options[var.get()] if 0 <= var.get() < len(options) else None

    return _run_tk_dialog(lambda r: _build_custom_modal(r, title, _setup, _extract))

def show_text_editor(title: str, initial_text: str = "") -> Dict:
    def _setup(win):
        text_widget = tk.Text(win, height=15, width=60)
        text_widget.pack(padx=20, pady=10, fill="both", expand=True)
        text_widget.insert("1.0", initial_text)
        tk.Button(win, text="Save", command=win.destroy).pack(pady=10)
        return text_widget

    def _extract(widget, win):
        return widget.get("1.0", tk.END).strip()

    return _run_tk_dialog(lambda r: _build_custom_modal(r, title, _setup, _extract))

def show_about_dialog(app_name: str, version: str, description: str = "") -> Dict:
    def _setup(win):
        tk.Label(win, text=app_name, font=("Helvetica", 16, "bold")).pack(pady=10)
        tk.Label(win, text=f"Version {version}").pack(pady=2)
        if description:
            msg = tk.Label(win, text=description, justify="center", wraplength=300)
            msg.pack(pady=10)
        tk.Button(win, text="Close", command=win.destroy).pack(pady=10)
        return None

    def _extract(var, win):
        return {"app": app_name, "version": version, "description": description}

    return _run_tk_dialog(lambda r: _build_custom_modal(r, "About", _setup, _extract))

def show_splash_screen(image_path: str = "", duration: int = 3, text: str = "") -> Dict:
    def _worker():
        root = tk.Tk()
        root.withdraw()
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.9)
        
        # Center
        w, h = 400, 250
        x = (win.winfo_screenwidth() // 2) - (w // 2)
        y = (win.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
        
        bg = ttk.Frame(win)
        bg.pack(fill="both", expand=True)
        
        if image_path and os.path.exists(image_path):
            try:
                img = tk.PhotoImage(file=image_path)
                tk.Label(bg, image=img).pack(pady=10)
                # Keep reference
                bg.image_ref = img 
            except Exception:
                tk.Label(bg, text="[Image Load Failed]").pack(pady=10)
                
        if text:
            tk.Label(bg, text=text, font=("Helvetica", 12)).pack(pady=10)
            
        def close_splash():
            win.destroy()
            root.destroy()
            
        win.after(duration * 1000, close_splash)
        win.bind("<Button-1>", lambda e: close_splash())
        
        root.mainloop()

    threading.Thread(target=_worker, daemon=True).start()
    return _format_response("success", message=f"Splash displayed for {duration}s.")