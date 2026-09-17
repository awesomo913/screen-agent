import re
import json
import os
import time
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime, timedelta
import statistics
import gzip
import shutil
from typing import Dict, List, Any, Optional, Callable, Generator

class LogAnalyzer:
    """
    Production-grade Log Analyzer for screen agent toolkits.
    Prioritizes memory safety by processing files efficiently.
    """
    
    # Standard format: [2023-10-27 10:00:00] [ERROR] [AgentX] Connection timed out
    DEFAULT_PATTERN = re.compile(r"\[(?P<timestamp>.*?)\] \[(?P<level>.*?)\] \[(?P<source>.*?)\] (?P<message>.*)")
    
    def __init__(self):
        self.alert_thresholds: Dict[str, int] = {}

    def _parse_line(self, line: str, pattern: re.Pattern = DEFAULT_PATTERN) -> Optional[Dict[str, Any]]:
        match = pattern.match(line)
        if match:
            data = match.groupdict()
            try:
                data['datetime'] = datetime.strptime(data['timestamp'], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                data['datetime'] = None
            return data
        return None

    def parse_log_file(self, file_path: str) -> Dict[str, Any]:
        """Reads and parses a log file safely."""
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}", "logs": []}
        
        logs = []
        try:
            with path.open('r', encoding='utf-8') as f:
                for line in f:
                    parsed = self._parse_line(line.strip())
                    if parsed:
                        logs.append(parsed)
            return {"status": "success", "count": len(logs), "logs": logs}
        except Exception as e:
            return {"error": str(e), "logs": []}

    def parse_custom_format(self, file_path: str, regex_pattern: str) -> Dict[str, Any]:
        """Parses logs using a user-defined regex."""
        try:
            pattern = re.compile(regex_pattern)
        except re.error as e:
            return {"error": f"Invalid regex: {e}", "logs": []}
            
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found", "logs": []}
            
        logs = []
        try:
            with path.open('r', encoding='utf-8') as f:
                for line in f:
                    match = pattern.match(line.strip())
                    if match:
                        logs.append(match.groupdict())
            return {"status": "success", "count": len(logs), "logs": logs}
        except Exception as e:
            return {"error": str(e), "logs": []}

    def search_logs(self, logs: List[Dict[str, Any]], keyword: str) -> Dict[str, Any]:
        """Searches logs for a specific keyword."""
        keyword_lower = keyword.lower()
        results = [log for log in logs if keyword_lower in log.get('message', '').lower()]
        return {"status": "success", "count": len(results), "matches": results}

    def filter_by_level(self, logs: List[Dict[str, Any]], level: str) -> Dict[str, Any]:
        """Filters logs by severity level."""
        results = [log for log in logs if log.get('level', '').upper() == level.upper()]
        return {"status": "success", "level": level, "count": len(results), "matches": results}

    def filter_by_date_range(self, logs: List[Dict[str, Any]], start_str: str, end_str: str) -> Dict[str, Any]:
        """Filters logs between two timestamp strings."""
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
            results = [log for log in logs if log.get('datetime') and start_dt <= log['datetime'] <= end_dt]
            return {"status": "success", "count": len(results), "matches": results}
        except ValueError as e:
            return {"error": f"Date format error: {e}. Use YYYY-MM-DD HH:MM:SS", "matches": []}

    def get_error_summary(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregates all errors and counts unique messages."""
        errors = [log['message'] for log in logs if log.get('level', '').upper() in ('ERROR', 'CRITICAL', 'FATAL')]
        counts = dict(Counter(errors))
        return {"status": "success", "total_errors": len(errors), "unique_errors": len(counts), "summary": counts}

    def group_by_source(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Groups log entries by their origin source/agent."""
        grouped = defaultdict(list)
        for log in logs:
            grouped[log.get('source', 'UNKNOWN')].append(log)
        return {"status": "success", "sources_count": len(grouped), "groups": dict(grouped)}

    def get_frequency_analysis(self, logs: List[Dict[str, Any]], interval: str = 'hour') -> Dict[str, Any]:
        """Analyzes log volume frequency over specified intervals."""
        freq = defaultdict(int)
        for log in logs:
            dt = log.get('datetime')
            if not dt:
                continue
            if interval == 'hour':
                key = dt.strftime("%Y-%m-%d %H:00")
            elif interval == 'day':
                key = dt.strftime("%Y-%m-%d")
            else:
                key = dt.strftime("%Y-%m-%d %H:%M")
            freq[key] += 1
        return {"status": "success", "interval": interval, "frequencies": dict(freq)}

    def detect_anomalies(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detects anomalous spikes in log volume using statistical standard deviation."""
        freq_data = self.get_frequency_analysis(logs, interval='hour')
        if "error" in freq_data:
            return freq_data
            
        counts = list(freq_data['frequencies'].values())
        if len(counts) < 3:
            return {"status": "insufficient_data", "anomalies": {}}
            
        mean = statistics.mean(counts)
        stdev = statistics.stdev(counts) if len(counts) > 1 else 0
        threshold = mean + (2 * stdev)
        
        anomalies = {time: count for time, count in freq_data['frequencies'].items() if count > threshold}
        return {"status": "success", "mean": mean, "stdev": stdev, "threshold": threshold, "anomalies": anomalies}

    def extract_stack_traces(self, file_path: str) -> Dict[str, Any]:
        """Extracts multi-line stack traces (Tracebacks) from raw log files."""
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found", "traces": []}
            
        traces = []
        current_trace = []
        in_trace = False
        
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                if "Traceback (most recent call last):" in line:
                    in_trace = True
                    current_trace = [line.strip()]
                elif in_trace:
                    if line.startswith(" ") or line.startswith("\t") or ":" in line:
                        current_trace.append(line.strip())
                    else:
                        traces.append("\n".join(current_trace))
                        in_trace = False
                        current_trace = []
        if in_trace:
            traces.append("\n".join(current_trace))
            
        return {"status": "success", "count": len(traces), "traces": traces}

    def calculate_error_rate(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates the percentage of error logs vs total logs."""
        total = len(logs)
        if total == 0:
            return {"status": "success", "error_rate": 0.0, "total": 0, "errors": 0}
        
        errors = len([log for log in logs if log.get('level', '').upper() in ('ERROR', 'CRITICAL')])
        rate = (errors / total) * 100
        return {"status": "success", "error_rate": round(rate, 2), "total": total, "errors": errors}

    def get_top_errors(self, logs: List[Dict[str, Any]], n: int = 5) -> Dict[str, Any]:
        """Retrieves the top N most frequent error messages."""
        summary = self.get_error_summary(logs)
        if "error" in summary:
            return summary
            
        sorted_errors = sorted(summary['summary'].items(), key=lambda item: item[1], reverse=True)
        return {"status": "success", "top_errors": dict(sorted_errors[:n])}

    def extract_metrics(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extracts numerical metrics embedded in log messages (e.g., 'latency: 45ms')."""
        metrics = defaultdict(list)
        metric_pattern = re.compile(r"(?P<metric_name>[a-zA-Z_]+)\s*[:=]\s*(?P<value>[0-9.]+)(?P<unit>[a-zA-Z]*)")
        
        for log in logs:
            matches = metric_pattern.finditer(log.get('message', ''))
            for match in matches:
                name = match.group('metric_name')
                val = float(match.group('value'))
                metrics[name].append(val)
                
        stats = {}
        for name, values in metrics.items():
            stats[name] = {
                "min": min(values),
                "max": max(values),
                "avg": round(statistics.mean(values), 2),
                "count": len(values)
            }
        return {"status": "success", "metrics": stats}

    def correlate_events(self, logs: List[Dict[str, Any]], time_window_seconds: int) -> Dict[str, Any]:
        """Finds events that happen across different sources within a narrow time window."""
        correlated = []
        n = len(logs)
        for i in range(n):
            dt_i = logs[i].get('datetime')
            if not dt_i: continue
            
            cluster = [logs[i]]
            for j in range(i + 1, min(i + 50, n)): # Check next 50 logs safely
                dt_j = logs[j].get('datetime')
                if not dt_j: continue
                
                delta = abs((dt_j - dt_i).total_seconds())
                if delta <= time_window_seconds:
                    if logs[j]['source'] != logs[i]['source']: # Only correlate different sources
                        cluster.append(logs[j])
                else:
                    break
                    
            if len(cluster) > 1 and cluster not in correlated:
                correlated.append(cluster)
                
        return {"status": "success", "correlated_clusters": len(correlated), "clusters": correlated}

    def get_timeline(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates a chronological timeline of critical system events."""
        critical_logs = [log for log in logs if log.get('level', '').upper() in ('CRITICAL', 'FATAL', 'WARN')]
        sorted_logs = sorted(critical_logs, key=lambda x: x.get('datetime', datetime.min))
        timeline = [f"{log['timestamp']} - {log['source']} - {log['message']}" for log in sorted_logs]
        return {"status": "success", "events": len(timeline), "timeline": timeline}

    def generate_dashboard_data(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compiles a complete snapshot of data for a monitoring dashboard."""
        return {
            "status": "success",
            "total_logs": len(logs),
            "error_rate": self.calculate_error_rate(logs).get("error_rate", 0),
            "level_distribution": dict(Counter([log.get('level', 'UNKNOWN') for log in logs])),
            "top_errors": self.get_top_errors(logs, 5).get("top_errors", {}),
            "source_distribution": dict(Counter([log.get('source', 'UNKNOWN') for log in logs]))
        }

    def set_alert_threshold(self, level: str, count: int) -> Dict[str, Any]:
        """Configures memory thresholds for triggering alerts."""
        self.alert_thresholds[level.upper()] = count
        return {"status": "success", "thresholds": self.alert_thresholds}

    def tail_log(self, file_path: str, n: int = 10) -> Dict[str, Any]:
        """Returns the last N lines of a log file efficiently."""
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found", "lines": []}
            
        try:
            with path.open('rb') as f:
                f.seek(0, 2)
                block_size = 1024
                blocks = []
                while f.tell() > 0 and len(b"".join(blocks).split(b'\n')) <= n:
                    f.seek(max(f.tell() - block_size, 0))
                    blocks.append(f.read(block_size))
                    f.seek(max(f.tell() - block_size * 2, 0)) # Move back for next read
                
                lines = b"".join(reversed(blocks)).split(b'\n')
                decoded = [line.decode('utf-8', errors='ignore') for line in lines[-n-1:-1]]
                return {"status": "success", "lines": decoded}
        except Exception as e:
            return {"error": str(e), "lines": []}

    def watch_log_file(self, file_path: str, timeout_sec: int = 10) -> Dict[str, Any]:
        """Simulates watching a log file for new entries for a specific duration."""
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found"}
            
        new_lines = []
        try:
            with path.open('r', encoding='utf-8') as f:
                f.seek(0, 2)
                start_time = time.time()
                while time.time() - start_time < timeout_sec:
                    line = f.readline()
                    if line:
                        new_lines.append(line.strip())
                    else:
                        time.sleep(0.5)
            return {"status": "success", "new_lines_caught": len(new_lines), "lines": new_lines}
        except Exception as e:
            return {"error": str(e)}

    def aggregate_logs(self, log_dir: str) -> Dict[str, Any]:
        """Combines log entries from all files in a specific directory."""
        directory = Path(log_dir)
        if not directory.is_dir():
            return {"error": "Directory not found", "logs": []}
            
        all_logs = []
        for file_path in directory.glob('*.log'):
            res = self.parse_log_file(str(file_path))
            if "logs" in res:
                all_logs.extend(res["logs"])
        return {"status": "success", "total_logs": len(all_logs), "logs": all_logs}

    def merge_log_files(self, files: List[str], out_path: str) -> Dict[str, Any]:
        """Merges multiple distinct log files into one sorted output file."""
        all_logs = []
        for file in files:
            res = self.parse_log_file(file)
            if "logs" in res:
                all_logs.extend(res["logs"])
                
        sorted_logs = sorted(all_logs, key=lambda x: x.get('datetime', datetime.min))
        
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                for log in sorted_logs:
                    f.write(f"[{log.get('timestamp')}] [{log.get('level')}] [{log.get('source')}] {log.get('message')}\n")
            return {"status": "success", "merged_count": len(sorted_logs), "output": out_path}
        except Exception as e:
            return {"error": str(e)}

    def rotate_logs(self, file_path: str, max_size_mb: float = 10.0) -> Dict[str, Any]:
        """Rotates log file if it exceeds maximum size threshold."""
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found"}
            
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            rotated_path = f"{file_path}.{timestamp}.bak"
            try:
                shutil.move(file_path, rotated_path)
                Path(file_path).touch() # Create empty new file
                return {"status": "success", "action": "rotated", "new_file": rotated_path}
            except Exception as e:
                return {"error": str(e)}
        return {"status": "success", "action": "none_needed", "current_size_mb": round(size_mb, 2)}

    def compress_old_logs(self, log_dir: str, days_old: int = 7) -> Dict[str, Any]:
        """Compresses log files older than a specific timeframe to save Pi storage."""
        directory = Path(log_dir)
        if not directory.is_dir():
            return {"error": "Directory not found"}
            
        cutoff = time.time() - (days_old * 86400)
        compressed = []
        
        try:
            for file_path in directory.glob('*.log'):
                if file_path.stat().st_mtime < cutoff:
                    gz_path = f"{file_path}.gz"
                    with file_path.open('rb') as f_in, gzip.open(gz_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    file_path.unlink() # delete original
                    compressed.append(str(file_path.name))
            return {"status": "success", "compressed_files": compressed}
        except Exception as e:
            return {"error": str(e)}

    def archive_logs(self, log_dir: str, archive_dir: str) -> Dict[str, Any]:
        """Moves all compressed logs to dedicated archive storage."""
        src = Path(log_dir)
        dst = Path(archive_dir)
        if not src.is_dir():
            return {"error": "Source directory not found"}
            
        dst.mkdir(parents=True, exist_ok=True)
        archived = []
        
        try:
            for file_path in src.glob('*.gz'):
                shutil.move(str(file_path), str(dst / file_path.name))
                archived.append(file_path.name)
            return {"status": "success", "archived_files": archived, "destination": archive_dir}
        except Exception as e:
            return {"error": str(e)}

    def export_report(self, data: Dict[str, Any], out_path: str) -> Dict[str, Any]:
        """Exports analytics data cleanly to a JSON file."""
        try:
            # Custom default to handle datetime objects in serialization
            def default_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, default=default_serializer)
            return {"status": "success", "path": out_path}
        except Exception as e:
            return {"error": str(e)}

# --- Usage Example (Can be executed directly) ---
if __name__ == "__main__":
    analyzer = LogAnalyzer()
    print(analyzer.set_alert_threshold("ERROR", 100))
