"""
Toolkit Registry - Auto-discovers and provides access to all toolkit modules.
Gracefully skips modules with missing dependencies.
"""

import importlib
import inspect
import os
import sys
import json
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Category mapping for toolkit modules
MODULE_CATEGORIES = {
    "clipboard_advanced": "Clipboard", "clipboard_sync": "Clipboard",
    "mouse_actions": "Input Control", "hotkey_actions": "Input Control",
    "screenshot_manager": "Screen", "image_processing": "Image",
    "color_actions": "Image",
    "http_client": "Network", "web_scraping_advanced": "Network",
    "websocket_actions": "Network", "dns_actions": "Network",
    "proxy_manager": "Network", "ftp_actions": "Network",
    "ssh_actions": "Network", "web_auth": "Network",
    "process_manager": "System", "power_manager": "System",
    "service_manager": "System", "system_monitor": "System",
    "env_manager": "System", "registry_actions": "System",
    "file_watcher": "Files", "backup_actions": "Files",
    "compression_actions": "Files",
    "database_orm": "Data", "cache_manager": "Data",
    "migration_actions": "Data", "json_validator": "Data",
    "excel_actions": "Data", "csv_actions": "Data",
    "text_processing": "Text", "markdown_actions": "Text",
    "html_parser": "Text", "xml_actions": "Text",
    "template_engine": "Text", "regex_actions": "Text",
    "pdf_actions": "Documents", "form_filler": "Documents",
    "encryption_actions": "Security", "string_encryption": "Security",
    "date_time_actions": "DateTime", "calendar_actions": "DateTime",
    "cron_scheduler": "Scheduling", "scheduler_actions": "Scheduling",
    "notification_actions": "Notifications", "dialog_actions": "UI",
    "tray_icon": "UI", "browser_profile_manager": "Browser",
    "qr_code_actions": "QR Code", "audio_actions": "Audio",
    "docker_actions": "Docker", "workflow_engine": "Automation",
    "event_system": "Automation", "testing_e2e": "Testing",
    "window_manager_advanced": "Windows",
    "screen_macro_recorder": "Automation",
    "screen_ocr_extractor": "Screen",
    "auto_file_organizer": "Files",
    "desktop_task_automator": "Automation",
    "screen_template_matcher": "Screen",
    "auto_system_cleaner": "System",
    "auto_file_renamer": "Files",
    "screen_ocr_batch": "Screen",
    "auto_data_entry": "Automation",
    "auto_window_resizer": "Windows",
    "auto_sound_controller": "Audio",
    "clipboard_history_manager": "Clipboard",
    "clipboard_image_tools": "Clipboard",
    "browser_control": "Browser",
    "window_control": "Windows",
    "desktop_control": "Windows",
    "display_gamma": "Screen",
    "wifi_tools": "Network",
    "print_queue": "Documents",
    "screen_color_analyzer": "Screen",
    "auto_screenshot_organizer": "Screen",
    "csv_advanced": "Data",
    "data_validation": "Data",
    "diff_patch": "Text",
    "file_metadata": "Files",
    "git_actions": "DevTools",
    "log_analyzer": "DevTools",
    "url_parser": "Network",
    "yaml_actions": "Data",
    "zip_archive": "Files",
    "data_pipeline": "Data",
    "pixel_color_actions": "Screen",
    "ini_config": "Data",
    "performance_profiler": "System",
    "command_executor": "System",
    "chart_generator": "Data",
    "accessibility_checker": "Automation",
    "screen_recorder_advanced": "Screen",
    "file_sync": "Files",
    "memory_manager": "System",
    "notification_service": "Notifications",
    # ── toolkit_01–toolkit_80 ──
    "toolkit_01_font_inspector": "System",
    "toolkit_02_network_scanner": "Network",
    "toolkit_03_startup_manager": "System",
    "toolkit_04_disk_health": "System",
    "toolkit_05_display_manager": "System",
    "toolkit_06_installed_apps": "System",
    "toolkit_07_user_accounts": "System",
    "toolkit_08_event_log_reader": "System",
    "toolkit_09_hosts_file_manager": "Network",
    "toolkit_10_printer_manager": "System",
    "toolkit_11_usb_devices": "System",
    "toolkit_12_audio_devices": "Audio",
    "toolkit_13_firewall_rules": "Security",
    "toolkit_14_certificate_store": "Security",
    "toolkit_15_network_shares": "Network",
    "toolkit_16_task_scheduler": "Scheduling",
    "toolkit_17_power_plans": "System",
    "toolkit_18_math_tools": "Data",
    "toolkit_19_string_tools": "Text",
    "toolkit_20_file_permissions": "Files",
    "toolkit_21_bluetooth_devices": "System",
    "toolkit_22_shortcut_inspector": "Files",
    "toolkit_23_windows_search": "Files",
    "toolkit_24_icon_cache": "System",
    "toolkit_25_process_memory": "System",
    "toolkit_26_network_diagnostics": "Network",
    "toolkit_27_image_metadata": "Image",
    "toolkit_28_environment_scanner": "System",
    "toolkit_29_window_inspector": "Windows",
    "toolkit_30_system_tray": "UI",
    "toolkit_31_file_hash": "Files",
    "toolkit_32_pdf_tools": "Documents",
    "toolkit_33_qr_barcode": "QR Code",
    "toolkit_34_word_excel": "Documents",
    "toolkit_35_color_picker": "Image",
    "toolkit_36_email_tools": "Network",
    "toolkit_37_hardware_info": "System",
    "toolkit_38_windows_update": "System",
    "toolkit_39_text_to_speech": "Audio",
    "toolkit_40_speech_recognition": "Audio",
    "toolkit_41_web_scraper": "Network",
    "toolkit_42_data_export": "Data",
    "toolkit_43_sqlite_manager": "Data",
    "toolkit_44_media_info": "Audio",
    "toolkit_45_virtual_desktop": "Windows",
    "toolkit_46_password_tools": "Security",
    "toolkit_47_app_launcher": "Automation",
    "toolkit_48_keyboard_mouse": "Input Control",
    "toolkit_49_json_tools": "Data",
    "toolkit_50_date_utils": "DateTime",
    "toolkit_51_clipboard_watcher": "Clipboard",
    "toolkit_52_image_converter": "Image",
    "toolkit_53_process_automation": "Automation",
    "toolkit_54_archive_inspector": "Files",
    "toolkit_55_active_directory": "System",
    "toolkit_56_code_runner": "DevTools",
    "toolkit_57_file_watcher_advanced": "Files",
    "toolkit_58_ocr_advanced": "Screen",
    "toolkit_59_network_traffic": "Network",
    "toolkit_60_system_health": "System",
    "toolkit_61_git_tools_advanced": "DevTools",
    "toolkit_62_text_analyzer": "Text",
    "toolkit_63_screen_capture_advanced": "Screen",
    "toolkit_64_productivity_timer": "Automation",
    "toolkit_65_remote_desktop": "Network",
    "toolkit_66_data_visualizer": "Data",
    "toolkit_67_windows_notifications": "Notifications",
    "toolkit_68_api_client": "Network",
    "toolkit_69_online_code_runner": "DevTools",
    "toolkit_70_code_formatter": "DevTools",
    "toolkit_71_code_linter": "DevTools",
    "toolkit_72_github_api": "DevTools",
    "toolkit_73_package_manager": "DevTools",
    "toolkit_74_stackoverflow_search": "DevTools",
    "toolkit_75_code_snippet_manager": "DevTools",
    "toolkit_76_string_encoding": "Text",
    "toolkit_77_markdown_tools": "Text",
    "toolkit_78_docstring_generator": "DevTools",
    "toolkit_79_code_complexity": "DevTools",
    "toolkit_80_replit_runner": "DevTools",
    # ── toolkit_81–toolkit_99 ──
    "toolkit_81_unit_test_generator": "DevTools",
    "toolkit_82_regex_builder": "DevTools",
    "toolkit_83_web_search_api": "Network",
    "toolkit_84_code_converter": "DevTools",
    "toolkit_85_algorithm_tools": "Data",
    "toolkit_86_leetcode_helper": "DevTools",
    "toolkit_87_code_review_ai": "DevTools",
    "toolkit_88_jupyter_tools": "DevTools",
    "toolkit_89_html_generator": "Text",
    "toolkit_91_api_mock_server": "Network",
    "toolkit_92_git_workflow": "DevTools",
    "toolkit_93_project_scaffolder": "DevTools",
    "toolkit_94_data_structure_visualizer": "DevTools",
    "toolkit_95_dependency_analyzer": "DevTools",
    "toolkit_96_codepad_runner": "DevTools",
    "toolkit_97_devdocs_fetcher": "DevTools",
    "toolkit_98_language_server_client": "DevTools",
    "toolkit_99_code_metrics_dashboard": "DevTools",
    # ── toolkit_100–toolkit_108 ──
    "toolkit_100_ideone_runner": "DevTools",
    "toolkit_101_code_sharing": "DevTools",
    "toolkit_102_json_schema_tools": "Data",
    "toolkit_103_openai_tools": "DevTools",
    "toolkit_104_terminal_ui": "UI",
    "toolkit_105_file_template_engine": "Files",
    "toolkit_106_code_diff_tools": "DevTools",
    "toolkit_107_ssh_tools": "Network",
    "toolkit_108_docker_tools": "DevTools",
    # ── toolkit_109–toolkit_125 ──
    "toolkit_109_swagger_openapi": "DevTools",
    "toolkit_110_graphql_tools": "Network",
    "toolkit_111_websocket_client": "Network",
    "toolkit_112_database_tools": "Data",
    "toolkit_113_file_watcher_api": "Files",
    "toolkit_114_celery_tasks": "Automation",
    "toolkit_115_redis_tools": "Data",
    "toolkit_116_aws_tools": "Network",
    "toolkit_117_performance_tools": "DevTools",
    "toolkit_118_code_search": "DevTools",
    "toolkit_119_ast_transformer": "DevTools",
    "toolkit_120_pypi_downloader": "DevTools",
    "toolkit_121_code_obfuscator": "DevTools",
    "toolkit_122_http_client_tools": "Network",
    "toolkit_123_config_manager": "Data",
    "toolkit_124_test_data_generator": "Data",
    "toolkit_125_number_systems": "Data",
    # ── toolkit_127–toolkit_134 ──
    "toolkit_127_color_tools": "Image",
    "toolkit_128_file_format_detector": "Files",
    "toolkit_129_crypto_tools": "Security",
    "toolkit_130_performance_profiler": "System",
    "toolkit_131_network_topology": "Network",
    "toolkit_132_text_statistics": "Text",
    "toolkit_133_image_analysis": "Image",
    "toolkit_134_video_tools": "Image",
    # ── numbered 121–140 (legacy names) ──
    "121_screen_qr_code_tool": "QR Code",
    "122_desktop_font_viewer": "UI",
    "123_screen_input_validator": "Data",
    "124_desktop_icon_manager": "UI",
    "137_screen_ocr_translator": "Screen",
    "138_auto_form_filler": "Automation",
    "139_desktop_hotkey_manager": "Input Control",
    "140_screen_color_picker": "Image",
}

