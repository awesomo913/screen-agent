import re
import json
import ipaddress
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field

def _build_result(is_valid: bool, errors: Optional[List[str]] = None, value: Any = None) -> Dict[str, Any]:
    """Helper to standardize the return dictionary structure across all validators."""
    return {
        "is_valid": is_valid,
        "errors": errors if errors is not None else [],
        "value": value
    }

def validate_email(email: str) -> Dict[str, Any]:
    """Validates an email address format."""
    if not isinstance(email, str):
        return _build_result(False, ["Email must be a string."], email)
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if re.match(pattern, email):
        return _build_result(True, [], email)
    return _build_result(False, ["Invalid email format."], email)

def validate_url(url: str) -> Dict[str, Any]:
    """Validates a standard HTTP/HTTPS URL format."""
    if not isinstance(url, str):
        return _build_result(False, ["URL must be a string."], url)
    pattern = r"^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$"
    if re.match(pattern, url):
        return _build_result(True, [], url)
    return _build_result(False, ["Invalid URL format."], url)

def validate_ip(ip: str) -> Dict[str, Any]:
    """Validates an IPv4 or IPv6 address."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return _build_result(True, [], str(ip_obj))
    except ValueError:
        return _build_result(False, [f"Invalid IP address format: {ip}"], ip)

def validate_phone(phone: str) -> Dict[str, Any]:
    """Validates a standard international phone number (E.164 basic check)."""
    if not isinstance(phone, str):
        return _build_result(False, ["Phone number must be a string."], phone)
    pattern = r"^\+?[1-9]\d{1,14}$"
    if re.match(pattern, phone.replace(" ", "").replace("-", "")):
        return _build_result(True, [], phone)
    return _build_result(False, ["Invalid phone number format."], phone)

def validate_date(date_str: str, format_str: str = "%Y-%m-%d") -> Dict[str, Any]:
    """Validates a date string against a specific datetime format."""
    try:
        parsed_date = datetime.strptime(date_str, format_str)
        return _build_result(True, [], parsed_date)
    except (ValueError, TypeError):
        return _build_result(False, [f"Date does not match format '{format_str}'."], date_str)

def validate_json(json_str: str) -> Dict[str, Any]:
    """Validates that a string is valid JSON and parses it."""
    if not isinstance(json_str, str):
        return _build_result(False, ["Input must be a string."], json_str)
    try:
        parsed = json.loads(json_str)
        return _build_result(True, [], parsed)
    except json.JSONDecodeError as e:
        return _build_result(False, [f"Invalid JSON: {str(e)}"], json_str)

def validate_schema(data: Dict[str, Any], schema: Dict[str, Type]) -> Dict[str, Any]:
    """Validates a dictionary against a simple key:Type schema."""
    if not isinstance(data, dict):
        return _build_result(False, ["Data must be a dictionary."], data)
    
    errors = []
    for key, expected_type in schema.items():
        if key not in data:
            errors.append(f"Missing required key: '{key}'.")
        elif not isinstance(data[key], expected_type):
            errors.append(f"Key '{key}' expected {expected_type.__name__}, got {type(data[key]).__name__}.")
            
    return _build_result(len(errors) == 0, errors, data)

def validate_type(value: Any, expected_type: Type) -> Dict[str, Any]:
    """Validates that a value matches the expected python type."""
    if isinstance(value, expected_type):
        return _build_result(True, [], value)
    return _build_result(False, [f"Expected {expected_type.__name__}, got {type(value).__name__}."], value)

def validate_range(value: Union[int, float], min_val: float, max_val: float) -> Dict[str, Any]:
    """Validates that a numeric value falls within an inclusive range."""
    if not isinstance(value, (int, float)):
        return _build_result(False, ["Value must be a number."], value)
    if min_val <= value <= max_val:
        return _build_result(True, [], value)
    return _build_result(False, [f"Value {value} is out of range [{min_val}, {max_val}]."], value)

def validate_length(value: Union[str, list, dict], min_len: int, max_len: int) -> Dict[str, Any]:
    """Validates the length of a string, list, or dictionary."""
    try:
        length = len(value)
        if min_len <= length <= max_len:
            return _build_result(True, [], value)
        return _build_result(False, [f"Length {length} is out of bounds [{min_len}, {max_len}]."], value)
    except TypeError:
        return _build_result(False, ["Value does not support length checking."], value)

def validate_regex(value: str, pattern: str) -> Dict[str, Any]:
    """Validates a string against a custom regular expression."""
    if not isinstance(value, str):
        return _build_result(False, ["Value must be a string."], value)
    try:
        if re.search(pattern, value):
            return _build_result(True, [], value)
        return _build_result(False, [f"Value does not match pattern: {pattern}"], value)
    except re.error as e:
        return _build_result(False, [f"Invalid regex pattern provided: {str(e)}"], value)

def validate_required(value: Any) -> Dict[str, Any]:
    """Validates that a value is not None or empty (for strings/collections)."""
    if value is None:
        return _build_result(False, ["Value is required and cannot be None."], value)
    if isinstance(value, (str, list, dict, set)) and len(value) == 0:
        return _build_result(False, ["Value is required and cannot be empty."], value)
    return _build_result(True, [], value)

def validate_unique(values: List[Any]) -> Dict[str, Any]:
    """Validates that a list contains entirely unique items (must be hashable)."""
    if not isinstance(values, list):
        return _build_result(False, ["Input must be a list."], values)
    try:
        if len(values) == len(set(values)):
            return _build_result(True, [], values)
        return _build_result(False, ["List contains duplicate items."], values)
    except TypeError:
        return _build_result(False, ["List items are not hashable, cannot verify uniqueness."], values)

def validate_custom(value: Any, validator_func: Callable[[Any], bool], error_msg: str) -> Dict[str, Any]:
    """Executes a custom boolean-returning function as a validator."""
    try:
        if validator_func(value):
            return _build_result(True, [], value)
        return _build_result(False, [error_msg], value)
    except Exception as e:
        return _build_result(False, [f"Custom validator threw an exception: {str(e)}"], value)

def create_validator(func: Callable, *args, **kwargs) -> Callable[[Any], Dict[str, Any]]:
    """Wraps a validation function to pre-configure it with specific arguments."""
    def wrapper(value: Any) -> Dict[str, Any]:
        return func(value, *args, **kwargs)
    return wrapper

def chain_validators(value: Any, validators: List[Callable[[Any], Dict[str, Any]]]) -> Dict[str, Any]:
    """Runs a value through a sequence of validators. Stops on first failure."""
    current_value = value
    for validator in validators:
        result = validator(current_value)
        if not result["is_valid"]:
            return result
        current_value = result["value"]
    return _build_result(True, [], current_value)

def validate_dict(data: Dict[str, Any], validators_map: Dict[str, List[Callable]]) -> Dict[str, Any]:
    """Validates specific dictionary keys against a list of validators."""
    if not isinstance(data, dict):
        return _build_result(False, ["Data must be a dictionary."], data)
    
    all_errors = []
    validated_data = data.copy()
    
    for key, validators in validators_map.items():
        val = data.get(key)
        chain_result = chain_validators(val, validators)
        if not chain_result["is_valid"]:
            all_errors.extend([f"Key '{key}': {err}" for err in chain_result["errors"]])
        else:
            validated_data[key] = chain_result["value"]
            
    if all_errors:
        return _build_result(False, all_errors, data)
    return _build_result(True, [], validated_data)

def validate_list(data: List[Any], validators: List[Callable]) -> Dict[str, Any]:
    """Applies a chain of validators to every item in a list."""
    if not isinstance(data, list):
        return _build_result(False, ["Input must be a list."], data)
    
    all_errors = []
    validated_list = []
    
    for i, item in enumerate(data):
        result = chain_validators(item, validators)
        if not result["is_valid"]:
            all_errors.extend([f"Index [{i}]: {err}" for err in result["errors"]])
        validated_list.append(result["value"])
        
    if all_errors:
        return _build_result(False, all_errors, data)
    return _build_result(True, [], validated_list)

def get_validation_errors(validation_result: Dict[str, Any]) -> List[str]:
    """Extracts and returns just the error messages from a validation result dictionary."""
    if not isinstance(validation_result, dict) or "errors" not in validation_result:
        return ["Invalid validation result object provided."]
    return validation_result["errors"]

def sanitize_string(value: str) -> Dict[str, Any]:
    """Strips leading/trailing whitespace and removes non-printable characters."""
    if not isinstance(value, str):
        return _build_result(False, ["Value must be a string."], value)
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value).strip()
    return _build_result(True, [], cleaned)

def sanitize_html(value: str) -> Dict[str, Any]:
    """Removes all HTML tags from a string."""
    if not isinstance(value, str):
        return _build_result(False, ["Value must be a string."], value)
    cleaned = re.sub(r'<[^>]*>', '', value)
    return _build_result(True, [], cleaned)

def normalize_whitespace(value: str) -> Dict[str, Any]:
    """Collapses multiple spaces, tabs, and newlines into single spaces."""
    if not isinstance(value, str):
        return _build_result(False, ["Value must be a string."], value)
    cleaned = re.sub(r'\s+', ' ', value).strip()
    return _build_result(True, [], cleaned)

def validate_file_path(path_str: str, must_exist: bool = False) -> Dict[str, Any]:
    """Validates that a string is a valid file path and optionally checks existence."""
    if not isinstance(path_str, str):
        return _build_result(False, ["Path must be a string."], path_str)
    try:
        path = Path(path_str)
        if must_exist and not path.exists():
            return _build_result(False, [f"File or directory does not exist: {path_str}"], path_str)
        return _build_result(True, [], path)
    except Exception as e:
        return _build_result(False, [f"Invalid path format: {str(e)}"], path_str)

def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validates password strength (min 8 chars, 1 upper, 1 lower, 1 num, 1 special)."""
    if not isinstance(password, str):
        return _build_result(False, ["Password must be a string."], None)
    
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number.")
    if not re.search(r'[\W_]', password):
        errors.append("Password must contain at least one special character.")
        
    if errors:
        return _build_result(False, errors, password)
    return _build_result(True, [], password)

def batch_validate(items: List[Dict[str, Any]], validators_map: Dict[str, List[Callable]]) -> Dict[str, Any]:
    """Validates a batch of dictionaries against a validator map."""
    if not isinstance(items, list):
        return _build_result(False, ["Items must be a list of dictionaries."], items)
    
    batch_errors = []
    validated_items = []
    
    for i, item in enumerate(items):
        result = validate_dict(item, validators_map)
        if not result["is_valid"]:
            batch_errors.append(f"Item {i}: {', '.join(result['errors'])}")
        validated_items.append(result["value"])
        
    if batch_errors:
        return _build_result(False, batch_errors, items)
    return _build_result(True, [], validated_items)
