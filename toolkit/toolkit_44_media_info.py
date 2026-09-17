"""
toolkit_44_media_info.py
Get metadata from audio/video files: duration, codec, bitrate,
resolution, frame rate. Uses ffprobe (FFmpeg) and mutagen (soft-import).
"""
from __future__ import annotations
import subprocess
import json
import os
from pathlib import Path
from typing import Any, Dict, List

try:
    import mutagen
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

def _run(cmd: list, timeout: int = 15) -> tuple:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip(), result.returncode

def _ffprobe_available() -> bool:
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False

def get_media_info(path: str) -> Dict[str, Any]:
    """Get full media metadata using ffprobe."""
    try:
        if not _ffprobe_available():
            return {"success": False, "data": None, "error": "ffprobe not found (install FFmpeg)"}
        out, _ = _run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path])
        data = json.loads(out) if out else None
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_duration(path: str) -> Dict[str, Any]:
    try:
        if not _ffprobe_available():
            return {"success": False, "data": None, "error": "ffprobe not found"}
        out, _ = _run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "json", path])
        data = json.loads(out) if out else {}
        duration = float(data.get("format", {}).get("duration", 0))
        mins = int(duration // 60)
        secs = round(duration % 60, 1)
        return {"success": True, "data": {"seconds": round(duration, 2), "minutes": mins, "formatted": str(mins) + ":" + str(secs).zfill(4)}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_video_info(path: str) -> Dict[str, Any]:
    try:
        if not _ffprobe_available():
            return {"success": False, "data": None, "error": "ffprobe not found"}
        out, _ = _run(["ffprobe", "-v", "quiet", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,codec_name,bit_rate", "-of", "json", path])
        data = json.loads(out) if out else {}
        streams = data.get("streams", [{}])
        s = streams[0] if streams else {}
        fps_str = s.get("r_frame_rate", "0/1")
        try:
            num, den = fps_str.split("/")
            fps = round(int(num) / int(den), 2)
        except Exception:
            fps = 0
        return {"success": True, "data": {
            "codec": s.get("codec_name", ""),
            "width": s.get("width"),
            "height": s.get("height"),
            "fps": fps,
            "bitrate": s.get("bit_rate", "")
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_audio_info(path: str) -> Dict[str, Any]:
    try:
        if not _ffprobe_available():
            return {"success": False, "data": None, "error": "ffprobe not found"}
        out, _ = _run(["ffprobe", "-v", "quiet", "-select_streams", "a:0", "-show_entries", "stream=codec_name,sample_rate,channels,bit_rate", "-of", "json", path])
        data = json.loads(out) if out else {}
        streams = data.get("streams", [{}])
        s = streams[0] if streams else {}
        return {"success": True, "data": {
            "codec": s.get("codec_name", ""),
            "sample_rate": s.get("sample_rate", ""),
            "channels": s.get("channels", ""),
            "bitrate": s.get("bit_rate", "")
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_mp3_tags(path: str) -> Dict[str, Any]:
    try:
        if not HAS_MUTAGEN:
            return {"success": False, "data": None, "error": "mutagen not installed (pip install mutagen)"}
        audio = MP3(path)
        tags = {}
        if audio.tags:
            for k in ["TIT2", "TPE1", "TALB", "TDRC", "TCON", "TRCK"]:
                v = audio.tags.get(k)
                if v:
                    tags[k] = str(v)
        tag_names = {"TIT2": "title", "TPE1": "artist", "TALB": "album", "TDRC": "year", "TCON": "genre", "TRCK": "track"}
        named = {tag_names.get(k, k): v for k, v in tags.items()}
        return {"success": True, "data": {
            "duration_s": round(audio.info.length, 1),
            "bitrate_kbps": audio.info.bitrate // 1000,
            "sample_rate": audio.info.sample_rate,
            "tags": named
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def set_mp3_tags(path: str, title: str = "", artist: str = "", album: str = "", year: str = "", genre: str = "") -> Dict[str, Any]:
    try:
        if not HAS_MUTAGEN:
            return {"success": False, "data": None, "error": "mutagen not installed"}
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON
        try:
            tags = ID3(path)
        except Exception:
            tags = ID3()
        if title: tags["TIT2"] = TIT2(encoding=3, text=title)
        if artist: tags["TPE1"] = TPE1(encoding=3, text=artist)
        if album: tags["TALB"] = TALB(encoding=3, text=album)
        if year: tags["TDRC"] = TDRC(encoding=3, text=year)
        if genre: tags["TCON"] = TCON(encoding=3, text=genre)
        tags.save(path)
        return {"success": True, "data": "Tags saved", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_flac_info(path: str) -> Dict[str, Any]:
    try:
        if not HAS_MUTAGEN:
            return {"success": False, "data": None, "error": "mutagen not installed"}
        audio = FLAC(path)
        return {"success": True, "data": {
            "duration_s": round(audio.info.length, 1),
            "sample_rate": audio.info.sample_rate,
            "channels": audio.info.channels,
            "bits_per_sample": audio.info.bits_per_sample,
            "tags": dict(audio.tags or {})
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_mp4_info(path: str) -> Dict[str, Any]:
    try:
        if not HAS_MUTAGEN:
            return {"success": False, "data": None, "error": "mutagen not installed"}
        audio = MP4(path)
        tags = {}
        tag_map = {"\xa9nam": "title", "\xa9ART": "artist", "\xa9alb": "album", "\xa9day": "year"}
        if audio.tags:
            for k, name in tag_map.items():
                v = audio.tags.get(k)
                if v:
                    tags[name] = str(v[0])
        return {"success": True, "data": {
            "duration_s": round(audio.info.length, 1),
            "bitrate_kbps": audio.info.bitrate // 1000,
            "tags": tags
        }, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_media_files(folder: str, recursive: bool = True) -> Dict[str, Any]:
    try:
        exts = {".mp3", ".mp4", ".mkv", ".avi", ".mov", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".webm", ".wmv"}
        files = []
        if recursive:
            for root, dirs, filelist in os.walk(folder):
                for f in filelist:
                    if Path(f).suffix.lower() in exts:
                        fp = os.path.join(root, f)
                        files.append({"path": fp, "ext": Path(f).suffix.lower(), "size_mb": round(os.path.getsize(fp) / 1048576, 2)})
        else:
            for f in os.listdir(folder):
                if Path(f).suffix.lower() in exts:
                    fp = os.path.join(folder, f)
                    files.append({"path": fp, "ext": Path(f).suffix.lower(), "size_mb": round(os.path.getsize(fp) / 1048576, 2)})
        return {"success": True, "data": {"count": len(files), "files": files[:200]}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_ffprobe() -> Dict[str, Any]:
    available = _ffprobe_available()
    return {"success": True, "data": {"ffprobe": available, "mutagen": HAS_MUTAGEN}, "error": None}
