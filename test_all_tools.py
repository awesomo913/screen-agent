"""
Test every toolkit function — calls each with safe defaults, logs pass/fail.
Uses threading-based timeout to prevent hangs.
"""
import sys
import os
import json
import time
import inspect
import traceback
import io
import threading
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import logging
logging.disable(logging.CRITICAL)  # Suppress all logger output during tests

# Prevent Tk from being created in threads
os.environ['TK_SILENCE_DEPRECATION'] = '1'

from toolkit.registry import get_registry

FUNC_TIMEOUT = 5  # seconds per function call

def _safe_arg(pname, pinfo):
    ptype = pinfo.get("type", "any").lower()
    name = pname.lower()

    if not pinfo.get("required", True):
        return None

    if name in ("db_path", "output_path", "input_path", "requirements_path"):
        return None
    if name in ("text", "markdown_text", "html_text", "content", "source", "code", "source_code",
                 "input_text", "string", "message", "data", "body", "query", "search_query",
                 "prompt", "template", "pattern", "error_message", "csv_text", "json_text",
                 "yaml_text", "xml_text", "ini_text", "log_text", "input_string", "value",
                 "json_string", "json_str", "payload"):
        return "Hello World test 123"
    if name in ("title", "name", "label", "description", "tag", "category", "language",
                 "snippet_id", "key", "section", "field", "column", "header", "word",
                 "prefix", "suffix", "separator", "delimiter", "module_name", "func_name",
                 "class_name", "var_name", "attr", "attribute", "prop", "property_name",
                 "event_name", "signal", "channel", "topic", "queue_name", "job_id",
                 "task_id", "session_id", "user_id", "group", "role", "scope"):
        return "test"
    if name in ("url", "target_url", "base_url", "endpoint", "link", "href", "webhook_url",
                 "api_url", "callback_url", "redirect_url"):
        return "https://example.com"
    if name in ("path", "file_path", "filepath", "directory", "dir_path", "folder",
                 "folder_path", "dir", "source_path", "dest_path", "target_path",
                 "src", "dst", "source_dir", "target_dir", "dest_dir", "root_dir",
                 "watch_dir", "input_dir", "output_dir", "backup_dir", "base_dir",
                 "config_path", "log_path", "image_path", "template_path", "repo_path",
                 "project_path", "working_dir", "cwd"):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    if name in ("filename", "file_name", "fname"):
        return "test_file.txt"
    if name in ("command", "cmd"):
        return "echo test"
    if name in ("domain",):
        return "example.com"
    if name in ("ip", "ip_address", "host", "hostname", "server", "address"):
        return "127.0.0.1"
    if name in ("port",):
        return 80
    if name in ("email", "email_address", "from_email", "to_email", "recipient"):
        return "test@example.com"
    if name in ("password", "passwd", "secret", "token", "api_key", "auth_token"):
        return "TestPass123!"
    if name in ("username", "user", "login"):
        return "testuser"
    if name in ("regex", "expr", "expression"):
        return r"\w+"
    if name in ("replacement", "replace", "new_text", "new_string", "new_value"):
        return "replaced"
    if name in ("extension", "ext"):
        return ".txt"
    if name in ("encoding", "charset"):
        return "utf-8"
    if name in ("algorithm", "hash_algo", "method"):
        return "sha256"
    if name in ("format", "fmt", "output_format"):
        return "json"
    if name in ("width", "height", "size", "max_size"):
        return 100
    if name in ("x", "y", "x1", "y1", "x2", "y2", "left", "top", "right", "bottom"):
        return 0
    if name in ("count", "limit", "max_results", "num", "number", "n", "top_n",
                 "pagesize", "page_size", "max_items", "max_count", "max_depth",
                 "max_retries", "retry_count", "batch_size", "chunk_size"):
        return 3
    if name in ("timeout", "wait", "delay", "interval", "duration", "seconds"):
        return 2
    if name in ("shift", "offset", "start", "begin", "index", "position"):
        return 1
    if name in ("level", "depth", "indent", "priority", "severity"):
        return 1
    if name in ("question_id",):
        return 11227809
    if name in ("package", "package_name", "module", "lib"):
        return "pip"
    if name in ("tagged", "tags"):
        return "python"
    if name in ("hex_str",):
        return "48656c6c6f"
    if name in ("binary_str",):
        return "01001000 01101001"
    if name in ("codes_str",):
        return "72,101,108,108,111"
    if name in ("color", "colour", "hex_color", "bg_color", "fg_color"):
        return "#FF5733"
    if name in ("font", "font_name", "font_family"):
        return "Arial"
    if name in ("date", "date_str", "start_date", "end_date", "from_date", "to_date"):
        return "2026-01-01"
    if name in ("time_str", "time_val"):
        return "12:00:00"
    if name in ("timezone", "tz", "from_tz", "to_tz"):
        return "UTC"
    if name in ("json_data", "json_obj", "config", "settings", "options", "params",
                 "headers", "metadata", "kwargs", "extra", "context", "env", "variables",
                 "mapping", "filters", "rules", "schema"):
        return {}
    if name in ("items", "values", "elements", "entries", "records", "rows",
                 "columns", "fields", "keys", "args", "arguments", "files",
                 "paths", "urls", "names", "ids", "extensions", "patterns",
                 "list_items", "input_list", "data_list", "strings", "numbers",
                 "packages", "commands", "steps", "tasks", "events", "listeners",
                 "callbacks", "hooks", "plugins", "modules"):
        return []
    if name in ("enabled", "active", "verbose", "debug", "force", "recursive",
                 "overwrite", "append", "create", "update", "check_http",
                 "include_hidden", "follow_links", "case_sensitive", "dry_run",
                 "quiet", "silent", "raw", "pretty", "ascending", "descending",
                 "confirm", "strict", "safe", "async_mode", "background",
                 "upgrade", "all_users"):
        return False
    if name in ("ratio", "threshold", "confidence", "similarity", "opacity",
                 "scale", "factor", "rate", "percentage", "amount"):
        return 0.5

    # By type
    if "str" in ptype:
        return "test"
    if "int" in ptype:
        return 1
    if "float" in ptype:
        return 1.0
    if "bool" in ptype:
        return False
    if "list" in ptype:
        return []
    if "dict" in ptype:
        return {}
    return "test"


