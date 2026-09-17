import requests
import jwt
import oauthlib.oauth2
import urllib.parse
import json
import time
import hashlib
import hmac
import base64
import http.cookiejar
import re
import secrets
import string
import struct
import logging
from typing import Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def login_form(driver: webdriver.Chrome, url: str, username: str, password: str, selectors: Dict[str, str]) -> Dict:
    """
    Automates form-based login using Selenium.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        driver.get(url)
        wait = WebDriverWait(driver, timeout=15)
        
        username_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selectors["username"])))
        password_elem = driver.find_element(By.CSS_SELECTOR, selectors["password"])
        submit_elem = driver.find_element(By.CSS_SELECTOR, selectors.get("submit", "button[type='submit']"))
        
        username_elem.clear()
        username_elem.send_keys(username)
        password_elem.clear()
        password_elem.send_keys(password)
        submit_elem.click()
        
        # Wait briefly for navigation or state change
        time.sleep(2)
        result["success"] = True
        result["data"] = {
            "current_url": driver.current_url,
            "cookies": driver.get_cookies()
        }
    except TimeoutException as te:
        result["error"] = f"Timeout waiting for login elements: {te}"
    except WebDriverException as wde:
        result["error"] = f"Selenium WebDriver error: {wde}"
    except Exception as e:
        result["error"] = f"Unexpected error during login: {str(e)}"
    return result


def logout(driver: webdriver.Chrome, logout_url: str) -> Dict:
    """
    Handles logout by navigating to logout_url and clearing session data.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        driver.get(logout_url)
        time.sleep(2)
        driver.delete_all_cookies()
        driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
        result["success"] = True
        result["data"] = {"status": "logged_out", "session_cleared": True}
    except Exception as e:
        result["error"] = f"Logout failed: {str(e)}"
    return result


def oauth2_authorize(client_id: str, auth_url: str, redirect_uri: str, scopes: str) -> Dict:
    """
    Constructs an OAuth2 authorization URL.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        client = oauthlib.oauth2.WebApplicationClient(client_id)
        state = secrets.token_urlsafe(16)
        auth_req_url = client.prepare_request_uri(
            uri=auth_url,
            redirect_uri=redirect_uri,
            scope=scopes.split() if scopes else None,
            state=state
        )
        result["success"] = True
        result["data"] = {"authorization_url": auth_req_url, "state": state}
    except Exception as e:
        result["error"] = f"Failed to prepare authorization URL: {str(e)}"
    return result


def oauth2_token_exchange(code: str, client_id: str, client_secret: str, token_url: str) -> Dict:
    """
    Exchanges authorization code for access/refresh tokens.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        response = requests.post(token_url, data=payload, timeout=15)
        response.raise_for_status()
        token_data = response.json()
        result["success"] = True
        result["data"] = token_data
    except requests.exceptions.RequestException as re:
        result["error"] = f"Token exchange failed: {re.response.text if hasattr(re, 'response') else str(re)}"
    except Exception as e:
        result["error"] = f"Unexpected error during token exchange: {str(e)}"
    return result


def refresh_oauth_token(refresh_token: str, client_id: str, client_secret: str, token_url: str) -> Dict:
    """
    Refreshes an expired OAuth2 access token.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        response = requests.post(token_url, data=payload, timeout=15)
        response.raise_for_status()
        token_data = response.json()
        result["success"] = True
        result["data"] = token_data
    except requests.exceptions.RequestException as re:
        result["error"] = f"Token refresh failed: {re.response.text if hasattr(re, 'response') else str(re)}"
    except Exception as e:
        result["error"] = f"Unexpected error during token refresh: {str(e)}"
    return result


def create_jwt(payload: Dict, secret: str, algorithm: str = "HS256") -> Dict:
    """
    Encodes a JWT token.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        token = jwt.encode(payload, secret, algorithm=algorithm)
        result["success"] = True
        result["data"] = {"token": token}
    except Exception as e:
        result["error"] = f"JWT creation failed: {str(e)}"
    return result


def verify_jwt(token: str, secret: str, algorithm: str = "HS256") -> Dict:
    """
    Decodes and verifies a JWT token.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        result["success"] = True
        result["data"] = {"payload": payload, "valid": True}
    except jwt.ExpiredSignatureError:
        result["error"] = "Token has expired"
    except jwt.InvalidTokenError as e:
        result["error"] = f"Invalid token: {str(e)}"
    except Exception as e:
        result["error"] = f"Unexpected error during verification: {str(e)}"
    return result


def basic_auth_request(url: str, username: str, password: str) -> Dict:
    """
    Performs an HTTP GET with HTTP Basic Authentication.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        resp = requests.get(url, auth=(username, password), timeout=15)
        result["success"] = True
        result["data"] = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text
        }
    except requests.exceptions.RequestException as re:
        result["error"] = f"Request failed: {str(re)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    return result


