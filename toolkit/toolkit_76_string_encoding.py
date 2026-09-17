"""toolkit_76_string_encoding.py
Encode and decode strings — base64, URL, hex, HTML entities, ROT13, etc.
"""
import base64
import urllib.parse
import html
import codecs
import binascii
import json
import re
import hashlib

def encode_base64(text: str, encoding: str = 'utf-8') -> dict:
    """Encode string to base64."""
    try:
        encoded = base64.b64encode(text.encode(encoding)).decode('ascii')
        return {'success': True, 'data': encoded, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decode_base64(text: str, encoding: str = 'utf-8') -> dict:
    """Decode base64 string."""
    try:
        decoded = base64.b64decode(text).decode(encoding)
        return {'success': True, 'data': decoded, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def encode_base64_url(text: str, encoding: str = 'utf-8') -> dict:
    """Encode string to URL-safe base64."""
    try:
        encoded = base64.urlsafe_b64encode(text.encode(encoding)).decode('ascii')
        return {'success': True, 'data': encoded, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decode_base64_url(text: str, encoding: str = 'utf-8') -> dict:
    """Decode URL-safe base64."""
    try:
        padding = 4 - len(text) % 4
        if padding != 4:
            text += '=' * padding
        decoded = base64.urlsafe_b64decode(text).decode(encoding)
        return {'success': True, 'data': decoded, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def url_encode(text: str) -> dict:
    """URL-encode a string."""
    try:
        return {'success': True, 'data': urllib.parse.quote(text, safe=''), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def url_decode(text: str) -> dict:
    """URL-decode a string."""
    try:
        return {'success': True, 'data': urllib.parse.unquote(text), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def encode_hex(text: str, encoding: str = 'utf-8') -> dict:
    """Encode string to hex."""
    try:
        return {'success': True, 'data': text.encode(encoding).hex(), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decode_hex(hex_str: str, encoding: str = 'utf-8') -> dict:
    """Decode hex string."""
    try:
        return {'success': True, 'data': bytes.fromhex(hex_str.replace(' ','')).decode(encoding), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def encode_html_entities(text: str) -> dict:
    """Encode HTML special characters."""
    try:
        return {'success': True, 'data': html.escape(text), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decode_html_entities(text: str) -> dict:
    """Decode HTML entities."""
    try:
        return {'success': True, 'data': html.unescape(text), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def rot13(text: str) -> dict:
    """Apply ROT13 cipher."""
    try:
        return {'success': True, 'data': codecs.encode(text, 'rot_13'), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def encode_binary(text: str, encoding: str = 'utf-8') -> dict:
    """Encode string to binary (space-separated bytes)."""
    try:
        binary = ' '.join(format(b, '08b') for b in text.encode(encoding))
        return {'success': True, 'data': binary, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decode_binary(binary_str: str, encoding: str = 'utf-8') -> dict:
    """Decode space-separated binary to string."""
    try:
        parts = binary_str.strip().split()
        chars = bytes([int(b, 2) for b in parts])
        return {'success': True, 'data': chars.decode(encoding), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def encode_ascii_codes(text: str) -> dict:
    """Encode string to comma-separated ASCII/Unicode code points."""
    try:
        codes = [str(ord(c)) for c in text]
        return {'success': True, 'data': ','.join(codes), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decode_ascii_codes(codes_str: str) -> dict:
    """Decode comma-separated code points to string."""
    try:
        text = ''.join(chr(int(c.strip())) for c in codes_str.split(','))
        return {'success': True, 'data': text, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def morse_encode(text: str) -> dict:
    """Encode text to Morse code."""
    try:
        MORSE = {'A':'.-','B':'-...','C':'-.-.','D':'-..','E':'.','F':'..-.','G':'--.','H':'....','I':'..','J':'.---','K':'-.-','L':'.-..','M':'--','N':'-.','O':'---','P':'.--.','Q':'--.-','R':'.-.','S':'...','T':'-','U':'..-','V':'...-','W':'.--','X':'-..-','Y':'-.--','Z':'--..','0':'-----','1':'.----','2':'..---','3':'...--','4':'....-','5':'.....','6':'-....','7':'--...','8':'---..','9':'----.','.'|'.':'.-.-.-.',',' :'--..-.','\'':'/'}
        words = text.upper().split()
        encoded_words = []
        for word in words:
            letters = []
            for char in word:
                if char in MORSE:
                    letters.append(MORSE[char])
            encoded_words.append(' '.join(letters))
        return {'success': True, 'data': ' / '.join(encoded_words), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def caesar_cipher(text: str, shift: int = 3) -> dict:
    """Apply Caesar cipher with given shift."""
    try:
        result = []
        for char in text:
            if char.isalpha():
                base = ord('A') if char.isupper() else ord('a')
                result.append(chr((ord(char) - base + shift) % 26 + base))
            else:
                result.append(char)
        return {'success': True, 'data': ''.join(result), 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def hash_string(text: str, algorithm: str = 'sha256', encoding: str = 'utf-8') -> dict:
    """Hash a string with md5/sha1/sha256/sha512."""
    try:
        h = hashlib.new(algorithm)
        h.update(text.encode(encoding))
        return {'success': True, 'data': {'hash': h.hexdigest(), 'algorithm': algorithm}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def encode_punycode(domain: str) -> dict:
    """Encode internationalized domain name to punycode."""
    try:
        encoded = domain.encode('idna').decode('ascii')
        return {'success': True, 'data': encoded, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def decode_punycode(domain: str) -> dict:
    """Decode punycode domain."""
    try:
        decoded = domain.encode('ascii').decode('idna')
        return {'success': True, 'data': decoded, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}

def detect_encoding_type(text: str) -> dict:
    """Detect if text looks like base64, hex, or URL-encoded."""
    try:
        results = []
        if re.match(r'^[A-Za-z0-9+/=]+$', text) and len(text) % 4 == 0:
            results.append('base64')
        if re.match(r'^[0-9a-fA-F\s]+$', text):
            results.append('hex')
        if '%' in text and re.search(r'%[0-9A-Fa-f]{2}', text):
            results.append('url_encoded')
        if re.match(r'^[01\s]+$', text):
            results.append('binary')
        if '&' in text and re.search(r'&[a-z]+;|&#\d+;', text):
            results.append('html_entities')
        return {'success': True, 'data': {'possible_types': results or ['plain_text']}, 'error': None}
    except Exception as e:
        return {'success': False, 'data': None, 'error': str(e)}