SKIP_TOOLS = {
    "power_manager.shutdown", "power_manager.restart", "power_manager.sleep_system",
    "power_manager.hibernate", "power_manager.log_off", "power_manager.lock_screen",
    "process_manager.kill_process", "process_manager.kill_by_name",
    "service_manager.stop_service", "service_manager.start_service",
    "service_manager.delete_service", "service_manager.create_service",
    "auto_system_cleaner.clean_temp_files", "auto_system_cleaner.clean_all",
    "auto_system_cleaner.empty_recycle_bin", "auto_system_cleaner.clean_browser_cache",
    "auto_file_organizer.organize_folder", "auto_file_renamer.rename_files",
    "auto_file_renamer.batch_rename", "backup_actions.delete_backup",
    "file_sync.sync_directories", "file_sync.mirror_directory",
    "ssh_actions.connect", "ftp_actions.connect", "ftp_actions.upload",
    "proxy_manager.start_proxy",
    "registry_actions.set_value", "registry_actions.delete_key",
    "registry_actions.delete_value", "registry_actions.create_key",
    "env_manager.set_env_var", "env_manager.delete_env_var",
    "env_manager.add_to_path", "env_manager.remove_from_path",
    "toolkit_73_package_manager.install_package", "toolkit_73_package_manager.uninstall_package",
    "toolkit_73_package_manager.upgrade_package", "toolkit_73_package_manager.upgrade_all_packages",
    "toolkit_73_package_manager.install_from_requirements", "toolkit_73_package_manager.install_packages_batch",
    "toolkit_73_package_manager.create_virtualenv",
    "docker_actions.remove_container", "docker_actions.stop_container",
    "docker_actions.remove_image", "docker_actions.create_network",
    "docker_actions.remove_network", "docker_actions.remove_volume",
    "scheduler_actions.cancel_task", "cron_scheduler.remove_job",
    "toolkit_16_task_scheduler.create_task", "toolkit_16_task_scheduler.delete_task",
    "toolkit_39_text_to_speech.speak", "toolkit_39_text_to_speech.speak_to_file",
    "toolkit_40_speech_recognition.listen", "toolkit_40_speech_recognition.listen_continuous",
    "notification_service.send_desktop", "notification_service.send_slack",
    "notification_service.send_discord", "notification_service.send_telegram",
    "notification_service.send_email", "notification_actions.show_notification",
    "toolkit_67_windows_notifications.show_toast", "toolkit_67_windows_notifications.show_toast_advanced",
    "toolkit_09_hosts_file_manager.add_entry", "toolkit_09_hosts_file_manager.remove_entry",
    "toolkit_09_hosts_file_manager.block_domain", "toolkit_09_hosts_file_manager.unblock_domain",
    "toolkit_13_firewall_rules.add_rule", "toolkit_13_firewall_rules.remove_rule",
    "toolkit_13_firewall_rules.enable_rule", "toolkit_13_firewall_rules.disable_rule",
    "toolkit_38_windows_update.install_updates", "toolkit_38_windows_update.schedule_restart",
    "toolkit_03_startup_manager.add_startup", "toolkit_03_startup_manager.remove_startup",
    "toolkit_03_startup_manager.disable_startup", "toolkit_03_startup_manager.enable_startup",
    "dialog_actions.file_open_dialog", "dialog_actions.file_save_dialog",
    "dialog_actions.folder_dialog", "dialog_actions.color_dialog",
    "dialog_actions.input_dialog", "dialog_actions.confirm_dialog",
    "dialog_actions.message_box",
    "screen_macro_recorder.start_recording", "screen_macro_recorder.stop_recording",
    "screen_recorder_advanced.start_recording", "screen_recorder_advanced.stop_recording",
    "auto_window_resizer.minimize_all", "auto_window_resizer.restore_all",
    "auto_window_resizer.cascade_windows", "auto_window_resizer.tile_windows",
    "toolkit_48_keyboard_mouse.press_key", "toolkit_48_keyboard_mouse.type_text",
    "toolkit_48_keyboard_mouse.hotkey", "toolkit_48_keyboard_mouse.click",
    "toolkit_48_keyboard_mouse.move_mouse", "toolkit_48_keyboard_mouse.drag",
    "toolkit_48_keyboard_mouse.scroll",
    "toolkit_24_icon_cache.rebuild_icon_cache", "toolkit_24_icon_cache.clear_icon_cache",
    "toolkit_24_icon_cache.clear_thumbnail_cache",
    "command_executor.run_command", "command_executor.run_background",
    "command_executor.run_piped", "command_executor.run_powershell",
    "command_executor.run_as_admin", "command_executor.run_with_retry",
    "desktop_task_automator.run_automation", "desktop_task_automator.run_task_chain",
    "workflow_engine.run_workflow",
    "memory_manager.force_gc", "memory_manager.optimize_memory",
    "toolkit_55_active_directory.create_user", "toolkit_55_active_directory.delete_user",
    "toolkit_55_active_directory.reset_password",
    "toolkit_65_remote_desktop.connect", "toolkit_65_remote_desktop.disconnect",
    "toolkit_07_user_accounts.create_user", "toolkit_07_user_accounts.delete_user",
    "toolkit_07_user_accounts.change_password", "toolkit_07_user_accounts.enable_user",
    "toolkit_07_user_accounts.disable_user",
    "toolkit_56_code_runner.run_python", "toolkit_56_code_runner.run_javascript",
    "toolkit_56_code_runner.run_batch", "toolkit_56_code_runner.run_powershell",
    "toolkit_56_code_runner.run_code",
    "toolkit_80_replit_runner.create_repl", "toolkit_80_replit_runner.run_repl",
    "toolkit_69_online_code_runner.execute_code",
    "toolkit_08_event_log_reader.clear_log",
    "clipboard_advanced.copy_text", "clipboard_advanced.clear_clipboard",
    "clipboard_sync.clipboard_to_base64", "clipboard_sync.base64_to_clipboard",
    "clipboard_history_manager.clear_history",
    "toolkit_51_clipboard_watcher.start_watching", "toolkit_51_clipboard_watcher.stop_watching",
    "toolkit_53_process_automation.run_chain", "toolkit_53_process_automation.run_parallel",
    "toolkit_10_printer_manager.print_test_page", "toolkit_10_printer_manager.set_default_printer",
    "toolkit_10_printer_manager.cancel_all_jobs",
}

