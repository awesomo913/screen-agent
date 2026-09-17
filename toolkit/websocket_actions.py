import asyncio
import json
import threading
import time
import ssl
import logging
import queue
import uuid
import functools
from typing import Dict, Any, Optional, Callable, Union, List, Set

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException, InvalidURI

# Configure logging
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Global Runtime State
# ─────────────────────────────────────────────────────────────────────────────
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(
    target=_loop.run_forever, daemon=True, name="WS-Agent-EventLoop"
)
_loop_thread.start()

_reg_lock = threading.Lock()
_connections: Dict[str, Dict[str, Any]] = {}
_servers: Dict[str, Dict[str, Any]] = {}

# ─────────────────────────────────────────────────────────────────────────────
# Internal Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _run_async(coro, timeout: float = 15.0) -> Dict[str, Any]:
    """Bridge synchronous caller to internal async loop."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    try:
        return future.result(timeout=timeout)
    except asyncio.TimeoutError:
        future.cancel()
        return {"success": False, "error": "Async operation timed out", "data": None}
    except Exception as exc:
        logger.error(f"Async execution failed: {exc}", exc_info=True)
        return {"success": False, "error": str(exc), "data": None}


def _validate_connection(conn_id: str) -> Dict[str, Any]:
    """Thread-safe connection validation."""
    with _reg_lock:
        conn = _connections.get(conn_id)
    if not conn:
        return {"valid": False, "error": f"Connection '{conn_id}' not found."}
    return {"valid": True, "state": conn}


def _safe_callback(callback: Optional[Callable], *args):
    """Execute callback safely, avoiding event loop blockage."""
    if not callback:
        return
    try:
        if asyncio.iscoroutinefunction(callback):
            asyncio.ensure_future(callback(*args))
        else:
            asyncio.get_event_loop().run_in_executor(None, functools.partial(callback, *args))
    except Exception as e:
        logger.error(f"Callback execution failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Core Async Implementations
# ─────────────────────────────────────────────────────────────────────────────
async def _async_connect(url: str, headers: Optional[Dict[str, str]], ssl_context: Optional[ssl.SSLContext]) -> Dict:
    try:
        conn_id = str(uuid.uuid4())
        ws = await websockets.connect(url, extra_headers=headers, ssl=ssl_context)
        state = {
            "ws": ws, "url": url, "headers": headers or {}, "ssl_context": ssl_context,
            "status": "open", "listener_task": None,
            "callbacks": {"on_open": None, "on_close": None, "on_error": None, "on_message": None},
            "channels": set(), "message_buffer": asyncio.Queue(),
            "reconnect_lock": asyncio.Lock()
        }
        with _reg_lock:
            _connections[conn_id] = state
        _safe_callback(state["callbacks"]["on_open"], conn_id)
        return {"success": True, "data": {"connection_id": conn_id, "status": "open"}, "error": None}
    except Exception as e:
        logger.error(f"ws_connect failed: {e}")
        return {"success": False, "data": None, "error": str(e)}


async def _async_disconnect(conn_id: str) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    
    conn = valid["state"]
    ws = conn["ws"]
    try:
        if conn["listener_task"]:
            conn["listener_task"].cancel()
            try: await conn["listener_task"]
            except asyncio.CancelledError: pass
        
        await ws.close()
        conn["status"] = "closed"
        with _reg_lock:
            _connections.pop(conn_id, None)
        _safe_callback(conn["callbacks"]["on_close"], conn_id, 1000, "Normal Closure")
        return {"success": True, "data": {"connection_id": conn_id, "status": "closed"}, "error": None}
    except Exception as e:
        logger.error(f"ws_disconnect error: {e}")
        return {"success": False, "error": str(e), "data": None}


async def _async_send(conn_id: str, message: str) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    try:
        conn = valid["state"]
        await conn["ws"].send(message)
        return {"success": True, "data": {"bytes_sent": len(message.encode())}, "error": None}
    except Exception as e:
        logger.error(f"ws_send error: {e}")
        return {"success": False, "error": str(e), "data": None}


async def _async_send_json(conn_id: str, data: Any) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    try:
        payload = json.dumps(data)
        await _async_send(conn_id, payload)  # reuse send logic inside loop
        return {"success": True, "data": {"json_payload": payload}, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


async def _async_receive(conn_id: str, timeout: float) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    try:
        conn = valid["state"]
        msg = await asyncio.wait_for(conn["ws"].recv(), timeout=timeout)
        return {"success": True, "data": {"message": msg}, "error": None}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Receive timeout", "data": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


async def _async_receive_json(conn_id: str, timeout: float) -> Dict:
    res = await _async_receive(conn_id, timeout)
    if res["success"]:
        try:
            res["data"]["json_data"] = json.loads(res["data"]["message"])
            return res
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON: {e}", "data": None}
    return res


async def _listener_loop(conn_id: str, conn_state: Dict):
    while True:
        try:
            msg = await conn_state["ws"].recv()
            channel_match = True
            if conn_state["channels"]:
                try:
                    parsed = json.loads(msg)
                    ch = parsed.get("channel", "")
                    channel_match = ch in conn_state["channels"]
                except json.JSONDecodeError:
                    channel_match = len(conn_state["channels"]) == 0
            
            if channel_match:
                _safe_callback(conn_state["callbacks"]["on_message"], conn_id, msg)
                if not conn_state["channels"]:
                    await conn_state["message_buffer"].put(msg)
        except asyncio.CancelledError:
            break
        except ConnectionClosed:
            conn_state["status"] = "closed"
            _safe_callback(conn_state["callbacks"]["on_close"], conn_id, None, "Connection closed")
            break
        except Exception as e:
            conn_state["status"] = "error"
            _safe_callback(conn_state["callbacks"]["on_error"], conn_id, e)
            break


async def _async_listen(conn_id: str, callback: Callable) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    conn = valid["state"]
    conn["callbacks"]["on_message"] = callback
    if not conn["listener_task"] or conn["listener_task"].done():
        conn["listener_task"] = asyncio.create_task(_listener_loop(conn_id, conn))
    return {"success": True, "data": {"listening": True}, "error": None}


async def _async_stop_listening(conn_id: str) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    conn = valid["state"]
    if conn["listener_task"]:
        conn["listener_task"].cancel()
        conn["listener_task"] = None
    return {"success": True, "data": {"listening": False}, "error": None}


async def _async_ping(conn_id: str) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    try:
        start = time.monotonic()
        await valid["state"]["ws"].ping()
        latency = (time.monotonic() - start) * 1000
        return {"success": True, "data": {"latency_ms": round(latency, 2)}, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


async def _async_get_state(conn_id: str) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    return {"success": True, "data": {"connection_id": conn_id, "status": valid["state"]["status"]}, "error": None}


async def _async_reconnect(conn_id: str, max_retries: int) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return await _async_connect(
            valid.get("url", ""), valid.get("headers", {}), valid.get("ssl_context")
        )
    conn = valid["state"]
    await _async_disconnect(conn_id)
    delay = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            res = await _async_connect(conn["url"], conn["headers"], conn["ssl_context"])
            if res["success"]:
                new_id = res["data"]["connection_id"]
                _safe_callback(conn["callbacks"]["on_open"], new_id)
                return {"success": True, "data": new_id, "error": None}
        except Exception as e:
            logger.warning(f"Reconnect attempt {attempt} failed: {e}")
        time.sleep(delay)
        delay = min(delay * 2, 30.0)
    return {"success": False, "error": "Max retries exceeded", "data": None}


async def _async_server_handler(websocket, path, server_id: str):
    with _reg_lock:
        srv = _servers.get(server_id)
        if not srv: return
        client_id = str(uuid.uuid4())
        srv["clients"][client_id] = websocket
        srv["client_map"][websocket] = client_id
    try:
        await srv["handler"](websocket, path, client_id)
    finally:
        with _reg_lock:
            srv["clients"].pop(client_id, None)
            srv["client_map"].pop(websocket, None)


async def _async_create_server(host: str, port: int, handler: Callable) -> Dict:
    server_id = str(uuid.uuid4())
    srv_state = {
        "clients": {}, "client_map": {}, "handler": handler,
        "server_obj": None, "active": True
    }
    try:
        srv = await websockets.serve(
            functools.partial(_async_server_handler, server_id=server_id),
            host, port
        )
        srv_state["server_obj"] = srv
        with _reg_lock:
            _servers[server_id] = srv_state
        return {"success": True, "data": {"server_id": server_id, "host": host, "port": port}, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


async def _async_stop_server(server_id: str) -> Dict:
    with _reg_lock:
        srv = _servers.get(server_id)
    if not srv:
        return {"success": False, "error": "Server not found", "data": None}
    srv["active"] = False
    srv["server_obj"].close()
    await srv["server_obj"].wait_closed()
    with _reg_lock:
        _servers.pop(server_id, None)
    return {"success": True, "data": {"server_id": server_id, "status": "stopped"}, "error": None}


async def _async_broadcast(server_id: str, message: str) -> Dict:
    with _reg_lock:
        srv = _servers.get(server_id)
    if not srv:
        return {"success": False, "error": "Server not found", "data": None}
    sent = 0
    errors = []
    for ws in list(srv["clients"].values()):
        try:
            await ws.send(message)
            sent += 1
        except Exception as e:
            errors.append(str(e))
    return {"success": True, "data": {"sent_count": sent, "errors": errors}, "error": None}


async def _async_get_clients(server_id: str) -> Dict:
    with _reg_lock:
        srv = _servers.get(server_id)
    if not srv:
        return {"success": False, "error": "Server not found", "data": None}
    return {"success": True, "data": {"clients": list(srv["clients"].keys())}, "error": None}


async def _async_send_to_client(server_id: str, client_id: str, message: str) -> Dict:
    with _reg_lock:
        srv = _servers.get(server_id)
    if not srv:
        return {"success": False, "error": "Server not found", "data": None}
    ws = srv["clients"].get(client_id)
    if not ws:
        return {"success": False, "error": "Client not connected", "data": None}
    try:
        await ws.send(message)
        return {"success": True, "data": {"sent": True}, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e), "data": None}


async def _async_disconnect_client(server_id: str, client_id: str) -> Dict:
    with _reg_lock:
        srv = _servers.get(server_id)
    if not srv:
        return {"success": False, "error": "Server not found", "data": None}
    ws = srv["clients"].pop(client_id, None)
    if ws:
        srv["client_map"].pop(ws, None)
        await ws.close()
    return {"success": True, "data": {"disconnected": bool(ws)}, "error": None}


async def _async_set_callback(conn_id: str, event: str, callback: Optional[Callable]) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    if event not in valid["state"]["callbacks"]:
        return {"success": False, "error": f"Invalid event: {event}", "data": None}
    valid["state"]["callbacks"][event] = callback
    return {"success": True, "data": {"event": event, "set": True}, "error": None}


async def _async_subscribe(conn_id: str, channel: str) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    valid["state"]["channels"].add(channel)
    return {"success": True, "data": {"channel": channel, "subscribed": True}, "error": None}


async def _async_unsubscribe(conn_id: str, channel: str) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    valid["state"]["channels"].discard(channel)
    return {"success": True, "data": {"channel": channel, "unsubscribed": True}, "error": None}


async def _async_get_connection_info(conn_id: str) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    conn = valid["state"]
    return {
        "success": True,
        "data": {
            "connection_id": conn_id, "url": conn["url"], "status": conn["status"],
            "channels": list(conn["channels"]), "has_listener": bool(conn["listener_task"])
        }, "error": None
    }


async def _async_batch_send(conn_id: str, messages: List[str]) -> Dict:
    valid = _validate_connection(conn_id)
    if not valid["valid"]:
        return {"success": False, "error": valid["error"], "data": None}
    ws = valid["state"]["ws"]
    sent = 0
    errors = []
    for msg in messages:
        try:
            await ws.send(msg)
            sent += 1
        except Exception as e:
            errors.append(str(e))
            break
    return {"success": True, "data": {"sent_count": sent, "errors": errors}, "error": None}


# ─────────────────────────────────────────────────────────────────────────────
# Public Synchronous API Toolkit
# ─────────────────────────────────────────────────────────────────────────────

def ws_connect(url: str, headers: Optional[Dict[str, str]] = None, ssl_context: Optional[ssl.SSLContext] = None) -> Dict[str, Any]:
    """Establish a WebSocket connection."""
    return _run_async(_async_connect(url, headers, ssl_context))

def ws_disconnect(connection_id: str) -> Dict[str, Any]:
    """Gracefully close a WebSocket connection."""
    return _run_async(_async_disconnect(connection_id))

def ws_send(connection_id: str, message: str) -> Dict[str, Any]:
    """Send a raw string message."""
    return _run_async(_async_send(connection_id, message))

def ws_send_json(connection_id: str, data: Any) -> Dict[str, Any]:
    """Serialize and send JSON data."""
    return _run_async(_async_send_json(connection_id, data))

def ws_receive(connection_id: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Receive a single message with timeout."""
    return _run_async(_async_receive(connection_id, timeout))