# Functions to skip (internal helpers, classes, etc.)
SKIP_PREFIXES = ("_", "SKIP_")


class ToolkitRegistry:
    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.modules: Dict[str, Any] = {}
        self.failed_modules: Dict[str, str] = {}
        self.categories: Dict[str, List[str]] = {}
        self._loaded = False

    def discover(self) -> None:
        """Auto-discover all toolkit modules and their public functions."""
        if self._loaded:
            return

        toolkit_dir = Path(__file__).parent
        sys.path.insert(0, str(toolkit_dir.parent))

        for py_file in sorted(toolkit_dir.glob("*.py")):
            mod_name = py_file.stem
            if mod_name in ("__init__", "registry"):
                continue

            try:
                module = importlib.import_module(f"toolkit.{mod_name}")
                self.modules[mod_name] = module
                category = MODULE_CATEGORIES.get(mod_name, "Other")

                for name, obj in inspect.getmembers(module):
                    if not callable(obj):
                        continue
                    if name.startswith(tuple(SKIP_PREFIXES)):
                        continue
                    if inspect.isclass(obj):
                        continue
                    if getattr(obj, "__module__", "") != module.__name__:
                        # Skip re-exported builtins
                        if hasattr(obj, "__module__") and obj.__module__ in ("builtins", "typing"):
                            continue

                    # Get function signature
                    try:
                        sig = inspect.signature(obj)
                        params = {}
                        for pname, param in sig.parameters.items():
                            ptype = "any"
                            if param.annotation != inspect.Parameter.empty:
                                ptype = str(param.annotation).replace("typing.", "")
                            has_default = param.default != inspect.Parameter.empty
                            params[pname] = {
                                "type": ptype,
                                "required": not has_default,
                                "default": str(param.default) if has_default else None,
                            }
                    except (ValueError, TypeError):
                        params = {}

                    full_name = f"{mod_name}.{name}"
                    doc = inspect.getdoc(obj) or ""
                    first_line = doc.split("\n")[0] if doc else ""

                    self.tools[full_name] = {
                        "module": mod_name,
                        "function": name,
                        "callable": obj,
                        "category": category,
                        "doc": first_line,
                        "full_doc": doc,
                        "params": params,
                    }

                    if category not in self.categories:
                        self.categories[category] = []
                    if full_name not in self.categories[category]:
                        self.categories[category].append(full_name)

            except Exception as e:
                self.failed_modules[mod_name] = str(e)

        self._loaded = True

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, str]]:
        """List available tools, optionally filtered by category."""
        self.discover()
        result = []
        for name, info in self.tools.items():
            if category and info["category"] != category:
                continue
            result.append({
                "name": name,
                "category": info["category"],
                "doc": info["doc"],
            })
        return result

    def list_categories(self) -> Dict[str, int]:
        """List categories with tool counts."""
        self.discover()
        return {cat: len(tools) for cat, tools in sorted(self.categories.items())}

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about a specific tool."""
        self.discover()
        info = self.tools.get(tool_name)
        if not info:
            return None
        return {
            "name": tool_name,
            "module": info["module"],
            "function": info["function"],
            "category": info["category"],
            "doc": info["full_doc"],
            "params": info["params"],
        }

    def call_tool(self, tool_name: str, kwargs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a toolkit function by its full name (module.function)."""
        self.discover()
        kwargs = kwargs or {}

        info = self.tools.get(tool_name)
        if not info:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        try:
            result = info["callable"](**kwargs)
            # Normalize return to always be a dict
            if isinstance(result, dict):
                return result
            return {"success": True, "data": result}
        except TypeError as e:
            return {"success": False, "error": f"Invalid arguments: {e}"}
        except Exception as e:
            return {"success": False, "error": f"{type(e).__name__}: {e}"}

    def search_tools(self, query: str) -> List[Dict[str, str]]:
        """Search tools by name or description."""
        self.discover()
        q = query.lower()
        results = []
        for name, info in self.tools.items():
            if q in name.lower() or q in info["doc"].lower() or q in info["category"].lower():
                results.append({
                    "name": name,
                    "category": info["category"],
                    "doc": info["doc"],
                })
        return results

    def get_prompt_summary(self) -> str:
        """Generate a compact summary of available tools for the AI system prompt."""
        self.discover()
        lines = []
        for cat, tool_names in sorted(self.categories.items()):
            # Show just function names (without module prefix) for brevity
            funcs = []
            for tn in tool_names[:15]:  # Cap at 15 per category
                funcs.append(tn.split(".", 1)[1] if "." in tn else tn)
            extra = f" (+{len(tool_names) - 15} more)" if len(tool_names) > 15 else ""
            lines.append(f"  {cat}: {', '.join(funcs)}{extra}")
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        self.discover()
        return {
            "total_tools": len(self.tools),
            "total_modules": len(self.modules),
            "total_categories": len(self.categories),
            "failed_modules": len(self.failed_modules),
            "failed_details": self.failed_modules,
        }


# Global singleton
_registry = ToolkitRegistry()


def get_registry() -> ToolkitRegistry:
    """Get the global toolkit registry."""
    _registry.discover()
    return _registry
