"""
toolkit_40_speech_recognition.py
Speech-to-text using Windows Speech Recognition API (SAPI) and
optional whisper/vosk. Microphone capture and transcription.
"""
from __future__ import annotations
import subprocess
import os
from typing import Any, Dict, List

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    import vosk
    HAS_VOSK = True
except ImportError:
    HAS_VOSK = False

def _run_ps(script: str, timeout: int = 30) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {
        "speech_recognition": HAS_SR,
        "whisper": HAS_WHISPER,
        "vosk": HAS_VOSK
    }, "error": None}

def recognize_from_microphone(timeout: float = 5.0, language: str = "en-US") -> Dict[str, Any]:
    """Listen to microphone and transcribe via Google Speech API."""
    try:
        if not HAS_SR:
            return {"success": False, "data": None, "error": "speech_recognition not installed (pip install SpeechRecognition)"}
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=timeout)
        text = recognizer.recognize_google(audio, language=language)
        return {"success": True, "data": {"text": text, "language": language}, "error": None}
    except sr.WaitTimeoutError:
        return {"success": False, "data": None, "error": "No speech detected within timeout"}
    except sr.UnknownValueError:
        return {"success": False, "data": None, "error": "Could not understand audio"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def recognize_from_file(audio_path: str, language: str = "en-US") -> Dict[str, Any]:
    try:
        if not HAS_SR:
            return {"success": False, "data": None, "error": "speech_recognition not installed"}
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio, language=language)
        return {"success": True, "data": {"text": text, "file": audio_path}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def recognize_offline_sphinx(audio_path: str) -> Dict[str, Any]:
    """Offline recognition using pocketsphinx (requires extra install)."""
    try:
        if not HAS_SR:
            return {"success": False, "data": None, "error": "speech_recognition not installed"}
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_sphinx(audio)
        return {"success": True, "data": {"text": text}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def recognize_with_whisper(audio_path: str, model_size: str = "base") -> Dict[str, Any]:
    """Transcribe audio using OpenAI Whisper (offline)."""
    try:
        if not HAS_WHISPER:
            return {"success": False, "data": None, "error": "whisper not installed (pip install openai-whisper)"}
        model = whisper.load_model(model_size)
        result = model.transcribe(audio_path)
        return {"success": True, "data": {"text": result["text"], "language": result.get("language", "")}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def record_audio_to_file(output_path: str, duration: float = 5.0) -> Dict[str, Any]:
    """Record audio from microphone and save to a WAV file."""
    try:
        if not HAS_SR:
            return {"success": False, "data": None, "error": "speech_recognition not installed"}
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=duration + 1, phrase_time_limit=duration)
        with open(output_path, "wb") as f:
            f.write(audio.get_wav_data())
        return {"success": True, "data": {"saved": output_path, "duration_s": duration}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_microphones() -> Dict[str, Any]:
    try:
        if not HAS_SR:
            return {"success": False, "data": None, "error": "speech_recognition not installed"}
        mics = sr.Microphone.list_microphone_names()
        return {"success": True, "data": {"count": len(mics), "microphones": mics}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_default_microphone() -> Dict[str, Any]:
    try:
        if not HAS_SR:
            return {"success": False, "data": None, "error": "speech_recognition not installed"}
        mics = sr.Microphone.list_microphone_names()
        return {"success": True, "data": {"default_index": 0, "name": mics[0] if mics else None}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def continuous_listen_once(phrase_limit: float = 10.0) -> Dict[str, Any]:
    """Listen until a phrase ends or time limit reached."""
    try:
        if not HAS_SR:
            return {"success": False, "data": None, "error": "speech_recognition not installed"}
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source, phrase_time_limit=phrase_limit)
        try:
            text = recognizer.recognize_google(audio)
            return {"success": True, "data": {"text": text}, "error": None}
        except sr.UnknownValueError:
            return {"success": True, "data": {"text": ""}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def recognize_with_energy_threshold(audio_path: str, threshold: int = 300) -> Dict[str, Any]:
    try:
        if not HAS_SR:
            return {"success": False, "data": None, "error": "speech_recognition not installed"}
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = threshold
        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
        return {"success": True, "data": {"text": text}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def sapi_recognize_ps(duration_ms: int = 5000) -> Dict[str, Any]:
    """Use Windows SAPI for offline speech recognition via PowerShell."""
    try:
        script = '''
Add-Type -AssemblyName System.Speech
$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
$recognizer.SetInputToDefaultAudioDevice()
$grammar = New-Object System.Speech.Recognition.DictationGrammar
$recognizer.LoadGrammar($grammar)
$result = $recognizer.Recognize([TimeSpan]::FromMilliseconds(''' + str(duration_ms) + '''))
if ($result) { $result.Text } else { "" }
'''
        out = _run_ps(script, timeout=duration_ms // 1000 + 10)
        return {"success": True, "data": {"text": out.strip()}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
