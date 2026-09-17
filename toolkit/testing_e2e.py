#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""testing_e2e.py – A tiny but feature‑rich end‑to‑end test helper.

The module bundles common utilities that are useful when writing UI / screen‑agent
tests:

* Creation & execution of unittest suites
* A rich set of assertion helpers that return structured results
* Performance, stress, retry, timeout and benchmarking helpers
* File / image comparison utilities
* Reporting (JSON & HTML) & logging
* Test‑environment management, mocking, output capture
* Parallel and data‑driven execution
"""

from __future__ import annotations

import concurrent.futures
import datetime
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unittest
from dataclasses import dataclass, asdict
from io import StringIO
from typing import Any, Callable, Dict, Iterable, List, Tuple, Type, Union

# Optional Pillow import – required only for screenshot comparison.
# If Pillow is not available we fall back to a simple file‑size check.
try:
    from PIL import Image, ImageChops
except Exception:  # pragma: no cover
    Image = None
    ImageChops = None

# --------------------------------------------------------------------------- #
# Helper dataclasses
# --------------------------------------------------------------------------- #

@dataclass
class TestResult:
    """Standardised result returned by every helper in this module."""
    success: bool
    name: str = ""
    message: str = ""
    data: Dict[str, Any] = None
    elapsed: float = 0.0
    traceback: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the dataclass to a plain dict (JSON‑serialisable)."""
        d = asdict(self)
        # Remove empty traceback entries for brevity.
        if not d["traceback"]:
            del d["traceback"]
        return d


# --------------------------------------------------------------------------- #
# Test suite helpers
# --------------------------------------------------------------------------- #

def create_test_suite(name: str, tests: List[Callable[[], None]]) -> Dict[str, Any]:
    """
    Build a :class:`unittest.TestSuite` from a list of plain callables.

    The generated suite is stored under the ``suite`` key of the returned
    dict.  The suite can be executed with :func:`run_test_suite`.
    """
    suite = unittest.TestSuite()

    class _DynamicTestCase(unittest.TestCase):
        """Wrap a plain function as a unittest.TestCase."""

        def __init__(self, test_func: Callable[[], None], method_name: str = "runTest"):
            super().__init__(method_name)
            self._test_func = test_func

        def runTest(self) -> None:  # noqa: N802 (unittest convention)
            self._test_func()

    for idx, fn in enumerate(tests):
        test_name = f"{name}_test_{idx + 1}"
        suite.addTest(_DynamicTestCase(fn, method_name="runTest"))
    return TestResult(True, name=name, message="Suite created", data={"suite": suite}).to_dict()


