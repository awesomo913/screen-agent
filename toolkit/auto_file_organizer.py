#!/usr/bin/env python3
"""
Installation Requirements:
    pip install pyautogui

Raspberry Pi / Linux Paste Shortcut:
    Ctrl + Shift + V (in terminal)

Usage Examples:
    python3 auto_organizer.py rules --init
    python3 auto_organizer.py organize --dir ./Downloads
    python3 auto_organizer.py watch --dir ./Downloads --interval 2.0
    python3 auto_organizer.py undo --log move_log.json
"""

import os
import shutil
import json
import time
import argparse
from datetime import datetime
import pyautogui

class ConfigManager:
    DEFAULT_RULES = {
        "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
        "docs": [".pdf", ".doc", ".docx", ".txt", ".xlsx", ".csv", ".pptx", ".md"],
        "videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"],
        "code": [".py", ".js", ".html", ".css", ".cpp", ".c", ".h", ".json", ".xml"],
        "archives": [".zip", ".tar", ".gz", ".rar", ".7z"]
    }

    def __init__(self, config_file="rules.json"):
        self.config_file = config_file

    def init_rules(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.DEFAULT_RULES, f, indent=4)
        print(f"Initialized default rules in {self.config_file}")

    def load_rules(self):
        if not os.path.exists(self.config_file):
            print(f"Rules file {self.config_file} not found. Using defaults.")
            return self.DEFAULT_RULES
        with open(self.config_file, 'r') as f:
            return json.load(f)

    def show_rules(self):
        rules = self.load_rules()
        print(json.dumps(rules, indent=4))


