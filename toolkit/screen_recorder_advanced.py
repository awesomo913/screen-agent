import mss
import cv2
import numpy as np
import pyautogui
import json
import time
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

class AdvancedScreenRecorder:
    def __init__(self) -> None:
        self.sct = mss.mss()
        self.is_recording = False
        self.is_paused = False
        self.record_thread: Optional[threading.Thread] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        
        # Configuration
        self.fps = 20.0
        self.output_format = 'mp4'
        self.fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.quality = 80 # Conceptual for OpenCV, enforced heavily in FFmpeg compression
        self.current_monitor = self.sct.monitors[1] if len(self.sct.monitors) > 1 else self.sct.monitors[0]
        self.record_region: Optional[Dict[str, int]] = None
        self.audio_source: Optional[str] = None
        
        # Overlays
        self.overlay_cursor = False
        self.overlay_timestamp = False
        self.watermark_text: Optional[str] = None
        
        # State tracking
        self.start_time = 0.0
        self.pause_start_time = 0.0
        self.total_paused_time = 0.0
        self.output_file: Optional[Path] = None

    def _create_response(self, status: str, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Standardized JSON-serializable response dict."""
        return {"status": status, "message": message, "data": data or {}}

    def get_available_monitors(self) -> Dict[str, Any]:
        """Returns a list of available monitors and their dimensions."""
        try:
            monitors = [{"id": i, "width": m["width"], "height": m["height"], "left": m["left"], "top": m["top"]} 
                        for i, m in enumerate(self.sct.monitors)]
            return self._create_response("success", "Monitors retrieved", {"monitors": monitors})
        except Exception as e:
            return self._create_response("error", f"Failed to get monitors: {str(e)}")

    def set_fps(self, fps: float) -> Dict[str, Any]:
        """Sets the frames per second for recording."""
        if self.is_recording:
            return self._create_response("error", "Cannot change FPS while recording.")
        self.fps = float(fps)
        return self._create_response("success", f"FPS set to {self.fps}")

    def set_output_format(self, format_ext: str) -> Dict[str, Any]:
        """Sets the output format (mp4, avi, etc)."""
        if self.is_recording:
            return self._create_response("error", "Cannot change format while recording.")
        valid_formats = {'mp4': 'mp4v', 'avi': 'XVID'}
        ext = format_ext.lower().replace('.', '')
        if ext not in valid_formats:
            return self._create_response("error", f"Unsupported format. Use: {list(valid_formats.keys())}")
        self.output_format = ext
        self.fourcc = cv2.VideoWriter_fourcc(*valid_formats[ext])
        return self._create_response("success", f"Output format set to {ext}")

    def set_quality(self, quality: int) -> Dict[str, Any]:
        """Sets recording quality (0-100)."""
        self.quality = max(0, min(100, int(quality)))
        return self._create_response("success", f"Quality set to {self.quality}")

    def set_audio_source(self, source: str) -> Dict[str, Any]:
        """Sets the audio source to be multiplexed later. Requires FFmpeg for actual capture."""
        self.audio_source = source
        return self._create_response("success", f"Audio source set to {source}. Note: Handled via post-processing or FFmpeg.")

    def record_monitor(self, monitor_id: int) -> Dict[str, Any]:
        """Selects which monitor to record."""
        if self.is_recording:
            return self._create_response("error", "Cannot change monitor while recording.")
        if monitor_id < 0 or monitor_id >= len(self.sct.monitors):
            return self._create_response("error", "Invalid monitor ID.")
        self.current_monitor = self.sct.monitors[monitor_id]
        self.record_region = None
        return self._create_response("success", f"Monitor {monitor_id} selected.", {"monitor": self.current_monitor})

    def record_window(self, left: int, top: int, width: int, height: int) -> Dict[str, Any]:
        """Sets a specific bounding box to record. (Used for targeting windows)."""
        if self.is_recording:
            return self._create_response("error", "Cannot change region while recording.")
        self.record_region = {"top": top, "left": left, "width": width, "height": height}
        return self._create_response("success", "Region set.", {"region": self.record_region})

    def add_cursor_overlay(self, enable: bool) -> Dict[str, Any]:
        """Toggles the rendering of the mouse cursor."""
        self.overlay_cursor = enable
        return self._create_response("success", f"Cursor overlay {'enabled' if enable else 'disabled'}")

    def add_timestamp_overlay(self, enable: bool) -> Dict[str, Any]:
        """Toggles the rendering of a timestamp."""
        self.overlay_timestamp = enable
        return self._create_response("success", f"Timestamp overlay {'enabled' if enable else 'disabled'}")

    def add_watermark(self, text: str) -> Dict[str, Any]:
        """Sets a watermark text to overlay."""
        self.watermark_text = text if text else None
        return self._create_response("success", f"Watermark set to: {text}")

    def capture_region(self, output_path: str, left: int, top: int, width: int, height: int) -> Dict[str, Any]:
        """Takes a single screenshot of a specific region."""
        try:
            region = {"top": top, "left": left, "width": width, "height": height}
            img = np.array(self.sct.grab(region))
            cv2.imwrite(output_path, cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))
            return self._create_response("success", "Region captured", {"path": output_path})
        except Exception as e:
            return self._create_response("error", f"Capture failed: {str(e)}")

    def _recording_loop(self) -> None:
        """Internal loop executing the frame capture."""
        frame_duration = 1.0 / self.fps
        capture_area = self.record_region if self.record_region else self.current_monitor
        
        while self.is_recording:
            loop_start = time.time()
            
            if not self.is_paused:
                # Capture screen
                img = np.array(self.sct.grab(capture_area))
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Apply Overlays
                if self.overlay_cursor:
                    mx, my = pyautogui.position()
                    # Adjust for monitor/region offset
                    adj_x = mx - capture_area["left"]
                    adj_y = my - capture_area["top"]
                    if 0 <= adj_x <= capture_area["width"] and 0 <= adj_y <= capture_area["height"]:
                        cv2.circle(frame, (adj_x, adj_y), 5, (0, 0, 255), -1)

                if self.overlay_timestamp:
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    cv2.putText(frame, ts, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                if self.watermark_text:
                    cv2.putText(frame, self.watermark_text, (10, capture_area["height"] - 20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                self.video_writer.write(frame)

            # Frame pacing
            elapsed = time.time() - loop_start
            sleep_time = frame_duration - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def start_recording(self, output_filename: str) -> Dict[str, Any]:
        """Starts the recording process."""
        if self.is_recording:
            return self._create_response("error", "Already recording.")
        
        try:
            self.output_file = Path(output_filename).with_suffix(f'.{self.output_format}')
            capture_area = self.record_region if self.record_region else self.current_monitor
            dimensions = (capture_area["width"], capture_area["height"])
            
            self.video_writer = cv2.VideoWriter(str(self.output_file), self.fourcc, self.fps, dimensions)
            
            self.is_recording = True
            self.is_paused = False
            self.start_time = time.time()
            self.total_paused_time = 0.0
            
            self.record_thread = threading.Thread(target=self._recording_loop, daemon=True)
            self.record_thread.start()
            
            return self._create_response("success", "Recording started.", {"file": str(self.output_file)})
        except Exception as e:
            self.is_recording = False
            return self._create_response("error", f"Failed to start recording: {str(e)}")

    def stop_recording(self) -> Dict[str, Any]:
        """Stops the active recording."""
        if not self.is_recording:
            return self._create_response("error", "Not currently recording.")
        
        self.is_recording = False
        if self.record_thread:
            self.record_thread.join(timeout=2.0)
        
        if self.video_writer:
            self.video_writer.release()
            
        dur = self.get_recording_duration()["data"].get("duration_seconds", 0)
        return self._create_response("success", "Recording stopped.", {"file": str(self.output_file), "duration": dur})

    def pause_recording(self) -> Dict[str, Any]:
        """Pauses the recording."""
        if not self.is_recording or self.is_paused:
            return self._create_response("error", "Recording is not active or already paused.")
        self.is_paused = True
        self.pause_start_time = time.time()
        return self._create_response("success", "Recording paused.")

    def resume_recording(self) -> Dict[str, Any]:
        """Resumes a paused recording."""
        if not self.is_recording or not self.is_paused:
            return self._create_response("error", "Recording is not active or not paused.")
        self.is_paused = False
        self.total_paused_time += (time.time() - self.pause_start_time)
        return self._create_response("success", "Recording resumed.")

    def get_recording_status(self) -> Dict[str, Any]:
        """Gets current state of the recorder."""
        status = {
            "is_recording": self.is_recording,
            "is_paused": self.is_paused,
            "fps": self.fps,
            "output_file": str(self.output_file) if self.output_file else None
        }
        return self._create_response("success", "Status retrieved", status)

    def get_recording_duration(self) -> Dict[str, Any]:
        """Returns the active or final duration of the recording in seconds."""
        if self.start_time == 0:
            return self._create_response("success", "Duration retrieved", {"duration_seconds": 0.0})
        
        current_time = time.time()
        if self.is_paused:
            active_pause = current_time - self.pause_start_time
            dur = (current_time - self.start_time) - self.total_paused_time - active_pause
        elif self.is_recording:
            dur = (current_time - self.start_time) - self.total_paused_time
        else: # Stopped
             dur = (self.pause_start_time if self.is_paused else current_time) - self.start_time - self.total_paused_time

        return self._create_response("success", "Duration retrieved", {"duration_seconds": round(dur, 2)})

    def schedule_recording(self, delay_seconds: int, duration_seconds: int, output_filename: str) -> Dict[str, Any]:
        """Schedules a recording to start after X seconds and stop after Y seconds."""
        if self.is_recording:
            return self._create_response("error", "Already recording.")
        
        def _task():
            time.sleep(delay_seconds)
            self.start_recording(output_filename)
            time.sleep(duration_seconds)
            self.stop_recording()
            
        threading.Thread(target=_task, daemon=True).start()
        return self._create_response("success", f"Scheduled recording in {delay_seconds}s for {duration_seconds}s.")

    # --- FFmpeg Post-Processing Operations ---
    def _run_ffmpeg(self, cmd: List[str]) -> Dict[str, Any]:
        """Helper to run ffmpeg commands safely."""
        try:
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if process.returncode != 0:
                return self._create_response("error", f"FFmpeg error: {process.stderr}")
            return self._create_response("success", "FFmpeg operation completed successfully.")
        except FileNotFoundError:
            return self._create_response("error", "FFmpeg not found. Please install it on your system.")
        except Exception as e:
            return self._create_response("error", f"Execution error: {str(e)}")

    def compress_recording(self, input_path: str, output_path: str, crf: int = 28) -> Dict[str, Any]:
        """Compresses video using FFmpeg H.264 CRF."""
        cmd = ['ffmpeg', '-y', '-i', input_path, '-vcodec', 'libx264', '-crf', str(crf), output_path]
        res = self._run_ffmpeg(cmd)
        if res["status"] == "success": res["data"] = {"output": output_path}
        return res

    def trim_recording(self, input_path: str, start_time: str, duration: str, output_path: str) -> Dict[str, Any]:
        """Trims a video using FFmpeg (start_time and duration format: HH:MM:SS)."""
        cmd = ['ffmpeg', '-y', '-ss', start_time, '-t', duration, '-i', input_path, '-c', 'copy', output_path]
        res = self._run_ffmpeg(cmd)
        if res["status"] == "success": res["data"] = {"output": output_path}
        return res

    def split_recording(self, input_path: str, chunk_duration: str, output_pattern: str) -> Dict[str, Any]:
        """Splits video into chunks (e.g., chunk_duration='00:10:00', pattern='out_%03d.mp4')."""
        cmd = ['ffmpeg', '-y', '-i', input_path, '-c', 'copy', '-map', '0', '-segment_time', chunk_duration, 
               '-f', 'segment', '-reset_timestamps', '1', output_pattern]
        res = self._run_ffmpeg(cmd)
        if res["status"] == "success": res["data"] = {"pattern": output_pattern}
        return res

    def merge_recordings(self, input_paths: List[str], output_path: str) -> Dict[str, Any]:
        """Merges multiple videos using FFmpeg concat."""
        list_file = Path('files_to_merge.txt')
        try:
            with open(list_file, 'w') as f:
                for path in input_paths:
                    f.write(f"file '{Path(path).absolute()}'\n")
            cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file), '-c', 'copy', output_path]
            res = self._run_ffmpeg(cmd)
            list_file.unlink() # Cleanup
            if res["status"] == "success": res["data"] = {"output": output_path}
            return res
        except Exception as e:
            if list_file.exists(): list_file.unlink()
            return self._create_response("error", f"Merge failed: {str(e)}")

    def extract_frames(self, input_path: str, fps: int, output_pattern: str) -> Dict[str, Any]:
        """Extracts frames as images (e.g., pattern='frame_%04d.png')."""
        cmd = ['ffmpeg', '-y', '-i', input_path, '-vf', f'fps={fps}', output_pattern]
        res = self._run_ffmpeg(cmd)
        if res["status"] == "success": res["data"] = {"pattern": output_pattern}
        return res

    def create_timelapse(self, input_path: str, speed_multiplier: float, output_path: str) -> Dict[str, Any]:
        """Creates a timelapse by adjusting video speed via FFmpeg PTS filter."""
        pts_factor = 1.0 / speed_multiplier
        cmd = ['ffmpeg', '-y', '-i', input_path, '-filter:v', f'setpts={pts_factor}*PTS', '-an', output_path]
        res = self._run_ffmpeg(cmd)
        if res["status"] == "success": res["data"] = {"output": output_path}
        return res

    def export_gif_from_recording(self, input_path: str, output_path: str, fps: int = 10, scale: int = 480) -> Dict[str, Any]:
        """Creates an optimized GIF from a video using FFmpeg complex filters."""
        # 2-pass for optimal palette
        filters = f"fps={fps},scale={scale}:-1:flags=lanczos"
        cmd = ['ffmpeg', '-y', '-i', input_path, '-vf', f"{filters},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", output_path]
        res = self._run_ffmpeg(cmd)
        if res["status"] == "success": res["data"] = {"output": output_path}
        return res

# Example Usage
if __name__ == "__main__":
    recorder = AdvancedScreenRecorder()
    
    # 1. Setup
    print(json.dumps(recorder.get_available_monitors(), indent=2))
    recorder.set_fps(15)
    recorder.add_cursor_overlay(True)
    recorder.add_timestamp_overlay(True)
    
    # 2. Record
    print("\nStarting recording for 5 seconds...")
    recorder.start_recording("test_agent_record")
    time.sleep(5)
    result = recorder.stop_recording()
    print(json.dumps(result, indent=2))
    
    # 3. Post-process (Requires FFmpeg)
    # print("\nExporting to GIF...")
    # gif_result = recorder.export_gif_from_recording("test_agent_record.mp4", "test_agent_record.gif")
    # print(json.dumps(gif_result, indent=2))
