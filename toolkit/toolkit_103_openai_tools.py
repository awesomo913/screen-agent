"""toolkit_103_openai_tools.py
OpenAI-compatible API tools for chat, code generation, translation via free endpoints.
"""
import json, urllib.request, re
try:
    import requests; HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

def _post(url, payload, headers):
    try:
        body = json.dumps(payload).encode()
        if HAS_REQUESTS:
            r = requests.post(url, json=payload, headers=headers, timeout=60)
            return r.status_code, r.json()
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return 0, {"error": str(e)}

def chat_completion(messages: list, model: str = "gpt-3.5-turbo", api_key: str = "", base_url: str = "https://api.openai.com/v1", max_tokens: int = 500, temperature: float = 0.7) -> dict:
    """Send a chat completion request to any OpenAI-compatible API."""
    try:
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        status, resp = _post(base_url + "/chat/completions", payload, headers)
        if status == 200:
            text = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "data": {"text": text, "model": resp.get("model"), "usage": resp.get("usage")}, "error": None}
        return {"success": False, "data": None, "error": resp.get("error", {}).get("message", "HTTP " + str(status))}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def simple_question(question: str, api_key: str = "", model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1") -> dict:
    """Ask a single question."""
    return chat_completion([{"role": "user", "content": question}], model=model, api_key=api_key, base_url=base_url)

def chat_with_system(user_message: str, system_prompt: str, api_key: str = "", model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1") -> dict:
    """Chat with a system prompt."""
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
    return chat_completion(messages, model=model, api_key=api_key, base_url=base_url)

def list_models(api_key: str = "", base_url: str = "https://api.openai.com/v1") -> dict:
    """List models from OpenAI-compatible API."""
    try:
        headers = {"Authorization": "Bearer " + api_key}
        if HAS_REQUESTS:
            r = requests.get(base_url + "/models", headers=headers, timeout=15)
            if r.status_code == 200:
                return {"success": True, "data": [m.get("id","") for m in r.json().get("data",[])], "error": None}
        return {"success": False, "data": None, "error": "requests not installed"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def chat_with_ollama(prompt: str, model: str = "llama2", host: str = "http://localhost:11434", system: str = "") -> dict:
    """Chat with a local Ollama model."""
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        status, resp = _post(host + "/api/chat", {"model": model, "messages": messages, "stream": False}, {"Content-Type": "application/json"})
        if status == 200:
            return {"success": True, "data": {"text": resp.get("message", {}).get("content",""), "model": model}, "error": None}
        return {"success": False, "data": None, "error": str(resp)}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def generate_code_llm(description: str, language: str = "python", api_key: str = "", model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1") -> dict:
    """Generate code from description using LLM."""
    try:
        prompt = "Write " + language + " code for: " + description + ". Return only the code."
        result = chat_completion([{"role": "user", "content": prompt}], model=model, api_key=api_key, base_url=base_url)
        if result["success"]:
            text = result["data"]["text"]
            code_match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
            result["data"]["code"] = code_match.group(1).strip() if code_match else text.strip()
        return result
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def summarize_text(text: str, max_words: int = 100, api_key: str = "", model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1") -> dict:
    """Summarize text using LLM."""
    prompt = "Summarize in " + str(max_words) + " words or less: " + text[:3000]
    return chat_completion([{"role": "user", "content": prompt}], model=model, api_key=api_key, base_url=base_url, max_tokens=max_words*2)

def translate_text(text: str, target_language: str = "Spanish", api_key: str = "", model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1") -> dict:
    """Translate text using LLM."""
    return chat_completion([{"role": "user", "content": "Translate to " + target_language + ": " + text}], model=model, api_key=api_key, base_url=base_url)

def fix_code_llm(code: str, error: str = "", language: str = "python", api_key: str = "", model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1") -> dict:
    """Ask LLM to fix buggy code."""
    prompt = "Fix this " + language + " code" + (" Error: " + error if error else "") + ":\n```\n" + code + "\n```\nReturn only fixed code."
    result = chat_completion([{"role": "user", "content": prompt}], model=model, api_key=api_key, base_url=base_url)
    if result["success"]:
        text = result["data"]["text"]
        m = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        result["data"]["fixed_code"] = m.group(1).strip() if m else text.strip()
    return result

def explain_code_llm(code: str, language: str = "python", api_key: str = "", model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1") -> dict:
    """Ask LLM to explain code in plain English."""
    prompt = "Explain this " + language + " code in plain English:\n```\n" + code + "\n```"
    return chat_completion([{"role": "user", "content": prompt}], model=model, api_key=api_key, base_url=base_url)

def check_grammar_llm(text: str, api_key: str = "", model: str = "gpt-3.5-turbo", base_url: str = "https://api.openai.com/v1") -> dict:
    """Check and fix grammar using LLM."""
    return chat_completion([{"role": "user", "content": "Fix grammar and spelling, return only corrected text: " + text}], model=model, api_key=api_key, base_url=base_url)