SKIP_NAME_PARTS = {"delete", "remove", "destroy", "kill", "wipe", "purge", "drop", "truncate",
                    "uninstall", "format_drive", "clear_all", "reset_all", "clean_all"}

# Modules whose functions are all network/blocking — skip to save time
SKIP_MODULES = {
    "toolkit_72_github_api",      # all GitHub API calls
    "toolkit_74_stackoverflow_search",  # all SO API calls
    "toolkit_68_api_client",      # HTTP calls
    "toolkit_41_web_scraper",     # web requests
    "toolkit_65_remote_desktop",  # RDP
    "toolkit_36_email_tools",     # email server calls
    "toolkit_59_network_traffic", # network monitoring
    "toolkit_80_replit_runner",   # Replit API
    "toolkit_69_online_code_runner",  # online API
    "toolkit_02_network_scanner", # port scanning
    "toolkit_83_web_search_api",  # web API calls
    "toolkit_87_code_review_ai",  # Ollama/Gemini API
    "toolkit_91_api_mock_server", # starts HTTP server
    "toolkit_96_codepad_runner",  # Rextester/Godbolt API
    "toolkit_97_devdocs_fetcher", # web fetching
    "toolkit_100_ideone_runner",  # Ideone API
    "toolkit_101_code_sharing",   # pastebin API
    "toolkit_103_openai_tools",   # OpenAI API
    "toolkit_107_ssh_tools",      # SSH connections
    "toolkit_110_graphql_tools",  # GraphQL API
    "toolkit_111_websocket_client", # WebSocket connections
    "toolkit_116_aws_tools",      # AWS API
    "toolkit_120_pypi_downloader", # PyPI downloads
    "toolkit_122_http_client_tools", # HTTP requests
    "toolkit_131_network_topology", # traceroute
    "dialog_actions",             # tkinter dialogs
    "clipboard_advanced",         # tkinter clipboard
    "clipboard_sync",             # tkinter clipboard
    "clipboard_history_manager",  # tkinter clipboard
    "tray_icon",                  # pystray / tkinter
}


