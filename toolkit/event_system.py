import threading
import queue
import time
import json
import logging
import uuid
import functools
import weakref
import inspect
import collections
import copy
from typing import Dict, Any, Callable, Optional, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("event_system")

_BUS_REGISTRY: Dict[str, "_EventBus"] = {}
_REGISTRY_LOCK = threading.RLock()


class _EventBus:
    """Internal thread-safe event bus implementation."""
    def __init__(self, name: str) -> None:
        self.name = name
        self.id = str(uuid.uuid4())
        self.lock = threading.RLock()
        self.subscribers: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.middleware: Dict[str, Dict[str, Any]] = {}
        self.history: collections.deque[Dict[str, Any]] = collections.deque(maxlen=10000)
        self.stats: Dict[str, int] = {"published": 0, "dispatched": 0, "errors": 0, "filtered": 0}
        self.async_queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self.wait_queues: Dict[str, List[queue.Queue[Dict[str, Any]]]] = {}
        self.filters: Dict[str, Callable[[Dict[str, Any]], bool]] = {}
        self.operators: Dict[str, Dict[str, Any]] = {}
        self._shutdown = threading.Event()
        self._debounce_timers: Dict[str, Optional[threading.Timer]] = {}
        self._batch_buffers: Dict[str, List[Dict[str, Any]]] = {}
        self._batch_timers: Dict[str, Optional[threading.Timer]] = {}
        self._throttle_times: Dict[str, float] = {}
        
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name=f"EventBusWorker-{name}")
        self._worker.start()
        logger.info("EventBus '%s' initialized (id: %s)", self.name, self.id)

    def _validate_handler(self, handler: Callable) -> None:
        sig = inspect.signature(handler)
        if len(sig.parameters) < 1:
            raise ValueError("Handler must accept at least one argument (event dict).")

    def _run_middleware(self, event: Dict[str, Any]) -> Dict[str, Any]:
        current_event = event
        for mw_id, mw_data in sorted(self.middleware.items(), key=lambda x: x[1].get("priority", 0)):
            try:
                result = mw_data["func"](current_event)
                if result is None or result.get("_halt", False):
                    return {"_halt": True}
                current_event = result if isinstance(result, dict) else current_event
            except Exception as e:
                logger.error("Middleware '%s' failed: %s", mw_id, str(e))
                current_event.setdefault("_errors", []).append({"middleware_id": mw_id, "error": str(e)})
        return current_event

    def _apply_filters(self, event: Dict[str, Any]) -> bool:
        event_type = event.get("event_type")
        if event_type in self.filters:
            if not self.filters[event_type](event):
                self.stats["filtered"] += 1
                return False
        return True

    def _handle_operators(self, event: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        event_type = event.get("event_type")
        if event_type not in self.operators:
            return [event]
        
        ops = self.operators[event_type]
        
        # Throttle
        if "throttle" in ops:
            now = time.time()
            last = self._throttle_times.get(event_type, 0.0)
            if now - last < ops["throttle"]["interval"]:
                return None
            self._throttle_times[event_type] = now

        # Debounce
        if "debounce" in ops:
            delay = ops["debounce"]["delay"]
            if self._debounce_timers.get(event_type):
                self._debounce_timers[event_type].cancel()
            
            def _fire_debounce():
                evt = self._debounce_timers.get(f"_cache_{event_type}", event)
                self._route_to_subscribers(evt)
                self._debounce_timers.pop(event_type, None)
                self._debounce_timers.pop(f"_cache_{event_type}", None)

            timer = threading.Timer(delay, _fire_debounce)
            self._debounce_timers[event_type] = timer
            self._debounce_timers[f"_cache_{event_type}"] = event
            timer.start()
            return None

        # Batch
        if "batch" in ops:
            cfg = ops["batch"]
            self._batch_buffers.setdefault(event_type, [])
            self._batch_buffers[event_type].append(event)
            
            if self._batch_timers.get(event_type):
                self._batch_timers[event_type].cancel()

            def _flush_batch():
                with self.lock:
                    buf = self._batch_buffers.pop(event_type, [])
                    self._batch_timers.pop(event_type, None)
                if buf:
                    batch_event = create_event(f"{event_type}_batch", buf, source=buf[-1].get("source"))["result"]
                    self._route_to_subscribers(batch_event)

            timer = threading.Timer(cfg["timeout"], _flush_batch)
            self._batch_timers[event_type] = timer
            timer.start()

            self.stats["published"] += 1
            if len(self._batch_buffers[event_type]) >= cfg["size"]:
                _flush_batch()
            return None

        return [event]

    def _route_to_subscribers(self, event: Dict[str, Any]) -> None:
        event_type = event.get("event_type")
        with self.lock:
            subs = self.subscribers.get(event_type, {})
            history_snapshot = copy.deepcopy(event)
            self.history.append(history_snapshot)
            
            for wq in self.wait_queues.get(event_type, []):
                wq.put_nowait(event)
                self.wait_queues[event_type].remove(wq)

        dispatched = 0
        errors = 0
        for _, sub_data in sorted(subs.items(), key=lambda x: x[1].get("priority", 0)):
            try:
                sub_data["handler"](event)
                dispatched += 1
                if sub_data.get("once"):
                    sub_data["callback"](event_type, sub_data["handler_id"])
            except Exception as e:
                logger.error("Handler '%s' failed for event_type '%s': %s", sub_data["handler_id"], event_type, str(e))
                errors += 1
        
        self.stats["dispatched"] += dispatched
        self.stats["errors"] += errors

    def _process_incoming_event(self, event: Dict[str, Any]) -> None:
        try:
            processed = self._run_middleware(event)
            if processed.get("_halt"):
                return
            if not self._apply_filters(processed):
                return
            result = self._handle_operators(processed)
            if result:
                for evt in result:
                    self._route_to_subscribers(evt)
        except Exception as e:
            logger.error("Event processing failed: %s", str(e))
            self.stats["errors"] += 1

    def _worker_loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                event = self.async_queue.get(timeout=0.5)
                self.stats["published"] += 1
                self._process_incoming_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error("Async worker error: %s", str(e))
                self.stats["errors"] += 1

    def stop(self) -> None:
        self._shutdown.set()
        if self._worker.is_alive():
            self._worker.join(timeout=2.0)
        for timer in list(self._debounce_timers.values()) + list(self._batch_timers.values()):
            if timer and timer.is_alive():
                timer.cancel()
        logger.info("EventBus '%s' stopped.", self.name)


def create_event_bus(name: str) -> Dict[str, Any]:
    try:
        if not name or not isinstance(name, str):
            raise ValueError("Bus name must be a non-empty string.")
        with _REGISTRY_LOCK:
            if name in _BUS_REGISTRY:
                return {"success": False, "error": "Bus already exists", "code": "BUS_EXISTS"}
            bus = _EventBus(name)
            _BUS_REGISTRY[name] = bus
        return {"success": True, "bus_name": name, "bus_id": bus.id}
    except Exception as e:
        logger.error("create_event_bus failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "CREATE_BUS_FAILED"}


def _resolve_bus(bus: Any) -> Tuple[bool, Optional[_EventBus], str]:
    if isinstance(bus, str):
        name = bus
    elif isinstance(bus, dict) and "name" in bus:
        name = bus["name"]
    else:
        raise TypeError("Invalid bus identifier. Expected str or bus dict.")
    
    with _REGISTRY_LOCK:
        b = _BUS_REGISTRY.get(name)
    if b is None:
        raise ValueError(f"Bus '{name}' not found or destroyed.")
    return True, b, name


def subscribe(bus: Any, event_type: str, handler: Callable[..., None], priority: int = 0) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type must be a non-empty string.")
        if not callable(handler):
            raise TypeError("handler must be callable.")
        b._validate_handler(handler)
        
        handler_id = str(uuid.uuid4())
        with b.lock:
            b.subscribers.setdefault(event_type, {})
            b.subscribers[event_type][handler_id] = {
                "handler": handler,
                "priority": priority,
                "once": False,
                "handler_id": handler_id
            }
        return {"success": True, "handler_id": handler_id}
    except Exception as e:
        logger.error("subscribe failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "SUBSCRIBE_FAILED"}


def unsubscribe(bus: Any, event_type: str, handler_id: str) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if not isinstance(handler_id, str):
            raise TypeError("handler_id must be a string.")
        with b.lock:
            subs = b.subscribers.get(event_type, {})
            if handler_id in subs:
                del subs[handler_id]
                if not subs:
                    del b.subscribers[event_type]
                return {"success": True, "unsubscribed": True}
        return {"success": True, "unsubscribed": False}
    except Exception as e:
        logger.error("unsubscribe failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "UNSUBSCRIBE_FAILED"}


def publish(bus: Any, event_type: str, data: Any) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        evt = create_event(event_type, data, source=f"sync_publish_{b.name}")
        if not evt["success"]:
            raise RuntimeError(evt.get("error", "Event creation failed"))
        
        b.stats["published"] += 1
        b._process_incoming_event(evt["result"])
        return {"success": True, "published": True}
    except Exception as e:
        logger.error("publish failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "PUBLISH_FAILED"}


def publish_async(bus: Any, event_type: str, data: Any) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        evt = create_event(event_type, data, source=f"async_publish_{b.name}")
        if not evt["success"]:
            raise RuntimeError(evt.get("error"))
        b.async_queue.put_nowait(evt["result"])
        return {"success": True, "queued": True}
    except queue.Full:
        return {"success": False, "error": "Async queue full", "code": "QUEUE_FULL"}
    except Exception as e:
        logger.error("publish_async failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "PUBLISH_ASYNC_FAILED"}


def once(bus: Any, event_type: str, handler: Callable[..., None]) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        
        @functools.wraps(handler)
        def wrapped_handler(event: Dict[str, Any]) -> None:
            b._validate_handler(handler)
            try:
                handler(event)
            finally:
                unsubscribe(bus, event_type, self._handler_id if hasattr(self, '_handler_id') else "")

        # Inject handler_id dynamically after subscription
        result = subscribe(bus, event_type, wrapped_handler)
        if result["success"]:
            hid = result["handler_id"]
            with b.lock:
                b.subscribers.setdefault(event_type, {})[hid]["once"] = True
                b.subscribers[event_type][hid]["callback"] = lambda et, hid: unsubscribe(bus, et, hid)
        return result
    except Exception as e:
        logger.error("once failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "ONCE_FAILED"}


def wait_for_event(bus: Any, event_type: str, timeout: float = 5.0) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        q: queue.Queue[Dict[str, Any]] = queue.Queue()
        with b.lock:
            b.wait_queues.setdefault(event_type, []).append(q)
        
        try:
            event = q.get(timeout=timeout)
            return {"success": True, "event": event}
        except queue.Empty:
            with b.lock:
                if event_type in b.wait_queues and q in b.wait_queues[event_type]:
                    b.wait_queues[event_type].remove(q)
            return {"success": False, "error": "Timeout waiting for event", "code": "WAIT_TIMEOUT"}
    except Exception as e:
        logger.error("wait_for_event failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "WAIT_FAILED"}


def get_subscribers(bus: Any, event_type: Optional[str] = None) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        with b.lock:
            if event_type:
                targets = {event_type: b.subscribers.get(event_type, {})}
            else:
                targets = copy.deepcopy(b.subscribers)
        result = {et: list(sd.keys()) for et, sd in targets.items()}
        return {"success": True, "subscribers": result}
    except Exception as e:
        logger.error("get_subscribers failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "GET_SUBS_FAILED"}


def clear_subscribers(bus: Any, event_type: Optional[str] = None) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        with b.lock:
            if event_type:
                if event_type in b.subscribers:
                    b.subscribers.pop(event_type)
            else:
                b.subscribers.clear()
        return {"success": True}
    except Exception as e:
        logger.error("clear_subscribers failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "CLEAR_SUBS_FAILED"}


def create_event(event_type: str, data: Any, source: str = "unknown") -> Dict[str, Any]:
    try:
        if not event_type or not isinstance(event_type, str):
            raise ValueError("event_type must be a non-empty string.")
        return {
            "success": True,
            "result": {
                "id": str(uuid.uuid4()),
                "event_type": event_type,
                "data": data,
                "source": source,
                "timestamp": time.time(),
                "_metadata": {}
            }
        }
    except Exception as e:
        logger.error("create_event failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "CREATE_EVENT_FAILED"}


def filter_events(bus: Any, event_type: str, predicate: Callable[[Dict[str, Any]], bool]) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if not callable(predicate):
            raise TypeError("predicate must be callable.")
        with b.lock:
            b.filters[event_type] = predicate
        return {"success": True, "filter_id": f"filter_{event_type}_{str(uuid.uuid4())[:8]}"}
    except Exception as e:
        logger.error("filter_events failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "FILTER_FAILED"}


def throttle_events(bus: Any, event_type: str, interval: float) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if interval <= 0:
            raise ValueError("interval must be > 0.")
        with b.lock:
            b.operators.setdefault(event_type, {})["throttle"] = {"interval": interval}
        return {"success": True, "operator": "throttle"}
    except Exception as e:
        logger.error("throttle_events failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "THROTTLE_FAILED"}


def debounce_events(bus: Any, event_type: str, delay: float) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if delay <= 0:
            raise ValueError("delay must be > 0.")
        with b.lock:
            b.operators.setdefault(event_type, {})["debounce"] = {"delay": delay}
        return {"success": True, "operator": "debounce"}
    except Exception as e:
        logger.error("debounce_events failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "DEBOUNCE_FAILED"}


def batch_events(bus: Any, event_type: str, batch_size: int, timeout: float) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if batch_size <= 0 or timeout <= 0:
            raise ValueError("batch_size and timeout must be > 0.")
        with b.lock:
            b.operators.setdefault(event_type, {})["batch"] = {"size": batch_size, "timeout": timeout}
        return {"success": True, "operator": "batch"}
    except Exception as e:
        logger.error("batch_events failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "BATCH_FAILED"}


def replay_events(bus: Any, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if not isinstance(events, list):
            raise TypeError("events must be a list.")
        count = 0
        for evt in events:
            if isinstance(evt, dict) and "event_type" in evt:
                b.stats["published"] += 1
                b._process_incoming_event(evt)
                count += 1
        return {"success": True, "replayed": count}
    except Exception as e:
        logger.error("replay_events failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "REPLAY_FAILED"}


def get_event_history(bus: Any, event_type: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        with b.lock:
            history = list(b.history)
        if event_type:
            filtered = [e for e in history if e.get("event_type") == event_type]
        else:
            filtered = history
        
        result = filtered[-limit:] if limit > 0 else filtered
        return {"success": True, "events": result, "count": len(result)}
    except Exception as e:
        logger.error("get_event_history failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "HISTORY_FAILED"}


def save_event_log(bus: Any, filepath: str) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if not filepath.endswith(".json"):
            raise ValueError("filepath must end with .json")
        with b.lock:
            data = list(b.history)
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return {"success": True, "filepath": filepath, "records_saved": len(data)}
    except Exception as e:
        logger.error("save_event_log failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "SAVE_LOG_FAILED"}


def load_event_log(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, "r") as f:
            events = json.load(f)
        if not isinstance(events, list):
            raise ValueError("Log file does not contain an event list.")
        return {"success": True, "events": events, "count": len(events)}
    except Exception as e:
        logger.error("load_event_log failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "LOAD_LOG_FAILED"}


def create_event_pipeline(stages: List[Callable[[Dict], Dict]]) -> Dict[str, Any]:
    try:
        for i, stage in enumerate(stages):
            if not callable(stage):
                raise TypeError(f"Stage {i} is not callable.")
        return {"success": True, "pipeline_id": str(uuid.uuid4()), "stages_count": len(stages), "stages": stages}
    except Exception as e:
        logger.error("create_event_pipeline failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "PIPELINE_CREATE_FAILED"}


def execute_pipeline(pipeline: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not isinstance(pipeline, dict) or "stages" not in pipeline:
            raise ValueError("Invalid pipeline object.")
        current = copy.deepcopy(event)
        for i, stage in enumerate(pipeline["stages"]):
            result = stage(current)
            if result is None:
                break
            current = result
        
        return {"success": True, "result_event": current}
    except Exception as e:
        logger.error("execute_pipeline failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "EXEC_PIPELINE_FAILED"}


def create_middleware(func: Callable[[Dict], Dict], priority: int = 0) -> Dict[str, Any]:
    try:
        if not callable(func):
            raise TypeError("func must be callable.")
        sig = inspect.signature(func)
        if len(sig.parameters) < 1:
            raise ValueError("Middleware must accept at least one argument (event dict).")
        
        @functools.wraps(func)
        def wrapper(evt: Dict) -> Dict:
            return func(evt)
            
        mw_id = str(uuid.uuid4())
        return {"success": True, "middleware_id": mw_id, "func": wrapper, "priority": priority}
    except Exception as e:
        logger.error("create_middleware failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "MIDDLEWARE_CREATE_FAILED"}


def add_middleware(bus: Any, middleware: Dict[str, Any]) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        if not isinstance(middleware, dict) or "func" not in middleware or "middleware_id" not in middleware:
            raise ValueError("Invalid middleware configuration.")
        with b.lock:
            b.middleware[middleware["middleware_id"]] = {
                "func": middleware["func"],
                "priority": middleware.get("priority", 0)
            }
        return {"success": True, "added": middleware["middleware_id"]}
    except Exception as e:
        logger.error("add_middleware failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "ADD_MIDDLEWARE_FAILED"}


def remove_middleware(bus: Any, middleware_id: str) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        with b.lock:
            if middleware_id in b.middleware:
                del b.middleware[middleware_id]
                return {"success": True, "removed": True}
        return {"success": True, "removed": False}
    except Exception as e:
        logger.error("remove_middleware failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "REMOVE_MIDDLEWARE_FAILED"}


def get_event_stats(bus: Any) -> Dict[str, Any]:
    try:
        _, b, _ = _resolve_bus(bus)
        with b.lock:
            stats = copy.deepcopy(b.stats)
            stats["active_subscribers"] = sum(len(s) for s in b.subscribers.values())
            stats["history_size"] = len(b.history)
            stats["middleware_count"] = len(b.middleware)
            stats["async_queue_depth"] = b.async_queue.qsize()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error("get_event_stats failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "STATS_FAILED"}


def destroy_event_bus(bus_name: str) -> Dict[str, Any]:
    try:
        if not isinstance(bus_name, str):
            raise TypeError("bus_name must be a string.")
        
        with _REGISTRY_LOCK:
            b = _BUS_REGISTRY.pop(bus_name, None)
            if not b:
                return {"success": False, "error": "Bus not found", "code": "BUS_NOT_FOUND"}
            
        b.stop()
        with b.lock:
            b.subscribers.clear()
            b.middleware.clear()
            b.history.clear()
            b.async_queue = queue.Queue()  # Drain reference
            
        b_weak = weakref.ref(b)
        del b
        return {"success": True, "destroyed": bus_name, "gc_ref_cleared": b_weak() is None}
    except Exception as e:
        logger.error("destroy_event_bus failed: %s", str(e))
        return {"success": False, "error": str(e), "code": "DESTROY_FAILED"}