def bearer_auth_request(url: str, token: str, method: str = "GET", data: Any = None) -> Dict:
    """
    Performs an HTTP request with Bearer token authentication.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.request(method, url, headers=headers, json=data, timeout=15)
        result["success"] = True
        result["data"] = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text
        }
    except requests.exceptions.RequestException as re:
        result["error"] = f"Request failed: {str(re)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    return result


def api_key_auth(url: str, api_key: str, header_name: str) -> Dict:
    """
    Performs an HTTP GET with a custom API key header.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        headers = {header_name: api_key}
        resp = requests.get(url, headers=headers, timeout=15)
        result["success"] = True
        result["data"] = {
            "status_code": resp.status_code,
            "body": resp.text
        }
    except requests.exceptions.RequestException as re:
        result["error"] = f"Request failed: {str(re)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    return result


def session_login(url: str, credentials: Dict, session: requests.Session) -> Dict:
    """
    Authenticates using requests.Session with form/JSON credentials.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        resp = session.post(url, json=credentials, timeout=15)
        resp.raise_for_status()
        result["success"] = True
        result["data"] = {
            "status_code": resp.status_code,
            "cookies": dict(session.cookies)
        }
    except requests.exceptions.RequestException as re:
        result["error"] = f"Session login failed: {str(re)}"
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    return result


def save_session_cookies(session: requests.Session, filepath: str) -> Dict:
    """
    Saves session cookies to disk using http.cookiejar compatibility.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        cj = http.cookiejar.MozillaCookieJar(filepath)
        cj.load = lambda: None  # Override load to prevent errors
        for cookie in session.cookies:
            cj.set_cookie(cookie)
        cj.save(ignore_discard=True, ignore_expires=True)
        result["success"] = True
        result["data"] = {"path": filepath, "cookies_saved": len(cj)}
    except Exception as e:
        result["error"] = f"Failed to save cookies: {str(e)}"
    return result


def load_session_cookies(filepath: str) -> Dict:
    """
    Loads cookies from disk into a cookiejar and returns them.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        cj = http.cookiejar.MozillaCookieJar(filepath)
        cj.load(ignore_discard=True, ignore_expires=True)
        cookies_dict = {c.name: c.value for c in cj}
        result["success"] = True
        result["data"] = cookies_dict
    except Exception as e:
        result["error"] = f"Failed to load cookies: {str(e)}"
    return result


def check_auth_status(driver: webdriver.Chrome, indicator: str) -> Dict:
    """
    Checks DOM for an authentication status indicator element.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        wait = WebDriverWait(driver, timeout=5)
        elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, indicator)))
        result["success"] = True
        result["data"] = {
            "is_authenticated": elem.is_displayed(),
            "text_content": elem.text.strip()
        }
    except TimeoutException:
        result["success"] = True
        result["data"] = {"is_authenticated": False, "indicator_found": False}
    except Exception as e:
        result["error"] = f"Auth status check failed: {str(e)}"
    return result


def handle_mfa_totp(secret: str) -> Dict:
    """
    Generates a TOTP code for MFA based on RFC 6238.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        # Decode base32 secret
        key = base64.b32decode(secret.upper().strip())
        time_step = 30
        current_time = int(time.time())
        msg = struct.pack(">Q", current_time // time_step)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0xF
        binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
        otp = str(binary % 1000000).zfill(6)
        
        result["success"] = True
        result["data"] = {"totp": otp, "expires_in": time_step - (current_time % time_step)}
    except Exception as e:
        result["error"] = f"TOTP generation failed: {str(e)}"
    return result


def generate_csrf_token() -> Dict:
    """
    Generates a cryptographically secure CSRF token.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        token = secrets.token_urlsafe(32)
        result["success"] = True
        result["data"] = {"csrf_token": token}
    except Exception as e:
        result["error"] = f"CSRF generation failed: {str(e)}"
    return result


def extract_csrf_token(page_source: str, pattern: str) -> Dict:
    """
    Extracts CSRF token from HTML source using regex.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        match = re.search(pattern, page_source)
        if match:
            token = match.group(1) if match.groups() else match.group(0)
            result["success"] = True
            result["data"] = {"csrf_token": token}
        else:
            result["error"] = "CSRF token pattern not found in source"
    except re.error as re_err:
        result["error"] = f"Invalid regex pattern: {str(re_err)}"
    except Exception as e:
        result["error"] = f"Extraction failed: {str(e)}"
    return result


def handle_recaptcha_v2(driver: webdriver.Chrome, site_key: str) -> Dict:
    """
    Waits for manual reCAPTCHA v2 completion or DOM indication of success.
    Note: Automated solving requires third-party services and is omitted for compliance.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    start = time.time()
    try:
        WebDriverWait(driver, timeout=60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".recaptcha-checkbox-checkmark[aria-checked='true']"))
        )
        elapsed = time.time() - start
        result["success"] = True
        result["data"] = {"status": "completed", "time_taken_seconds": round(elapsed, 2)}
    except TimeoutException:
        result["error"] = "reCAPTCHA not solved within timeout period"
    except Exception as e:
        result["error"] = f"reCAPTCHA handling failed: {str(e)}"
    return result