def ws_receive_json(connection_id: str, timeout: float = 10.0) -> Dict[str, Any]:
    """Receive and deserialize JSON."""
    return _run_async(_async_receive_json(connection_id, timeout))

def ws_listen(connection_id: str, callback: Callable[[str, str], None]) -> Dict[str, Any]:
    """Start background listener with message callback."""
    return _run_async(_async_listen(connection_id, callback))

def ws_stop_listening(connection_id: str) -> Dict[str, Any]:
    """Stop background listener task."""
    return _run_async(_async_stop_listening(connection_id))

def ws_ping(connection_id: str) -> Dict[str, Any]:
    """Send ping and measure latency."""
    return _run_async(_async_ping(connection_id))

def ws_get_state(connection_id: str) -> Dict[str, Any]:
    """Get connection liveness state."""
    return _run_async(_async_get_state(connection_id))

def ws_reconnect(connection_id: str, max_retries: int = 5) -> Dict[str, Any]:
    """Disconnect and retry connection establishment."""
    return _run_async(_async_reconnect(connection_id, max_retries))

def ws_create_server(host: str, port: int, handler: Callable) -> Dict[str, Any]:
    """Start a WebSocket server instance."""
    return _run_async(_async_create_server(host, port, handler))

def ws_stop_server(server_id: str) -> Dict[str, Any]:
    """Shutdown server and close all client sockets."""
    return _run_async(_async_stop_server(server_id))

