import urllib.parse
import re
import json
import os
import pathlib
import ipaddress
import socket
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Union

@dataclass
class URLComponents:
    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str
    hostname: Optional[str]
    port: Optional[int]
    is_ip: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class URLParserError(Exception):
    """Custom exception for URL parsing errors."""
    pass

def parse_url(url: str) -> Dict[str, Any]:
    """Parses a URL into its constituent components."""
    try:
        parsed = urllib.parse.urlparse(url)
        is_ip = False
        if parsed.hostname:
            try:
                ipaddress.ip_address(parsed.hostname)
                is_ip = True
            except ValueError:
                pass
                
        components = URLComponents(
            scheme=parsed.scheme,
            netloc=parsed.netloc,
            path=parsed.path,
            params=parsed.params,
            query=parsed.query,
            fragment=parsed.fragment,
            hostname=parsed.hostname,
            port=parsed.port,
            is_ip=is_ip
        )
        return components.to_dict()
    except Exception as e:
        raise URLParserError(f"Failed to parse URL '{url}': {e}")

def build_url(scheme: str = '', netloc: str = '', path: str = '', 
              params: str = '', query: str = '', fragment: str = '') -> str:
    """Reconstructs a URL from its components."""
    try:
        return urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment))
    except Exception as e:
        raise URLParserError(f"Failed to build URL: {e}")

def get_domain(url: str) -> str:
    """Extracts the root domain or IP address from the URL."""
    parsed = parse_url(url)
    hostname = parsed.get("hostname", "")
    if not hostname:
        return ""
    if parsed.get("is_ip"):
        return hostname
    
    parts = hostname.split('.')
    # Simplistic heuristic for standard domains. 
    # Production-level strict TLD extraction requires an external library (like tldextract).
    if len(parts) > 2 and parts[-2] in ['co', 'com', 'gov', 'edu', 'org', 'net']:
        return '.'.join(parts[-3:])
    elif len(parts) >= 2:
        return '.'.join(parts[-2:])
    return hostname

def get_subdomain(url: str) -> str:
    """Extracts the subdomain from the URL, excluding www."""
    parsed = parse_url(url)
    hostname = parsed.get("hostname", "")
    domain = get_domain(url)
    
    if not hostname or not domain or hostname == domain:
        return ""
    
    subdomain = hostname.replace(f".{domain}", "")
    if subdomain == "www":
        return ""
    if subdomain.startswith("www."):
        return subdomain[4:]
    return subdomain

def get_path(url: str) -> str:
    """Returns the path component of the URL."""
    return parse_url(url).get("path", "")

def get_query_params(url: str) -> Dict[str, List[str]]:
    """Returns a dictionary of query parameters."""
    query_string = parse_url(url).get("query", "")
    return urllib.parse.parse_qs(query_string)

def set_query_params(url: str, params: Dict[str, Any]) -> str:
    """Overwrites existing query parameters with a new dictionary."""
    try:
        parsed = urllib.parse.urlparse(url)
        # Convert lists to single values for urlencode if they only have one item
        flat_params = []
        for k, v in params.items():
            if isinstance(v, list):
                for item in v:
                    flat_params.append((k, item))
            else:
                flat_params.append((k, v))
                
        new_query = urllib.parse.urlencode(flat_params)
        return urllib.parse.urlunparse(parsed._replace(query=new_query))
    except Exception as e:
        raise URLParserError(f"Failed to set query params on '{url}': {e}")

def add_query_param(url: str, key: str, value: Any) -> str:
    """Adds a single query parameter to the URL."""
    params = get_query_params(url)
    if key in params:
        params[key].append(str(value))
    else:
        params[key] = [str(value)]
    return set_query_params(url, params)

def remove_query_param(url: str, key: str) -> str:
    """Removes a specified query parameter from the URL."""
    params = get_query_params(url)
    if key in params:
        del params[key]
    return set_query_params(url, params)

def get_fragment(url: str) -> str:
    """Returns the fragment (anchor) component of the URL."""
    return parse_url(url).get("fragment", "")

def encode_url(url: str) -> str:
    """URL-encodes a string."""
    try:
        return urllib.parse.quote(url, safe=':/?&=+#')
    except TypeError as e:
        raise URLParserError(f"Failed to encode URL: {e}")