def wait_for_auth_redirect(driver: webdriver.Chrome, target_url: str, timeout: int = 30) -> Dict:
    """
    Waits for the browser to redirect to a target URL after authentication.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: target_url in d.current_url or target_url.rstrip("/") == d.current_url.rstrip("/")
        )
        result["success"] = True
        result["data"] = {"final_url": driver.current_url}
    except TimeoutException:
        result["error"] = f"Did not redirect to {target_url} within {timeout}s"
    except Exception as e:
        result["error"] = f"Redirect wait failed: {str(e)}"
    return result


def manage_auth_headers(headers: Dict, auth_type: str, credentials: Any) -> Dict:
    """
    Updates headers dictionary based on authentication type.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        auth_type = auth_type.lower()
        updated = headers.copy()
        
        if auth_type == "basic":
            b64 = base64.b64encode(f"{credentials[0]}:{credentials[1]}".encode()).decode()
            updated["Authorization"] = f"Basic {b64}"
        elif auth_type == "bearer":
            updated["Authorization"] = f"Bearer {credentials}"
        elif auth_type == "api_key":
            if isinstance(credentials, dict):
                updated[credentials.get("header", "X-API-KEY")] = credentials.get("key")
            else:
                updated["X-API-KEY"] = credentials
        elif auth_type == "oauth2":
            updated["Authorization"] = f"Bearer {credentials['access_token']}"
            
        result["success"] = True
        result["data"] = {"headers": updated}
    except Exception as e:
        result["error"] = f"Header management failed: {str(e)}"
    return result


def validate_password_strength(password: str) -> Dict:
    """
    Validates password complexity based on standard rules.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        criteria = {
            "length_>=8": len(password) >= 8,
            "uppercase": bool(re.search(r"[A-Z]", password)),
            "lowercase": bool(re.search(r"[a-z]", password)),
            "digit": bool(re.search(r"\d", password)),
            "special_char": bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", password))
        }
        passed = sum(criteria.values())
        score = round((passed / len(criteria)) * 100)
        is_valid = passed >= 4 and len(password) >= 8
        
        result["success"] = True
        result["data"] = {
            "valid": is_valid,
            "score": score,
            "criteria_met": criteria
        }
    except Exception as e:
        result["error"] = f"Validation failed: {str(e)}"
    return result


def generate_secure_password(length: int = 16) -> Dict:
    """
    Generates a cryptographically secure random password.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        if length < 8:
            result["error"] = "Password length must be at least 8"
            return result
            
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        while True:
            pwd = "".join(secrets.choice(alphabet) for _ in range(length))
            if (any(c.islower() for c in pwd) and
                any(c.isupper() for c in pwd) and
                any(c.isdigit() for c in pwd) and
                any(c in string.punctuation for c in pwd)):
                break
        result["success"] = True
        result["data"] = {"password": pwd}
    except Exception as e:
        result["error"] = f"Generation failed: {str(e)}"
    return result


def hash_password(password: str, salt: str) -> Dict:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with provided salt.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        salt_bytes = salt.encode("utf-8")
        pwd_bytes = password.encode("utf-8")
        dk = hashlib.pbkdf2_hmac("sha256", pwd_bytes, salt_bytes, iterations=100_000)
        hash_hex = base64.b64encode(dk).decode("utf-8")
        result["success"] = True
        result["data"] = {"hash": f"pbkdf2_sha256$100000${salt}${hash_hex}"}
    except Exception as e:
        result["error"] = f"Hashing failed: {str(e)}"
    return result


def verify_password_hash(password: str, hashed: str) -> Dict:
    """
    Verifies a password against a stored PBKDF2 hash.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            result["error"] = "Invalid hash format"
            return result
            
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]
        
        new_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations=iterations)
        new_hash_b64 = base64.b64encode(new_hash).decode("utf-8")
        
        matches = hmac.compare_digest(new_hash_b64, expected_hash)
        result["success"] = True
        result["data"] = {"match": matches}
    except Exception as e:
        result["error"] = f"Verification failed: {str(e)}"
    return result


def create_auth_session(base_url: str, auth_config: Dict) -> Dict:
    """
    Creates and configures a requests.Session with authentication settings.
    """
    result: Dict[str, Any] = {"success": False, "data": None, "error": None}
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": "ScreenAgentToolkit/1.0"})
        session.headers.update(auth_config.get("headers", {}))
        
        auth_type = auth_config.get("type", "").lower()
        creds = auth_config.get("credentials")
        
        if auth_type == "basic" and creds:
            session.auth = (creds["username"], creds["password"])
        elif auth_type == "bearer" and creds:
            session.headers["Authorization"] = f"Bearer {creds['token']}"
        elif auth_type == "api_key" and creds:
            header = creds.get("header", "X-API-KEY")
            session.headers[header] = creds["key"]
            
        if auth_config.get("cookies"):
            for name, value in auth_config.get("cookies").items():
                session.cookies.set(name, value)
                
        session.base_url = base_url  # Attach metadata
        
        result["success"] = True
        result["data"] = {
            "session_id": id(session),
            "configured": True,
            "base_url": base_url,
            "auth_type": auth_type
        }
    except Exception as e:
        result["error"] = f"Session creation failed: {str(e)}"
    return result