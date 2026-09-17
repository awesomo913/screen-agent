import functools
import hashlib
import json
import pickle
import pathlib
import os
import time
import threading
import sqlite3
from collections import OrderedDict
import re
import sys
import copy
from typing import Any, Callable, Dict, List, Optional, Union, Tuple

# ---------------------------------------------------------------------------
# Global State & Thread Safety
# ---------------------------------------------------------------------------
_cache_lock = threading.RLock()
_cache_store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
_cache_stats: Dict[str, int] = {"hits": 0, "misses": 0, "evictions": 0}

def _hash_key(key: Any) -> str:
    """Deterministically hash any cache key to a string."""
    if isinstance(key, str):
        return key
    try:
        return hashlib.sha256(pickle.dumps(key)).hexdigest()
    except Exception:
        return hashlib.sha256(str(key).encode()).hexdigest()

def _is_expired(entry: Dict[str, Any]) -> bool:
    """Check if a cache entry has exceeded its TTL."""
    return time.time() > entry.get("expires_at", float("inf"))

def _match_pattern(key: str, pattern: Optional[str]) -> bool:
    """Simple glob-like pattern matching without external dependencies."""
    if not pattern:
        return True
    regex = re.compile("^" + pattern.replace("*", ".*").replace("?", ".") + "$")
    return bool(regex.match(key))

# ---------------------------------------------------------------------------
# Core In-Memory Cache Functions
# ---------------------------------------------------------------------------

def cache_set(key: Any, value: Any, ttl: float) -> Dict[str, Any]:
    """Set a value in the global in-memory cache with a TTL (seconds)."""
    with _cache_lock:
        try:
            hashed_key = _hash_key(key)
            _cache_store[hashed_key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": (time.time() + ttl) if ttl > 0 else float("inf")
            }
            return {"success": True, "key": hashed_key, "ttl": ttl}
        except Exception as e:
            return {"success": False, "error": str(e)}

