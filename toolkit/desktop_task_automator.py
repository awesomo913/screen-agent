#!/usr/bin/env python3
"""Desktop Task Automator - Visual workflow engine for chaining screen automation steps."""
import os, sys, time, json, argparse
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pyautogui, pyperclip
try:
    import pytesseract; HAS_TESSERACT = True
except ImportError: HAS_TESSERACT = False

@dataclass
class TaskStep:
    id: int; name: str; action: str; params: Dict[str,Any] = field(default_factory=dict)
    on_fail: str = "stop"; delay_after: float = 0.5; retry_count: int = 0; enabled: bool = True

@dataclass
class TaskWorkflow:
    name: str; steps: List[TaskStep] = field(default_factory=list); description: str = ""
    variables: Dict[str,Any] = field(default_factory=dict)

@dataclass
class ExecutionResult:
    workflow_name: str; total_steps: int; completed_steps: int; failed_step: Optional[int] = None
    duration: float = 0; status: str = "success"; step_results: List[Dict] = field(default_factory=list)

class ActionExecutor:
    def __init__(self):
        self.screen_w, self.screen_h = pyautogui.size()
        pyautogui.FAILSAFE = True
        self.variables = {}

    def execute(self, action, params, variables=None):
        if variables: self.variables = variables
        params = self._resolve_vars(params)
        actions = {
            "click": lambda p: (pyautogui.click(p.get("x",0), p.get("y",0), button=p.get("button","left")), True)[1],
            "double_click": lambda p: (pyautogui.doubleClick(p.get("x",0), p.get("y",0)), True)[1],
            "right_click": lambda p: (pyautogui.rightClick(p.get("x",0), p.get("y",0)), True)[1],
            "type_text": self._type_text,
            "press_key": lambda p: (pyautogui.press(p.get("key","enter"), presses=p.get("times",1)), True)[1],
            "hotkey": lambda p: (pyautogui.hotkey(*p.get("keys",[])), True)[1],
            "move_mouse": self._move_mouse,
            "scroll": lambda p: (pyautogui.scroll(p.get("amount",3) if p.get("direction","down")=="up" else -p.get("amount",3)), True)[1],
            "wait": lambda p: (time.sleep(p.get("seconds",1)), True)[1],
            "screenshot": self._screenshot,
            "ocr_read": self._ocr_read,
            "clipboard_copy": self._clipboard_copy,
            "clipboard_paste": lambda p: (pyperclip.copy(p["text"]) if p.get("text") else None, pyautogui.hotkey("ctrl","v"), True)[2],
            "set_variable": lambda p: (self.variables.__setitem__(p.get("name",""), p.get("value","")), True)[1],
            "open_app": self._open_app,
            "open_url": self._open_url,
            "conditional": self._conditional,
            "log": self._log,
            "drag": lambda p: (pyautogui.moveTo(p.get("start_x",0), p.get("start_y",0)), pyautogui.drag(p.get("dx",0), p.get("dy",0), duration=0.5), True)[2],
            "select_all": lambda p: (pyautogui.hotkey("ctrl","a"), True)[1],
            "find_image": self._find_image,
            "wait_for_text": self._wait_for_text,
        }
        handler = actions.get(action)
        if handler: return handler(params)
        raise ValueError("Unknown action: " + action)

    def _resolve_vars(self, params):
        resolved = {}
        for key, val in params.items():
            if isinstance(val, str) and val.startswith("$"):
                resolved[key] = self.variables.get(val[1:], val)
            else:
                resolved[key] = val
        return resolved

    def _type_text(self, p):
        text = p.get("text", "")
        if p.get("use_clipboard"):
            pyperclip.copy(text); pyautogui.hotkey("ctrl","v")
        else:
            pyautogui.typewrite(text, interval=p.get("interval",0.02))
        return True

    def _move_mouse(self, p):
        if p.get("relative"): pyautogui.moveRel(p.get("x",0), p.get("y",0), duration=0.3)
        else: pyautogui.moveTo(p.get("x",0), p.get("y",0), duration=0.3)
        return True

    def _screenshot(self, p):
        path = p.get("path", os.path.expanduser("~/wf_ss_" + datetime.now().strftime("%H%M%S") + ".png"))
        region = p.get("region")
        img = pyautogui.screenshot(region=tuple(region)) if region else pyautogui.screenshot()
        img.save(path); self.variables["last_screenshot"] = path; return True

    def _ocr_read(self, p):
        if not HAS_TESSERACT: return False
        region = p.get("region")
        img = pyautogui.screenshot(region=tuple(region)) if region else pyautogui.screenshot()
        text = pytesseract.image_to_string(img).strip()
        self.variables[p.get("variable","ocr_text")] = text; return True

    def _clipboard_copy(self, p):
        pyautogui.hotkey("ctrl","c"); time.sleep(0.2)
        self.variables["clipboard"] = pyperclip.paste(); return True

    def _open_app(self, p):
        import subprocess
        subprocess.Popen(p.get("app",""), shell=True); time.sleep(p.get("wait",2)); return True

    def _open_url(self, p):
        import webbrowser; webbrowser.open(p.get("url","")); time.sleep(p.get("wait",2)); return True

    def _conditional(self, p):
        actual = str(self.variables.get(p.get("variable",""), ""))
        expected = p.get("expected",""); op = p.get("operator","equals")
        if op == "equals": return actual == expected
        elif op == "contains": return expected in actual
        elif op == "not_empty": return bool(actual)
        return False

    def _log(self, p):
        msg = p.get("message","")
        for vk, vv in self.variables.items(): msg = msg.replace("$" + vk, str(vv))
        print("  [LOG] " + msg); return True

    def _find_image(self, p):
        try:
            loc = pyautogui.locateOnScreen(p.get("template",""), confidence=p.get("confidence",0.8))
            if loc:
                cx, cy = pyautogui.center(loc)
                self.variables["found_x"] = cx; self.variables["found_y"] = cy; return True
        except: pass
        return False

    def _wait_for_text(self, p):
        if not HAS_TESSERACT: return False
        target = p.get("text","").lower(); timeout = p.get("timeout",30)
        region = p.get("region"); start = time.time()
        while time.time() - start < timeout:
            img = pyautogui.screenshot(region=tuple(region)) if region else pyautogui.screenshot()
            if target in pytesseract.image_to_string(img).lower(): return True
            time.sleep(1)
        return False