class ActionLogger:
    def __init__(self, log_file="move_log.json"):
        self.log_file = log_file

    def log_move(self, original_path, new_path):
        record = {
            "timestamp": datetime.now().isoformat(),
            "original_path": original_path,
            "new_path": new_path
        }

        logs = self.load_logs()
        logs.append(record)

        with open(self.log_file, 'w') as f:
            json.dump(logs, f, indent=4)

    def load_logs(self):
        if not os.path.exists(self.log_file):
            return []
        with open(self.log_file, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def clear_log(self):
        if os.path.exists(self.log_file):
            os.remove(self.log_file)


class FileOrganizer:
    def __init__(self, rules, logger):
        self.rules = rules
        self.logger = logger
        self.extension_map = self._build_extension_map()

    def _build_extension_map(self):
        ext_map = {}
        for category, extensions in self.rules.items():
            for ext in extensions:
                ext_map[ext.lower()] = category
        return ext_map

    def get_category(self, filename):
        _, ext = os.path.splitext(filename)
        return self.extension_map.get(ext.lower(), "others")

    def safe_move(self, src_path, dest_dir):
        filename = os.path.basename(src_path)
        name, ext = os.path.splitext(filename)
        dest_path = os.path.join(dest_dir, filename)

        if os.path.exists(dest_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_path = os.path.join(dest_dir, f"{name}_{timestamp}{ext}")

        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(src_path, dest_path)
        self.logger.log_move(src_path, dest_path)
        return dest_path

    def organize_directory(self, target_dir):
        if not os.path.exists(target_dir):
            print(f"Directory {target_dir} does not exist.")
            return

        moved_count = 0
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)

            if os.path.isfile(item_path):
                category = self.get_category(item)
                dest_dir = os.path.join(target_dir, category)

                try:
                    new_path = self.safe_move(item_path, dest_dir)
                    print(f"Moved: {item} -> {new_path}")
                    moved_count += 1
                except Exception as e:
                    print(f"Error moving {item}: {e}")

        if moved_count > 0:
            # Simulate a screen refresh to update file explorer view
            try:
                pyautogui.press('f5')
            except Exception:
                pass
            print(f"Successfully organized {moved_count} files.")
        else:
            print("No files to organize.")


class FolderWatcher:
    def __init__(self, target_dir, interval, organizer):
        self.target_dir = target_dir
        self.interval = interval
        self.organizer = organizer

    def watch(self):
        if not os.path.exists(self.target_dir):
            print(f"Directory {self.target_dir} does not exist.")
            return

        print(f"Watching {self.target_dir} for new files. Press Ctrl+C to stop.")

        def get_files():
            return {f for f in os.listdir(self.target_dir) if os.path.isfile(os.path.join(self.target_dir, f))}

        known_files = get_files()

        try:
            while True:
                time.sleep(self.interval)
                current_files = get_files()
                new_files = current_files - known_files

                if new_files:
                    for filename in new_files:
                        file_path = os.path.join(self.target_dir, filename)
                        category = self.organizer.get_category(filename)
                        dest_dir = os.path.join(self.target_dir, category)

                        # Wait briefly to ensure file download/copy is complete
                        time.sleep(0.5)
                        try:
                            if os.path.exists(file_path):
                                new_path = self.organizer.safe_move(file_path, dest_dir)
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-moved: {filename} -> {new_path}")
                        except Exception as e:
                            print(f"Error moving new file {filename}: {e}")

                    try:
                        pyautogui.press('f5')
                    except Exception:
                        pass

                known_files = get_files()
        except KeyboardInterrupt:
            print("\nStopped watching directory.")


class RollbackManager:
    def __init__(self, logger):
        self.logger = logger

    def undo_all(self):
        logs = self.logger.load_logs()
        if not logs:
            print("No logs found to undo.")
            return

        print(f"Found {len(logs)} operations to undo.")
        for record in reversed(logs):
            original_path = record["original_path"]
            current_path = record["new_path"]

            if os.path.exists(current_path):
                original_dir = os.path.dirname(original_path)
                os.makedirs(original_dir, exist_ok=True)

                try:
                    shutil.move(current_path, original_path)
                    print(f"Reverted: {current_path} -> {original_path}")
                except Exception as e:
                    print(f"Error reverting {current_path}: {e}")
            else:
                print(f"Skipped missing file: {current_path}")

        self.logger.clear_log()
        print("Undo complete. Log cleared.")
        try:
            pyautogui.press('f5')
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Auto File Organizer Toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: rules
    rules_parser = subparsers.add_parser("rules", help="Manage sorting rules")
    rules_parser.add_argument("--init", action="store_true", help="Initialize default rules.json")
    rules_parser.add_argument("--show", action="store_true", help="Show current rules")

    # Command: organize
    org_parser = subparsers.add_parser("organize", help="Organize a directory once")
    org_parser.add_argument("--dir", required=True, help="Target directory to organize")
    org_parser.add_argument("--config", default="rules.json", help="Path to rules config")
    org_parser.add_argument("--log", default="move_log.json", help="Path to operations log")

    # Command: watch
    watch_parser = subparsers.add_parser("watch", help="Monitor a directory and auto-organize")
    watch_parser.add_argument("--dir", required=True, help="Target directory to watch")
    watch_parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    watch_parser.add_argument("--config", default="rules.json", help="Path to rules config")
    watch_parser.add_argument("--log", default="move_log.json", help="Path to operations log")

    # Command: undo
    undo_parser = subparsers.add_parser("undo", help="Rollback organized files to original locations")
    undo_parser.add_argument("--log", default="move_log.json", help="Path to operations log")

    args = parser.parse_args()

    config_manager = ConfigManager()

    if args.command == "rules":
        if args.init:
            config_manager.init_rules()
        elif args.show:
            config_manager.show_rules()
        else:
            print("Please specify --init or --show")

    elif args.command == "organize":
        config_manager.config_file = args.config
        rules = config_manager.load_rules()
        logger = ActionLogger(log_file=args.log)
        organizer = FileOrganizer(rules, logger)
        organizer.organize_directory(args.dir)

    elif args.command == "watch":
        config_manager.config_file = args.config
        rules = config_manager.load_rules()
        logger = ActionLogger(log_file=args.log)
        organizer = FileOrganizer(rules, logger)
        watcher = FolderWatcher(args.dir, args.interval, organizer)
        watcher.watch()

    elif args.command == "undo":
        logger = ActionLogger(log_file=args.log)
        rollback = RollbackManager(logger)
        rollback.undo_all()


if __name__ == "__main__":
    main()