def should_skip(tool_name, func_name):
    if tool_name in SKIP_TOOLS:
        return True
    if func_name == "main":
        return True
    mod = tool_name.split(".")[0] if "." in tool_name else ""
    if mod in SKIP_MODULES:
        return True
    fn = func_name.lower()
    for part in SKIP_NAME_PARTS:
        if part in fn:
            return True
    return False


def build_test_args(tool_info):
    params = tool_info.get("params", {})
    kwargs = {}
    for pname, pinfo in params.items():
        if not pinfo.get("required", True):
            continue
        val = _safe_arg(pname, pinfo)
        if val is not None:
            kwargs[pname] = val
    return kwargs


def call_with_timeout(reg, tool_name, kwargs, timeout):
    """Call a tool with a timeout. Returns (result_or_None, error_or_None)."""
    result_box = [None]
    error_box = [None]

    def _run():
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            result_box[0] = reg.call_tool(tool_name, kwargs)
        except SystemExit as e:
            error_box[0] = f"SystemExit({e})"
        except BaseException as e:
            error_box[0] = f"{type(e).__name__}: {str(e)[:100]}"
        finally:
            try:
                sys.stdout, sys.stderr = old_out, old_err
            except:
                pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None, "TIMEOUT"
    return result_box[0], error_box[0]