class WorkflowEngine:
    def __init__(self, config_path=None):
        self.config_path = config_path or os.path.expanduser("~/.workflow_engine_config.json")
        self.workflows = {}
        self.executor = ActionExecutor()
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path,"r") as f: cfg = json.load(f)
            for name, wdata in cfg.get("workflows",{}).items():
                steps = [TaskStep(**s) for s in wdata.get("steps",[])]
                self.workflows[name] = TaskWorkflow(name=name, steps=steps, description=wdata.get("description",""), variables=wdata.get("variables",{}))

    def save_config(self):
        cfg = {"workflows":{}}
        for name, wf in self.workflows.items():
            cfg["workflows"][name] = {"description":wf.description, "variables":wf.variables,
                "steps":[{"id":s.id,"name":s.name,"action":s.action,"params":s.params,
                          "on_fail":s.on_fail,"delay_after":s.delay_after,"retry_count":s.retry_count,"enabled":s.enabled} for s in wf.steps]}
        with open(self.config_path,"w") as f: json.dump(cfg,f,indent=2)

    def create_workflow(self, name, desc=""):
        self.workflows[name] = TaskWorkflow(name=name, description=desc)
        self.save_config(); print("Created: " + name)

    def add_step(self, wf_name, name, action, params=None, on_fail="stop", delay=0.5):
        wf = self.workflows.get(wf_name)
        if not wf: print("Not found: " + wf_name); return
        step = TaskStep(id=len(wf.steps)+1, name=name, action=action, params=params or {}, on_fail=on_fail, delay_after=delay)
        wf.steps.append(step); self.save_config()
        print("Added step #" + str(step.id) + ": " + name)

    def run_workflow(self, name, variables=None):
        wf = self.workflows.get(name)
        if not wf: print("Not found"); return
        print("\nRunning: " + name + " (" + str(len(wf.steps)) + " steps)")
        start = time.time()
        self.executor.variables = dict(list(wf.variables.items()) + list((variables or {}).items()))
        result = ExecutionResult(workflow_name=name, total_steps=len(wf.steps), completed_steps=0)
        for step in wf.steps:
            if not step.enabled: continue
            print("  Step #" + str(step.id) + ": " + step.name + " (" + step.action + ")")
            success = False
            for attempt in range(step.retry_count + 1):
                try:
                    success = self.executor.execute(step.action, step.params, self.executor.variables)
                    if success: break
                except Exception as e:
                    print("    Error: " + str(e))
                    if attempt < step.retry_count: time.sleep(1)
            result.step_results.append({"id":step.id,"name":step.name,"success":success})
            if success: result.completed_steps += 1; time.sleep(step.delay_after)
            else:
                if step.on_fail == "stop": result.status = "failed"; result.failed_step = step.id; break
        result.duration = round(time.time()-start, 1)
        if result.status != "failed": result.status = "success"
        print("\nResult: " + result.status + " (" + str(result.completed_steps) + "/" + str(result.total_steps) + " in " + str(result.duration) + "s)")
        return result

    def export_workflow(self, name, path):
        wf = self.workflows.get(name)
        if not wf: return
        data = {"name":wf.name,"description":wf.description,"variables":wf.variables,
                "steps":[{"id":s.id,"name":s.name,"action":s.action,"params":s.params,"on_fail":s.on_fail,"delay_after":s.delay_after} for s in wf.steps]}
        with open(path,"w") as f: json.dump(data,f,indent=2)
        print("Exported: " + path)

    def import_workflow(self, path):
        with open(path,"r") as f: data = json.load(f)
        wf = TaskWorkflow(name=data["name"], description=data.get("description",""), variables=data.get("variables",{}))
        for s in data.get("steps",[]): wf.steps.append(TaskStep(**s))
        self.workflows[data["name"]] = wf; self.save_config()
        print("Imported: " + data["name"])