def ws_broadcast(server_id: str, message: str) -> Dict[str, Any]:
    """Send message to all connected clients."""
    return _run_async(_async_broadcast(server_id, message))

def ws_get_clients(server_id: str) -> Dict[str, Any]:
    """List active client IDs."""
    return _run_async(_async_get_clients(server_id))

def ws_send_to_client(server_id: str, client_id: str, message: str) -> Dict[str, Any]:
    """Direct message to specific client."""
    return _run_async(_async_send_to_client(server_id, client_id, message))

def ws_disconnect_client(server_id: str, client_id: str) -> Dict[str, Any]:
    """Force disconnect a specific client."""
    return _run_async(_async_disconnect_client(server_id, client_id))

def ws_set_on_open(connection_id: str, callback: Optional[Callable[[str], None]]) -> Dict[str, Any]:
    """Register open event callback."""
    return _run_async(_async_set_callback(connection_id, "on_open", callback))

def ws_set_on_close(connection_id: str, callback: Optional[Callable[[str, Optional[int], str], None]]) -> Dict[str, Any]:
    """Register close event callback."""
    return _run_async(_async_set_callback(connection_id, "on_close", callback))

def ws_set_on_error(connection_id: str, callback: Optional[Callable[[str, Exception], None]]) -> Dict[str, Any]:
    """Register error event callback."""
    return _run_async(_async_set_callback(connection_id, "on_error", callback))

def ws_set_on_message(connection_id: str, callback: Optional[Callable[[str, str], None]]) -> Dict[str, Any]:
    """Register message event callback."""
    return _run_async(_async_set_callback(connection_id, "on_message", callback))

def ws_subscribe(connection_id: str, channel: str) -> Dict[str, Any]:
    """Filter incoming messages by channel."""
    return _run_async(_async_subscribe(connection_id, channel))

def ws_unsubscribe(connection_id: str, channel: str) -> Dict[str, Any]:
    """Remove channel filter."""
    return _run_async(_async_unsubscribe(connection_id, channel))

def ws_get_connection_info(connection_id: str) -> Dict[str, Any]:
    """Retrieve metadata and configuration."""
    return _run_async(_async_get_connection_info(connection_id))

def ws_batch_send(connection_id: str, messages: List[str]) -> Dict[str, Any]:
    """Send multiple messages sequentially."""
    return _run_async(_async_batch_send(connection_id, messages))