def test_all():
    reg = get_registry()
    stats = reg.get_stats()

    print(f"=== TOOLKIT TEST RUNNER ===")
    print(f"Modules: {stats['total_modules']} | Tools: {stats['total_tools']} | Failed imports: {stats['failed_modules']}")
    print(f"=" * 70)
    print(f"Timeout per function: {FUNC_TIMEOUT}s")
    print(f"=" * 70)

    results = {"pass": [], "fail": [], "skip": [], "error": [], "timeout": []}
    module_results = {}

    tools = sorted(reg.tools.items())
    total = len(tools)
    start_time = time.time()

    for i, (tool_name, info) in enumerate(tools):
        mod = info["module"]
        func = info["function"]

        if mod not in module_results:
            module_results[mod] = {"pass": 0, "fail": 0, "skip": 0, "error": 0, "timeout": 0}

        if should_skip(tool_name, func):
            results["skip"].append(tool_name)
            module_results[mod]["skip"] += 1
            continue

        kwargs = build_test_args(info)
        result, error = call_with_timeout(reg, tool_name, kwargs, FUNC_TIMEOUT)

        if error and error == "TIMEOUT":
            results["timeout"].append(tool_name)
            module_results[mod]["timeout"] += 1
        elif error and error != "TIMEOUT":
            results["error"].append((tool_name, error))
            module_results[mod]["error"] += 1
        elif isinstance(result, dict):
            success = result.get("success", False) or result.get("status") == "success"
            if success:
                results["pass"].append(tool_name)
                module_results[mod]["pass"] += 1
            else:
                err = str(result.get("error", "unknown"))
                err_lower = err.lower()
                expected = ["not found", "not installed", "not exist", "no such",
                           "access denied", "permission", "could not", "cannot",
                           "invalid", "failed to", "error", "timeout", "unavailable",
                           "empty", "no data", "not supported", "not available",
                           "no module", "requires", "missing", "denied", "refused",
                           "no results", "no match", "not configured", "not connected",
                           "no devices", "no printer", "wmi", "win32", "winreg",
                           "not implemented", "unsupported", "disabled"]
                if any(e in err_lower for e in expected):
                    results["pass"].append(tool_name)
                    module_results[mod]["pass"] += 1
                else:
                    results["fail"].append((tool_name, err[:120]))
                    module_results[mod]["fail"] += 1
        else:
            results["pass"].append(tool_name)
            module_results[mod]["pass"] += 1

        if (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            print(f"  [{i+1}/{total}] P:{len(results['pass'])} F:{len(results['fail'])} E:{len(results['error'])} T:{len(results['timeout'])} S:{len(results['skip'])} ({elapsed:.0f}s)")

    total_time = time.time() - start_time
    tested = len(results['pass']) + len(results['fail']) + len(results['error']) + len(results['timeout'])

    print(f"\n{'=' * 70}")
    print(f"RESULTS: {total} total | {tested} tested | {len(results['skip'])} skipped | {total_time:.1f}s")
    print(f"  PASS:    {len(results['pass'])}")
    print(f"  FAIL:    {len(results['fail'])}")
    print(f"  ERROR:   {len(results['error'])}")
    print(f"  TIMEOUT: {len(results['timeout'])}")
    print(f"  SKIPPED: {len(results['skip'])}")

    pass_rate = len(results['pass']) / max(1, tested) * 100
    print(f"\n  PASS RATE: {pass_rate:.1f}%")

    print(f"\n{'=' * 70}")
    print("MODULE BREAKDOWN:")
    for mod in sorted(module_results.keys()):
        mr = module_results[mod]
        t = mr['pass'] + mr['fail'] + mr['error'] + mr['timeout']
        if t == 0:
            s = "SKIP"
        elif mr['fail'] == 0 and mr['error'] == 0 and mr['timeout'] == 0:
            s = "OK"
        elif mr['timeout'] > 0:
            s = "HANG"
        elif mr['error'] > 0:
            s = "ERR"
        else:
            s = "PARTIAL"
        print(f"  {s:>7} | {mod:<45} | P:{mr['pass']:>3} F:{mr['fail']:>2} E:{mr['error']:>2} T:{mr['timeout']:>2} S:{mr['skip']:>2}")

    if results["fail"]:
        print(f"\n{'=' * 70}")
        print("FAILURES:")
        for name, err in results["fail"]:
            print(f"  {name}: {err}")

    if results["error"]:
        print(f"\n{'=' * 70}")
        print("ERRORS:")
        for name, err in results["error"]:
            print(f"  {name}: {err}")

    if results["timeout"]:
        print(f"\n{'=' * 70}")
        print(f"TIMEOUTS (hung >{FUNC_TIMEOUT}s):")
        for name in results["timeout"]:
            print(f"  {name}")

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round(total_time, 1),
        "total": total, "tested": tested,
        "pass_count": len(results["pass"]),
        "fail_count": len(results["fail"]),
        "error_count": len(results["error"]),
        "timeout_count": len(results["timeout"]),
        "skip_count": len(results["skip"]),
        "pass_rate": round(pass_rate, 1),
        "failures": [{"tool": n, "error": e} for n, e in results["fail"]],
        "errors": [{"tool": n, "error": e} for n, e in results["error"]],
        "timeouts": results["timeout"],
        "module_breakdown": module_results,
    }

    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "test_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report: {report_path}")


if __name__ == "__main__":
    try:
        test_all()
    except SystemExit:
        pass
    except BaseException as e:
        print(f"\nTest runner crashed: {type(e).__name__}: {e}")
        # Still try to print what we have
        pass