def run_test_suite(suite_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a suite produced by :func:`create_test_suite`.

    Returns a dict with a summary of passed / failed tests and the raw
    ``unittest.TestResult`` object in the ``data`` field.
    """
    try:
        suite: unittest.TestSuite = suite_dict["suite"]
    except (KeyError, TypeError):
        return TestResult(
            False, name="run_test_suite",
            message="Invalid suite dict – missing 'suite' key",
        ).to_dict()

    runner = unittest.TextTestRunner(stream=StringIO(), verbosity=2)
    start = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - start

    summary = {
        "run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "expectedFailures": len(result.expectedFailures),
        "unexpectedSuccesses": len(result.unexpectedSuccesses),
    }

    success = result.wasSuccessful()
    message = "All tests passed" if success else "Some tests failed"
    return TestResult(
        success,
        name="run_test_suite",
        message=message,
        data={"unittest_result": summary},
        elapsed=elapsed,
    ).to_dict()


def run_single_test(test_func: Callable[[], None], name: str = "single_test") -> Dict[str, Any]:
    """Execute a single test function wrapped in a unittest case."""
    suite = unittest.TestSuite()
    suite.addTest(unittest.FunctionTestCase(test_func, description=name))
    return run_test_suite({"suite": suite})


# --------------------------------------------------------------------------- #
# Assertion helpers – all return a ``TestResult`` dict
# --------------------------------------------------------------------------- #

def _assert(condition: bool, name: str, message: str, **data: Any) -> TestResult:
    return TestResult(condition, name=name, message=message, data=data)


def assert_equals(actual: Any, expected: Any, message: str = "") -> Dict[str, Any]:
    """Assert ``actual == expected``."""
    try:
        assert actual == expected, message or f"{actual!r} != {expected!r}"
        return _assert(True, "assert_equals", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_equals", str(exc), actual=actual, expected=expected).to_dict()


def assert_not_equals(actual: Any, expected: Any, message: str = "") -> Dict[str, Any]:
    """Assert ``actual != expected``."""
    try:
        assert actual != expected, message or f"{actual!r} == {expected!r}"
        return _assert(True, "assert_not_equals", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_not_equals", str(exc), actual=actual, expected=expected).to_dict()


def assert_true(value: Any, message: str = "") -> Dict[str, Any]:
    try:
        assert bool(value), message or f"Expected True, got {value!r}"
        return _assert(True, "assert_true", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_true", str(exc), value=value).to_dict()


def assert_false(value: Any, message: str = "") -> Dict[str, Any]:
    try:
        assert not bool(value), message or f"Expected False, got {value!r}"
        return _assert(True, "assert_false", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_false", str(exc), value=value).to_dict()


def assert_contains(container: Any, item: Any, message: str = "") -> Dict[str, Any]:
    try:
        assert item in container, message or f"{item!r} not found in container"
        return _assert(True, "assert_contains", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_contains", str(exc), container=container, item=item).to_dict()


def assert_greater(a: Any, b: Any, message: str = "") -> Dict[str, Any]:
    try:
        assert a > b, message or f"{a!r} is not greater than {b!r}"
        return _assert(True, "assert_greater", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_greater", str(exc), a=a, b=b).to_dict()


def assert_less(a: Any, b: Any, message: str = "") -> Dict[str, Any]:
    try:
        assert a < b, message or f"{a!r} is not less than {b!r}"
        return _assert(True, "assert_less", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_less", str(exc), a=a, b=b).to_dict()


def assert_in_range(value: Any, min_val: Any, max_val: Any, message: str = "") -> Dict[str, Any]:
    try:
        assert min_val <= value <= max_val, message or f"{value!r} not in [{min_val!r}, {max_val!r}]"
        return _assert(True, "assert_in_range", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_in_range", str(exc), value=value,
                      min=min_val, max=max_val).to_dict()


def assert_type(value: Any, expected_type: Type, message: str = "") -> Dict[str, Any]:
    try:
        assert isinstance(value, expected_type), \
            message or f"Expected type {expected_type}, got {type(value)}"
        return _assert(True, "assert_type", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_type", str(exc), value=value,
                      expected_type=expected_type).to_dict()


def assert_raises(func: Callable, exception_type: Type[BaseException]) -> Dict[str, Any]:
    """Assert that *func* raises *exception_type*."""
    try:
        func()
        return _assert(False, "assert_raises",
                       f"Did not raise {exception_type.__name__}").to_dict()
    except exception_type:
        return _assert(True, "assert_raises", "").to_dict()
    except Exception as exc:  # pragma: no cover
        tb = traceback.format_exc()
        return _assert(False, "assert_raises",
                       f"Raised {type(exc).__name__} instead of {exception_type.__name__}",
                       traceback=tb).to_dict()


def assert_dict_has_key(d: Dict[Any, Any], key: Any, message: str = "") -> Dict[str, Any]:
    try:
        assert key in d, message or f"Key {key!r} not present in dict"
        return _assert(True, "assert_dict_has_key", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_dict_has_key", str(exc), dict=d, key=key).to_dict()


def assert_list_length(lst: List[Any], length: int, message: str = "") -> Dict[str, Any]:
    try:
        assert len(lst) == length, \
            message or f"List length {len(lst)} != expected {length}"
        return _assert(True, "assert_list_length", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_list_length", str(exc), actual=len(lst), expected=length).to_dict()


def assert_string_matches(text: str, pattern: str, message: str = "") -> Dict[str, Any]:
    try:
        assert re.search(pattern, text), \
            message or f"Pattern {pattern!r} not found in text"
        return _assert(True, "assert_string_matches", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_string_matches", str(exc), text=text, pattern=pattern).to_dict()


def assert_file_exists(path: Union[str, pathlib.Path], message: str = "") -> Dict[str, Any]:
    p = pathlib.Path(path)
    try:
        assert p.is_file(), message or f"File does not exist: {p}"
        return _assert(True, "assert_file_exists", "").to_dict()
    except AssertionError as exc:
        return _assert(False, "assert_file_exists", str(exc), path=str(p)).to_dict()


def assert_files_equal(file1: Union[str, pathlib.Path],
                      file2: Union[str, pathlib.Path],
                      message: str = "") -> Dict[str, Any]:
    """Binary comparison of two files (fallback to diff for text)."""
    p1, p2 = pathlib.Path(file1), pathlib.Path(file2)
    try:
        assert p1.is_file() and p2.is_file(), "Both paths must be files"
        if p1.stat().st_size != p2.stat().st_size:
            raise AssertionError("File sizes differ")

        # Try binary compare; if both are text we also give a diff preview.
        b1 = p1.read_bytes()
        b2 = p2.read_bytes()
        assert b1 == b2, "File contents differ"

        return _assert(True, "assert_files_equal", "").to_dict()
    except AssertionError as exc:
        # Generate a short diff for text files if possible
        try:
            t1 = p1.read_text().splitlines()
            t2 = p2.read_text().splitlines()
            diff = "\n".join(difflib.unified_diff(t1, t2, fromfile=str(p1), tofile=str(p2), n=2))
        except Exception:  # pragma: no cover
            diff = ""
        return _assert(False, "assert_files_equal", str(exc),
                      file1=str(p1), file2=str(p2), diff=diff).to_dict()


# --------------------------------------------------------------------------- #
# Image comparison (screenshot) – requires Pillow
# --------------------------------------------------------------------------- #

def screenshot_compare(image1: Union[str, pathlib.Path],
                      image2: Union[str, pathlib.Path],
                      threshold: float = 0.0) -> Dict[str, Any]:
    """
    Compare two screenshots.

    *threshold* is the maximum acceptable RMS difference (0 = identical).
    Returns ``success=False`` when Pillow is unavailable or the images differ.
    """
    if Image is None:
        return _assert(False, "screenshot_compare",
                       "Pillow is not installed; cannot compare images").to_dict()

    p1, p2 = pathlib.Path(image1), pathlib.Path(image2)
    try:
        img1 = Image.open(p1).convert("RGB")
        img2 = Image.open(p2).convert("RGB")
        if img1.size != img2.size:
            raise AssertionError(f"Image sizes differ: {img1.size} vs {img2.size}")

        diff = ImageChops.difference(img1, img2)
        # RMS (root‑mean‑square) error
        h = diff.histogram()
        sq = (value * ((idx % 256) ** 2) for idx, value in enumerate(h))
        sum_of_squares = sum(sq)
        rms = (sum_of_squares / (float(img1.size[0]) * img1.size[1])) ** 0.5

        if rms <= threshold:
            return _assert(True, "screenshot_compare", "").to_dict()
        else:
            return _assert(
                False, "screenshot_compare",
                f"RMS {rms:.3f} exceeds threshold {threshold}",
                rms=rms, threshold=threshold
            ).to_dict()
    except Exception as exc:  # pragma: no cover
        tb = traceback.format_exc()
        return _assert(False, "screenshot_compare", str(exc), traceback=tb).to_dict()


# --------------------------------------------------------------------------- #
# Performance / stress / retry / timeout helpers
# --------------------------------------------------------------------------- #

def performance_test(func: Callable, max_duration: float) -> Dict[str, Any]:
    """
    Run *func* once and ensure it finishes within *max_duration* seconds.
    """
    start = time.perf_counter()
    try:
        func()
    except Exception as exc:  # pragma: no cover
        tb = traceback.format_exc()
        return _assert(False, "performance_test",
                       f"Function raised {type(exc).__name__}", traceback=tb).to_dict()
    elapsed = time.perf_counter() - start
    if elapsed <= max_duration:
        return _assert(True, "performance_test", "", elapsed=elapsed).to_dict()
    return _assert(False, "performance_test",
                   f"Duration {elapsed:.4f}s > max {max_duration}s",
                   elapsed=elapsed).to_dict()


def stress_test(func: Callable, iterations: int = 10, delay: float = 0.0) -> Dict[str, Any]:
    """
    Execute *func* repeatedly.  Returns a summary dict with any failures.
    """
    failures: List[Dict[str, Any]] = []
    start = time.perf_counter()
    for i in range(iterations):
        try:
            func()
        except Exception as exc:  # pragma: no cover
            failures.append({
                "iteration": i,
                "exception": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            })
        if delay:
            time.sleep(delay)
    elapsed = time.perf_counter() - start
    success = not failures
    return TestResult(
        success,
        name="stress_test",
        message="All iterations passed" if success else f"{len(failures)} failures",
        data={"iterations": iterations, "failures": failures, "elapsed": elapsed},
        elapsed=elapsed,
    ).to_dict()


def retry_test(func: Callable, max_retries: int = 3, delay: float = 0.0) -> Dict[str, Any]:
    """
    Call *func* until it succeeds or *max_retries* is exhausted.
    """
    attempts = 0
    last_exc: Exception | None = None
    while attempts <= max_retries:
        try:
            func()
            return _assert(True, "retry_test", "", attempts=attempts).to_dict()
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            attempts += 1
            if delay:
                time.sleep(delay)
    tb = traceback.format_exception_only(type(last_exc), last_exc) if last_exc else []
    return _assert(
        False, "retry_test",
        f"Failed after {attempts} attempts: {last_exc}",
        attempts=attempts,
        traceback="".join(tb)
    ).to_dict()


def timeout_test(func: Callable, timeout_seconds: float) -> Dict[str, Any]:
    """
    Run *func* in a separate thread and abort after *timeout_seconds*.

    The thread cannot be force‑killed; we simply stop waiting and report a
    timeout.
    """
    result: List[Exception | None] = [None]

    def _target() -> None:
        try:
            func()
        except Exception as exc:  # pragma: no cover
            result[0] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        return _assert(False, "timeout_test",
                       f"Function timed out after {timeout_seconds}s").to_dict()
    if result[0] is None:
        return _assert(True, "timeout_test", "").to_dict()
    # Function raised an exception before timeout.
    tb = traceback.format_exc()
    return _assert(False, "timeout_test",
                   f"Function raised {type(result[0]).__name__}",
                   traceback=tb).to_dict()


# --------------------------------------------------------------------------- #
# Reporting helpers
# --------------------------------------------------------------------------- #

def create_test_report(results: List[Dict[str, Any]], output_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Write a JSON report and an HTML report (via the two helpers below)."""
    out_path = pathlib.Path(output_path)
    try:
        json_path = out_path.with_suffix(".json")
        html_path = out_path.with_suffix(".html")

        create_json_report(results, json_path)
        create_html_report(results, html_path)

        return _assert(True, "create_test_report", "", json=json_path, html=html_path).to_dict()
    except Exception as exc:  # pragma: no cover
        return _assert(False, "create_test_report", str(exc)).to_dict()


def create_json_report(results: List[Dict[str, Any]], output_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Serialize *results* as pretty‑printed JSON."""
    path = pathlib.Path(output_path)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        return _assert(True, "create_json_report", "", path=str(path)).to_dict()
    except Exception as exc:  # pragma: no cover
        return _assert(False, "create_json_report", str(exc)).to_dict()


def create_html_report(results: List[Dict[str, Any]], output_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Create a very small HTML summary."""
    path = pathlib.Path(output_path)
    try:
        rows = ""
        for r in results:
            status = "✅" if r.get("success") else "❌"
            name = r.get("name", "Unnamed")
            msg = r.get("message", "")
            rows += f"<tr><td>{status}</td><td>{name}</td><td>{msg}</td></tr>\n"

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Test Report</title>
<style>
table {{border-collapse: collapse; width: 100%;}}
th, td {{border: 1px solid #ddd; padding: 8px;}}
th {{background-color: #f2f2f2;}}
</style></head>
<body><h1>Test Report – {datetime.datetime.utcnow().isoformat()} UTC</h1>
<table><thead><tr><th>Status</th><th>Name</th><th>Message</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>
"""
        with path.open("w", encoding="utf-8") as f:
            f.write(html)
        return _assert(True, "create_html_report", "", path=str(path)).to_dict()
    except Exception as exc:  # pragma: no cover
        return _assert(False, "create_html_report", str(exc)).to_dict()


def log_test_result(result: Dict[str, Any], log_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Append a single ``result`` dict to a line‑delimited JSON log file."""
    log_file = pathlib.Path(log_path)
    try:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
        return _assert(True, "log_test_result", "", log_path=str(log_file)).to_dict()
    except Exception as exc:  # pragma: no cover
        return _assert(False, "log_test_result", str(exc)).to_dict()


# --------------------------------------------------------------------------- #
# Test environment management
# --------------------------------------------------------------------------- #

def setup_test_env(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a temporary directory and dump the supplied *config* as ``config.json``.
    Returns the path of the directory and the config file.
    """
    try:
        tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="e2e_env_"))
        cfg_path = tmp_dir / "config.json"
        with cfg_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return _assert(True, "setup_test_env", "",
                      env_path=str(tmp_dir), config_path=str(cfg_path)).to_dict()
    except Exception as exc:  # pragma: no cover
        return _assert(False, "setup_test_env", str(exc)).to_dict()


def teardown_test_env(env_path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Recursively delete the temporary environment created by :func:`setup_test_env`."""
    p = pathlib.Path(env_path)
    try:
        if p.is_dir():
            for child in p.rglob("*"):
                if child.is_file():
                    child.unlink()
                else:
                    child.rmdir()
            p.rmdir()
        return _assert(True, "teardown_test_env", "", removed=str(p)).to_dict()
    except Exception as exc:  # pragma: no cover
        return _assert(False, "teardown_test_env", str(exc)).to_dict()


# --------------------------------------------------------------------------- #
# Mocking helpers (built on unittest.mock)
# --------------------------------------------------------------------------- #

from unittest.mock import patch, Mock

_mock_registry: Dict[int, patch] = {}
_next_mock_id = 1


def mock_function(module: str, func_name: str, return_value: Any) -> Dict[str, Any]:
    """
    Replace ``module.func_name`` with a mock that returns *return_value*.
    Returns a dict containing a ``mock_id`` that can be used with :func:`restore_mock`.
    """
    global _next_mock_id
    try:
        target = f"{module}.{func_name}"
        patcher = patch(target, return_value=return_value)
        mock_obj = patcher.start()
        mock_id = _next_mock_id
        _mock_registry[mock_id] = patcher
        _next_mock_id += 1
        return _assert(True, "mock_function", "", mock_id=mock_id,
                       mocked_target=target, mock=repr(mock_obj)).to_dict()
    except Exception as exc:  # pragma: no cover
        return _assert(False, "mock_function", str(exc)).to_dict()


def restore_mock(mock_id: int) -> Dict[str, Any]:
    """Stop the patch associated with *mock_id*."""
    try:
        patcher = _mock_registry.pop(mock_id)
        patcher.stop()
        return _assert(True, "restore_mock", "", mock_id=mock_id).to_dict()
    except KeyError:
        return _assert(False, "restore_mock",
                       f"No mock registered with id {mock_id}").to_dict()
    except Exception as exc:  # pragma: no cover
        return _assert(False, "restore_mock", str(exc)).to_dict()


# --------------------------------------------------------------------------- #
# Utility wrappers
# --------------------------------------------------------------------------- #

def capture_output(func: Callable[..., Any]) -> Dict[str, Any]:
    """
    Execute *func* and capture ``stdout`` / ``stderr``.  Returns the captured
    strings together with any exception information.
    """
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = StringIO()
    try:
        result = func()
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        return _assert(True, "capture_output", "", stdout=out, stderr=err,
                      return_value=result).to_dict()
    except Exception as exc:  # pragma: no cover
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        tb = traceback.format_exc()
        return _assert(False, "capture_output", str(exc),
                      stdout=out, stderr=err, traceback=tb).to_dict()
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def benchmark(func: Callable[[], Any], iterations: int = 5) -> Dict[str, Any]:
    """Run *func* *iterations* times and report min/avg/max runtimes."""
    if iterations <= 0:
        return _assert(False, "benchmark", "iterations must be > 0").to_dict()
    timings: List[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            func()
        except Exception as exc:  # pragma: no cover
            tb = traceback.format_exc()
            return _assert(False, "benchmark", f"Function raised {type(exc).__name__}",
                          traceback=tb).to_dict()
        timings.append(time.perf_counter() - start)
    summary = {
        "iterations": iterations,
        "min": min(timings),
        "max": max(timings),
        "avg": sum(timings) / len(timings),
    }
    return _assert(True, "benchmark", "", **summary).to_dict()


def data_driven_test(test_func: Callable[[Any], Any],
                     test_data: Iterable[Any]) -> Dict[str, Any]:
    """
    Execute *test_func* for each element of *test_data*.  The element is passed
    as a single positional argument.
    """
    failures: List[Dict[str, Any]] = []
    start = time.perf_counter()
    for idx, data in enumerate(test_data):
        try:
            test_func(data)
        except Exception as exc:  # pragma: no cover
            failures.append({
                "index": idx,
                "data": data,
                "exception": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            })
    elapsed = time.perf_counter() - start
    success = not failures
    return TestResult(
        success,
        name="data_driven_test",
        message="All rows passed" if success else f"{len(failures)} failures",
        data={"iterations": len(list(test_data)), "failures": failures, "elapsed": elapsed},
        elapsed=elapsed,
    ).to_dict()


def parallel_test_run(tests: List[Callable[[], Any]],
                     max_workers: int = os.cpu_count() or 1) -> Dict[str, Any]:
    """
    Run a collection of test callables in parallel using a thread pool.
    Returns a summary of successes / failures.
    """
    successes = 0
    failures: List[Dict[str, Any]] = []
    start = time.perf_counter()

    def _run(test_idx: int, fn: Callable[[], Any]) -> Tuple[int, bool, str]:
        try:
            fn()
            return test_idx, True, ""
        except Exception as exc:  # pragma: no cover
            return test_idx, False, traceback.format_exc()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(_run, i, fn): i for i, fn in enumerate(tests)}
        for future in concurrent.futures.as_completed(future_to_idx):
            idx, ok, tb = future.result()
            if ok:
                successes += 1
            else:
                failures.append({"index": idx, "traceback": tb})

    elapsed = time.perf_counter() - start
    overall_success = not failures
    return TestResult(
        overall_success,
        name="parallel_test_run",
        message="All passed" if overall_success else f"{len(failures)} failures",
        data={"total": len(tests), "successes": successes, "failures": failures, "elapsed": elapsed},
        elapsed=elapsed,
    ).to_dict()


def generate_test_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Produce a high‑level summary from a collection of result dictionaries.
    """
    total = len(results)
    passed = sum(1 for r in results if r.get("success"))
    failed = total - passed
    start_times = [r.get("elapsed", 0) for r in results if isinstance(r.get("elapsed"), (int, float))]
    total_time = sum(start_times)
    avg_time = total_time / total if total else 0.0

    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "total_elapsed": total_time,
        "average_elapsed": avg_time,
    }
    return _assert(True, "generate_test_summary", "", **summary).to_dict()


# --------------------------------------------------------------------------- #
# __all__ – Exported public API
# --------------------------------------------------------------------------- #

__all__ = [
    "create_test_suite",
    "run_test_suite",
    "run_single_test",
    "assert_equals",
    "assert_not_equals",
    "assert_true",
    "assert_false",
    "assert_contains",
    "assert_greater",
    "assert_less",
    "assert_in_range",
    "assert_type",
    "assert_raises",
    "assert_dict_has_key",
    "assert_list_length",
    "assert_string_matches",
    "assert_file_exists",
    "assert_files_equal",
    "screenshot_compare",
    "performance_test",
    "stress_test",
    "retry_test",
    "timeout_test",
    "create_test_report",
    "create_html_report",
    "create_json_report",
    "log_test_result",
    "setup_test_env",
    "teardown_test_env",
    "mock_function",
    "restore_mock",
    "capture_output",
    "benchmark",
    "data_driven_test",
    "parallel_test_run",
    "generate_test_summary",
]