def main():
    parser = argparse.ArgumentParser(description="Desktop Task Automator")
    parser.add_argument("--config")
    subparsers = parser.add_subparsers(dest="command")
    c = subparsers.add_parser("create"); c.add_argument("name"); c.add_argument("--desc",default="")
    a = subparsers.add_parser("add-step"); a.add_argument("workflow"); a.add_argument("name")
    a.add_argument("action"); a.add_argument("--params"); a.add_argument("--on-fail",default="stop")
    r = subparsers.add_parser("run"); r.add_argument("name"); r.add_argument("--vars")
    subparsers.add_parser("list")
    s = subparsers.add_parser("show"); s.add_argument("name")
    e = subparsers.add_parser("export"); e.add_argument("name"); e.add_argument("output")
    i = subparsers.add_parser("import-wf"); i.add_argument("path")
    args = parser.parse_args()
    engine = WorkflowEngine(config_path=args.config)
    if args.command == "create": engine.create_workflow(args.name, args.desc)
    elif args.command == "add-step":
        params = json.loads(args.params) if args.params else {}
        engine.add_step(args.workflow, args.name, args.action, params, args.on_fail)
    elif args.command == "run":
        vs = json.loads(args.vars) if args.vars else {}
        engine.run_workflow(args.name, vs)
    elif args.command == "list":
        for n,w in engine.workflows.items(): print("  " + n + ": " + w.description + " (" + str(len(w.steps)) + " steps)")
    elif args.command == "show":
        w = engine.workflows.get(args.name)
        if w:
            print("Workflow: " + w.name)
            for st in w.steps: print("  #" + str(st.id) + ": " + st.name + " [" + st.action + "]")
    elif args.command == "export": engine.export_workflow(args.name, args.output)
    elif args.command == "import-wf": engine.import_workflow(args.path)
    else: parser.print_help()

if __name__ == "__main__":
    main()