def decode_url(url: str) -> str:
    """URL-decodes a string."""
    try:
        return urllib.parse.unquote(url)
    except TypeError as e:
        raise URLParserError(f"Failed to decode URL: {e}")

def normalize_url(url: str) -> str:
    """Normalizes a URL (lowercasing, removing default ports, removing trailing slashes)."""
    try:
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        
        # Remove default ports
        if (scheme == 'http' and netloc.endswith(':80')):
            netloc = netloc[:-3]
        elif (scheme == 'https' and netloc.endswith(':443')):
            netloc = netloc[:-4]
            
        path = parsed.path
        if path == '/' and not parsed.query and not parsed.fragment:
            path = ''
        elif path.endswith('/') and len(path) > 1:
            path = path.rstrip('/')
            
        return urllib.parse.urlunparse((scheme, netloc, path, parsed.params, parsed.query, parsed.fragment))
    except Exception as e:
        raise URLParserError(f"Failed to normalize URL '{url}': {e}")

def validate_url(url: str) -> bool:
    """Checks if a string is a formally valid URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except ValueError:
        return False

def is_absolute_url(url: str) -> bool:
    """Checks if the URL is absolute (contains a scheme and netloc)."""
    return validate_url(url)

def is_relative_url(url: str) -> bool:
    """Checks if the URL is relative (lacks a scheme or netloc)."""
    try:
        parsed = urllib.parse.urlparse(url)
        return not bool(parsed.scheme and parsed.netloc) and bool(parsed.path)
    except ValueError:
        return False

def join_urls(base: str, url: str) -> str:
    """Safely joins a base URL with a relative or absolute URL."""
    try:
        return urllib.parse.urljoin(base, url)
    except Exception as e:
        raise URLParserError(f"Failed to join URLs '{base}' and '{url}': {e}")

def get_base_url(url: str) -> str:
    """Returns the base URL (scheme + netloc)."""
    parsed = parse_url(url)
    if not parsed.get("scheme") or not parsed.get("netloc"):
        return ""
    return f"{parsed['scheme']}://{parsed['netloc']}"

def extract_urls_from_text(text: str) -> List[str]:
    """Extracts all valid URLs from a block of text using regex."""
    if not isinstance(text, str):
        return []
    url_pattern = re.compile(r'(https?://[^\s]+)')
    return url_pattern.findall(text)

def get_file_extension_from_url(url: str) -> str:
    """Extracts the file extension from the URL path."""
    path = get_path(url)
    if not path:
        return ""
    ext = pathlib.Path(path).suffix
    return ext.lower()

def url_to_filename(url: str) -> str:
    """Converts a URL to a safe filename for local storage."""
    parsed = parse_url(url)
    clean_str = f"{parsed.get('netloc', '')}{parsed.get('path', '')}"
    if not clean_str:
        return "default_url_file"
        
    # Replace invalid filename characters with underscores
    safe_filename = re.sub(r'[\/:*?"<>|]', '_', clean_str)
    return safe_filename.strip('_')

def compare_urls(url1: str, url2: str) -> bool:
    """Compares two URLs for equivalence after normalization."""
    try:
        return normalize_url(url1) == normalize_url(url2)
    except URLParserError:
        return False

def get_url_depth(url: str) -> int:
    """Calculates the depth of the URL path (number of slash-separated directories)."""
    path = get_path(url)
    if not path or path == '/':
        return 0
    return len([p for p in path.split('/') if p])

def shorten_url_path(url: str, max_depth: int = 1) -> str:
    """Truncates the URL path to a maximum depth while retaining query/fragment."""
    try:
        parsed = urllib.parse.urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        
        if len(path_parts) <= max_depth:
            return url
            
        new_path = '/' + '/'.join(path_parts[:max_depth])
        if parsed.path.endswith('/'):
            new_path += '/'
            
        return urllib.parse.urlunparse(parsed._replace(path=new_path))
    except Exception as e:
        raise URLParserError(f"Failed to shorten URL path for '{url}': {e}")

def batch_parse_urls(urls: List[str]) -> Dict[str, Dict[str, Any]]:
    """Parses a list of URLs and returns a dictionary mapped by original URL."""
    results = {}
    for url in urls:
        try:
            results[url] = parse_url(url)
        except Exception as e:
            results[url] = {"error": str(e)}
    return results

if __name__ == "__main__":
    # Internal module testing
    pass
