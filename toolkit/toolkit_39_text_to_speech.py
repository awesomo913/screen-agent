"""
toolkit_39_text_to_speech.py
Text-to-speech synthesis using Windows SAPI (built-in), with voice
selection, speed/pitch control, and saving to audio files.
"""
from __future__ import annotations
import subprocess
import os
from typing import Any, Dict, List

try:
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

def _run_ps(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=60
    )
    return result.stdout.strip()

def speak(text: str, rate: int = 0, volume: int = 100) -> Dict[str, Any]:
    """Speak text using Windows SAPI. rate: -10 to 10, volume: 0-100."""
    try:
        script = '''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = ''' + str(rate) + '''
$synth.Volume = ''' + str(volume) + '''
$synth.Speak("''' + text.replace('"', "'") + '''")
"OK"
'''
        out = _run_ps(script)
        return {"success": True, "data": "Spoken: " + text[:50], "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def speak_async(text: str, rate: int = 0, volume: int = 100) -> Dict[str, Any]:
    """Start speaking without waiting for completion."""
    try:
        script = '''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = ''' + str(rate) + '''
$synth.Volume = ''' + str(volume) + '''
$synth.SpeakAsync("''' + text.replace('"', "'") + '''")
Start-Sleep -Seconds 1
"OK"
'''
        subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])
        return {"success": True, "data": "Async speech started", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_voices() -> Dict[str, Any]:
    try:
        script = '''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.GetInstalledVoices() | ForEach-Object {
    @{Name=$_.VoiceInfo.Name; Culture=$_.VoiceInfo.Culture.Name; Gender=$_.VoiceInfo.Gender.ToString(); Age=$_.VoiceInfo.Age.ToString()}
} | ConvertTo-Json -Depth 3
'''
        import json
        out = _run_ps(script)
        data = json.loads(out) if out else []
        if isinstance(data, dict): data = [data]
        return {"success": True, "data": data, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def speak_with_voice(text: str, voice_name: str, rate: int = 0) -> Dict[str, Any]:
    try:
        script = '''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice("''' + voice_name + '''")
$synth.Rate = ''' + str(rate) + '''
$synth.Speak("''' + text.replace('"', "'") + '''")
"OK"
'''
        _run_ps(script)
        return {"success": True, "data": "Spoken with voice: " + voice_name, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def save_speech_to_wav(text: str, output_path: str, rate: int = 0) -> Dict[str, Any]:
    try:
        script = '''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = ''' + str(rate) + '''
$synth.SetOutputToWaveFile("''' + output_path + '''")
$synth.Speak("''' + text.replace('"', "'") + '''")
$synth.SetOutputToDefaultAudioDevice()
"OK"
'''
        _run_ps(script)
        exists = os.path.isfile(output_path)
        return {"success": exists, "data": {"saved": output_path}, "error": None if exists else "File not created"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def speak_ssml(ssml: str) -> Dict[str, Any]:
    """Speak SSML-formatted text for advanced control."""
    try:
        script = '''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SpeakSsml(@"
''' + ssml + '''
"@)
"OK"
'''
        _run_ps(script)
        return {"success": True, "data": "SSML spoken", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def announce_time() -> Dict[str, Any]:
    try:
        import datetime
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p")
        return speak("The time is " + time_str)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def announce_date() -> Dict[str, Any]:
    try:
        import datetime
        today = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return speak("Today is " + today)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def read_file_aloud(file_path: str, rate: int = 0) -> Dict[str, Any]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read(5000)
        return speak(content, rate=rate)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def spell_word(word: str) -> Dict[str, Any]:
    """Spell out a word letter by letter."""
    try:
        spelled = " ".join(list(word))
        return speak(spelled)
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def check_tts_available() -> Dict[str, Any]:
    try:
        out = _run_ps("[System.Reflection.Assembly]::LoadWithPartialName('System.Speech'); 'OK'")
        available = "OK" in out
        return {"success": True, "data": {"sapi_available": available, "pyttsx3": HAS_PYTTSX3, "win32com": HAS_WIN32COM}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def speak_pyttsx3(text: str, rate: int = 150, volume: float = 1.0) -> Dict[str, Any]:
    """Speak using pyttsx3 if available."""
    try:
        if not HAS_PYTTSX3:
            return {"success": False, "data": None, "error": "pyttsx3 not installed (pip install pyttsx3)"}
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        engine.setProperty("volume", volume)
        engine.say(text)
        engine.runAndWait()
        return {"success": True, "data": "Spoken via pyttsx3", "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def list_voices_pyttsx3() -> Dict[str, Any]:
    try:
        if not HAS_PYTTSX3:
            return {"success": False, "data": None, "error": "pyttsx3 not installed"}
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        result = [{"id": v.id, "name": v.name, "languages": v.languages} for v in voices]
        return {"success": True, "data": result, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