def cache_get(key: Any) -> Dict[str, Any]:
    """Retrieve a value from the global in-memory cache."""
    with _cache_lock:
        try:
            hashed_key = _hash_key(key)
            if hashed_key in _cache_store:
                entry = _cache_store[hashed_key]
                if _is_expired(entry):
                    del _cache_store[hashed_key]
                    _cache_stats["misses"] += 1
                    return {"success": False, "error": "Cache entry expired", "exists": False}
                _cache_stats["hits"] += 1
                _cache_store.move_to_end(hashed_key)
                return {"success": True, "value": entry["value"], "exists": True}
            _cache_stats["misses"] += 1
            return {"success": False, "error": "Key not found", "exists": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

def cache_delete(key: Any) -> Dict[str, Any]:
    """Delete a specific key from the global in-memory cache."""
    with _cache_lock:
        try:
            hashed_key = _hash_key(key)
            if hashed_key in _cache_store:
                del _cache_store[hashed_key]
                return {"success": True, "deleted": True}
            return {"success": False, "error": "Key not found", "deleted": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

def cache_clear() -> Dict[str, Any]:
    """Clear the entire global in-memory cache."""
    with _cache_lock:
        try:
            count = len(_cache_store)
            _cache_store.clear()
            return {"success": True, "cleared_count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

def cache_exists(key: Any) -> Dict[str, Any]:
    """Check if a key exists and is not expired."""
    with _cache_lock:
        try:
            hashed_key = _hash_key(key)
            exists = hashed_key in _cache_store and not _is_expired(_cache_store[hashed_key])
            if hashed_key in _cache_store and not exists:
                del _cache_store[hashed_key]
            return {"success": True, "exists": exists}
        except Exception as e:
            return {"success": False, "error": str(e)}

def cache_get_or_set(key: Any, factory: Callable[[], Any], ttl: float) -> Dict[str, Any]:
    """Get from cache or compute using factory and store result."""
    with _cache_lock:
        try:
            hashed_key = _hash_key(key)
            if hashed_key in _cache_store:
                entry = _cache_store[hashed_key]
                if not _is_expired(entry):
                    _cache_stats["hits"] += 1
                    return {"success": True, "value": entry["value"], "source": "cache"}
                else:
                    del _cache_store[hashed_key]
            
            _cache_stats["misses"] += 1
            try:
                value = factory()
                _cache_store[hashed_key] = {
                    "value": value,
                    "created_at": time.time(),
                    "expires_at": (time.time() + ttl) if ttl > 0 else float("inf")
                }
                return {"success": True, "value": value, "source": "factory"}
            except Exception as factory_err:
                return {"success": False, "error": f"Factory execution failed: {factory_err}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

def cache_keys(pattern: Optional[str] = None) -> Dict[str, Any]:
    """Return all valid cache keys, optionally filtered by a glob pattern."""
    with _cache_lock:
        try:
            valid_keys = [
                k for k, v in _cache_store.items() if not _is_expired(v)
            ]
            matched_keys = [k for k in valid_keys if _match_pattern(k, pattern)]
            return {"success": True, "keys": matched_keys, "count": len(matched_keys)}
        except Exception as e:
            return {"success": False, "error": str(e)}

def cache_size() -> Dict[str, Any]:
    """Return the number of active entries in the cache."""
    try:
        with _cache_lock:
            size = sum(1 for v in _cache_store.values() if not _is_expired(v))
        return {"success": True, "size": size}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cache_stats() -> Dict[str, Any]:
    """Return hit rate, misses, evictions, and current size."""
    try:
        with _cache_lock:
            total_reqs = _cache_stats["hits"] + _cache_stats["misses"]
            hit_rate = (_cache_stats["hits"] / total_reqs) * 100 if total_reqs > 0 else 0.0
            return {
                "success": True,
                "total_keys": len(_cache_store),
                "hits": _cache_stats["hits"],
                "misses": _cache_stats["misses"],
                "evictions": _cache_stats["evictions"],
                "hit_rate_percentage": round(hit_rate, 2)
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

def cache_invalidate_pattern(pattern: str) -> Dict[str, Any]:
    """Remove all keys matching a glob pattern."""
    try:
        with _cache_lock:
            matched = [k for k in _cache_store if _match_pattern(k, pattern)]
            for k in matched:
                del _cache_store[k]
            return {"success": True, "invalidated_count": len(matched)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cache_warmup(keys_values: Dict[str, Any]) -> Dict[str, Any]:
    """Pre-populate cache. Accepts {key: value} or {key: {"value": v, "ttl": t}}."""
    with _cache_lock:
        try:
            count = 0
            now = time.time()
            for raw_key, data in keys_values.items():
                k = _hash_key(raw_key)
                val = data
                ttl = 3600  # Default 1 hour
                if isinstance(data, dict):
                    val = data.get("value", data)
                    ttl = data.get("ttl", 3600)
                _cache_store[k] = {
                    "value": val,
                    "created_at": now,
                    "expires_at": (now + ttl) if ttl > 0 else float("inf")
                }
                count += 1
            return {"success": True, "warmed_count": count}
        except Exception as e:
            return {"success": False, "error": str(e)}

def cache_evict_expired() -> Dict[str, Any]:
    """Manually purge all expired entries."""
    with _cache_lock:
        try:
            expired = [k for k, v in _cache_store.items() if _is_expired(v)]
            for k in expired:
                del _cache_store[k]
            if expired:
                _cache_stats["evictions"] += len(expired)
            return {"success": True, "evicted_count": len(expired)}
        except Exception as e:
            return {"success": False, "error": str(e)}

def get_cache_memory_usage() -> Dict[str, Any]:
    """Estimate memory footprint of the cache in bytes."""
    try:
        with _cache_lock:
            snapshot = copy.deepcopy(_cache_store)
        total_bytes = 0
        stack = [snapshot]
        while stack:
            obj = stack.pop()
            total_bytes += sys.getsizeof(obj)
            if isinstance(obj, dict):
                stack.extend(obj.values())
            elif isinstance(obj, (list, tuple, set, frozenset)):
                stack.extend(obj)
        return {"success": True, "bytes": total_bytes, "keys": len(snapshot)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Functional & Decorator Utilities
# ---------------------------------------------------------------------------

def memoize(func: Callable[..., Any], ttl: float) -> Dict[str, Any]:
    """Decorate a function with TTL-based memoization. Returns wrapper dict."""
    _local_cache: Dict[str, Dict[str, Any]] = {}
    _lock = threading.RLock()

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key = hashlib.sha256(pickle.dumps((args, kwargs, func.__name__))).hexdigest()
        with _lock:
            if key in _local_cache and time.time() < _local_cache[key]["expires_at"]:
                return _local_cache[key]["value"]
            val = func(*args, **kwargs)
            _local_cache[key] = {
                "value": val,
                "expires_at": (time.time() + ttl) if ttl > 0 else float("inf")
            }
            return val

    return {
        "success": True,
        "wrapped_function": wrapper,
        "original_function": func,
        "ttl": ttl,
        "cache_store": _local_cache
    }

def create_cache_decorator(backend: str, ttl: float) -> Dict[str, Any]:
    """Factory that returns a caching decorator for the specified backend."""
    try:
        def decorator(func: Callable) -> Callable:
            _func_cache: Dict[str, Dict[str, Any]] = {}
            _lock = threading.RLock()

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                key = hashlib.sha256(pickle.dumps((args, kwargs, func.__name__))).hexdigest()
                with _lock:
                    if key in _func_cache and time.time() < _func_cache[key]["expires_at"]:
                        return _func_cache[key]["value"]
                
                res = func(*args, **kwargs)
                with _lock:
                    _func_cache[key] = {
                        "value": res,
                        "expires_at": (time.time() + ttl) if ttl > 0 else float("inf")
                    }
                return res
            return wrapper

        return {"success": True, "decorator": decorator, "backend": backend, "ttl": ttl}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Cache Instance Creators
# ---------------------------------------------------------------------------

def lru_cache_create(maxsize: int) -> Dict[str, Any]:
    """Create an LRU-ordered cache instance."""
    try:
        instance = OrderedDict()
        
        def _put(key: Any, val: Any):
            hk = _hash_key(key)
            instance[hk] = val
            instance.move_to_end(hk)
            if len(instance) > maxsize:
                instance.popitem(last=False)
                
        def _get(key: Any) -> Any:
            hk = _hash_key(key)
            if hk in instance:
                instance.move_to_end(hk)
                return instance[hk]
            return None

        return {"success": True, "instance": instance, "maxsize": maxsize, "set": _put, "get": _get}
    except Exception as e:
        return {"success": False, "error": str(e)}

def ttl_cache_create(maxsize: int, ttl: float) -> Dict[str, Any]:
    """Create a fixed-size cache with TTL eviction."""
    try:
        instance: OrderedDict[str, Dict[str, Any]] = OrderedDict()

        def _put(key: Any, val: Any) -> None:
            hk = _hash_key(key)
            instance[hk] = {"value": val, "expires_at": (time.time() + ttl) if ttl > 0 else float("inf")}
            instance.move_to_end(hk)
            if len(instance) > maxsize:
                instance.popitem(last=False)

        def _get(key: Any) -> Optional[Any]:
            hk = _hash_key(key)
            if hk in instance:
                entry = instance[hk]
                if not _is_expired(entry):
                    instance.move_to_end(hk)
                    return entry["value"]
                del instance[hk]
            return None

        def _evict_expired() -> int:
            expired = [k for k, v in instance.items() if _is_expired(v)]
            for k in expired:
                del instance[k]
            return len(expired)

        return {"success": True, "instance": instance, "maxsize": maxsize, "ttl": ttl, "set": _put, "get": _get, "evict": _evict_expired}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Disk Cache Functions
# ---------------------------------------------------------------------------

def disk_cache_set(key: Any, value: Any, cache_dir: Union[str, pathlib.Path], ttl: float) -> Dict[str, Any]:
    """Persist a cache entry to disk using JSON/Pickle fallback."""
    try:
        p = pathlib.Path(cache_dir)
        p.mkdir(parents=True, exist_ok=True)
        hashed_key = _hash_key(key)
        file_path = p / f"{hashed_key}.cache"
        exp = (time.time() + ttl) if ttl > 0 else float("inf")
        metadata = {"expires_at": exp}
        
        # Attempt JSON for interoperability, fallback to base64-wrapped pickle
        try:
            payload = json.dumps({"data": value, "meta": metadata})
            mode = "text"
        except TypeError:
            payload = pickle.dumps({"data": value, "meta": metadata})
            mode = "binary"
            
        write_mode = "wb" if mode == "binary" else "w"
        with open(file_path, write_mode, encoding="utf-8" if mode == "text" else None) as f:
            if mode == "text":
                f.write(payload)
            else:
                f.write(payload)
                
        return {"success": True, "path": str(file_path), "format": mode}
    except Exception as e:
        return {"success": False, "error": str(e)}

def disk_cache_get(key: Any, cache_dir: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Retrieve a cached value from disk."""
    try:
        p = pathlib.Path(cache_dir)
        hashed_key = _hash_key(key)
        file_path = p / f"{hashed_key}.cache"
        if not file_path.exists():
            return {"success": False, "error": "File not found", "exists": False}
            
        read_mode = "rb"
        payload = file_path.read_bytes()
        
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = pickle.loads(payload)
            
        if time.time() > data.get("meta", {}).get("expires_at", float("inf")):
            os.remove(str(file_path))
            return {"success": False, "error": "Expired", "exists": False}
        return {"success": True, "value": data["data"], "exists": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def disk_cache_clear(cache_dir: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Remove all cache files from a directory."""
    try:
        p = pathlib.Path(cache_dir)
        if not p.exists() or not os.path.isdir(str(p)):
            return {"success": True, "cleared_count": 0}
        count = 0
        for f in p.glob("*.cache"):
            os.remove(str(f))
            count += 1
        return {"success": True, "cleared_count": count}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------------------------------------------------------------------
# SQLite Cache Functions
# ---------------------------------------------------------------------------

def sqlite_cache_set(key: Any, value: Any, db_path: Union[str, pathlib.Path], ttl: float) -> Dict[str, Any]:
    """Store value in SQLite database."""
    try:
        p = pathlib.Path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(p))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB,
                format TEXT,
                expires_at REAL
            )
        """)
        hashed_key = _hash_key(key)
        exp = (time.time() + ttl) if ttl > 0 else float("inf")
        
        fmt, blob = "pickle", pickle.dumps(value)
        try:
            blob = json.dumps(value).encode("utf-8")
            fmt = "json"
        except TypeError:
            pass
            
        cursor.execute("INSERT OR REPLACE INTO cache (key, value, format, expires_at) VALUES (?, ?, ?, ?)",
                       (hashed_key, blob, fmt, exp))
        conn.commit()
        conn.close()
        return {"success": True, "key": hashed_key, "db": str(p)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def sqlite_cache_get(key: Any, db_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Retrieve value from SQLite database."""
    try:
        p = pathlib.Path(db_path)
        if not p.exists():
            return {"success": False, "error": "DB not found", "exists": False}
        conn = sqlite3.connect(str(p))
        cursor = conn.cursor()
        hashed_key = _hash_key(key)
        cursor.execute("SELECT value, format, expires_at FROM cache WHERE key=?", (hashed_key,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"success": False, "error": "Not found", "exists": False}
        val_blob, fmt, exp = row
        if time.time() > exp:
            conn2 = sqlite3.connect(str(p))
            conn2.execute("DELETE FROM cache WHERE key=?", (hashed_key,))
            conn2.commit()
            conn2.close()
            return {"success": False, "error": "Expired", "exists": False}
            
        val = json.loads(val_blob.decode("utf-8")) if fmt == "json" else pickle.loads(val_blob)
        return {"success": True, "value": val, "exists": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def sqlite_cache_clear(db_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Clear all rows from the SQLite cache table."""
    try:
        p = pathlib.Path(db_path)
        if not p.exists():
            return {"success": True, "cleared_count": 0}
        conn = sqlite3.connect(str(p))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cache")
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return {"success": True, "cleared_count": count}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ---------------------------------------------------------------------------
# Export / Import Functions
# ---------------------------------------------------------------------------

def cache_export(filepath: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Serialize entire in-memory cache to disk."""
    try:
        with _cache_lock:
            data = copy.deepcopy(_cache_store)
        p = pathlib.Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        
        with open(p, "wb") as f:
            pickle.dump(data, f)
            
        # Keep a human-readable JSON manifest
        manifest = {k: str(type(v["value"])) for k, v in data.items()}
        json_path = pathlib.Path(str(p) + ".manifest.json")
        json_path.write_text(json.dumps(manifest, indent=2))
        
        return {"success": True, "exported_count": len(data), "path": str(p)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cache_import(filepath: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Load cache state from a pickle file into memory."""
    try:
        p = pathlib.Path(filepath)
        if not p.exists():
            return {"success": False, "error": "File not found"}
        with open(p, "rb") as f:
            data = pickle.load(f)
        with _cache_lock:
            count = len(data)
            _cache_store.update(data)
        return {"success": True, "imported_count": count, "path": str(p)}
    except Exception as e:
        return {"success": False, "error": str(e)}