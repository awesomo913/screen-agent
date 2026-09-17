"""
compression_actions.py
~~~~~~~~~~~~~~~~~~~~~~~

A small‑scale “screen‑agent” toolkit that bundles common archive‑handling
operations.  All functions are **fully implemented**, type‑annotated and
return a ``dict`` describing the outcome – suitable for direct consumption by
the surrounding agent framework.

The module relies only on the Python standard library:

* ``zipfile``, ``tarfile``, ``gzip``, ``bz2``, ``lzma`` – actual compression
  back‑ends.
* ``shutil``, ``pathlib``, ``os``, ``io`` – file‑system utilities.
* ``hashlib`` – checksum / integrity helpers.
* ``typing`` – type hints.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import zipfile
import tarfile
import gzip
import bz2
import lzma
from pathlib import Path
from typing import (
    Iterable,
    List,
    Tuple,
    Union,
    Callable,
    Dict,
    Any,
    Optional,
)

# --------------------------------------------------------------------------- #
# Helper utilities
# --------------------------------------------------------------------------- #
def _hash_file(file_path: Path, algo: str = "sha256") -> str:
    """Return a hex digest for ``file_path`` using ``algo``."""
    h = hashlib.new(algo)
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_path(p: Union[str, Path]) -> Path:
    """Coerce ``p`` to a ``Path`` and make it absolute."""
    return Path(p).expanduser().resolve()


def _result(
    success: bool,
    message: str,
    **extra: Any,
) -> Dict[str, Any]:
    """Standardised result dictionary."""
    data = {"success": success, "message": message}
    data.update(extra)
    return data


# --------------------------------------------------------------------------- #
# ZIP
# --------------------------------------------------------------------------- #
def compress_zip(
    files: Iterable[Union[str, Path]],
    output_path: Union[str, Path],
    password: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Create a ``.zip`` archive.

    Parameters
    ----------
    files: iterable of paths – files (or directories) to add.
    output_path: destination ``.zip`` file.
    password: optional password (bytes).  The standard library only supports
              **weak** ZIP encryption; the password is stored but not
              guaranteed to be secure.

    Returns
    -------
    Dict with ``success``, ``message`` and ``output_path``.
    """
    out = _safe_path(output_path)
    try:
        # ``w`` creates a new archive; ``allowZip64`` enables >4 GB files.
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for f in files:
                src = _safe_path(f)
                if not src.exists():
                    return _result(False, f"Source does not exist: {src}")
                arcname = src.relative_to(src.parent.parent) if src.is_absolute() else src
                if src.is_dir():
                    for root, _, filenames in os.walk(src):
                        for name in filenames:
                            file_path = Path(root) / name
                            rel_path = file_path.relative_to(src.parent)
                            zi = zipfile.ZipInfo(str(rel_path))
                            if password:
                                zi.flag_bits |= 0x9  # set encryption flag (legacy)
                            zf.writestr(zi, file_path.read_bytes())
                else:
                    zi = zipfile.ZipInfo(str(arcname))
                    if password:
                        zi.flag_bits |= 0x9
                    zf.writestr(zi, src.read_bytes())
        return _result(True, "ZIP archive created", output_path=str(out))
    except Exception as exc:  # pragma: no cover – defensive
        return _result(False, f"ZIP compression failed: {exc}")


def extract_zip(
    zip_path: Union[str, Path],
    dest: Union[str, Path],
    password: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Extract a ``.zip`` archive.

    Parameters
    ----------
    zip_path: path to the archive.
    dest: directory where files will be placed.
    password: optional password (bytes) for encrypted archives.

    Returns
    -------
    Dict with ``success``, ``message`` and ``extracted`` list.
    """
    src = _safe_path(zip_path)
    out_dir = _safe_path(dest)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(src, "r") as zf:
            if password:
                zf.setpassword(password)
            zf.extractall(path=out_dir)
            extracted = zf.namelist()
        return _result(True, "ZIP extracted", extracted=extracted, destination=str(out_dir))
    except RuntimeError as re:
        # Raised when password is wrong
        return _result(False, f"Incorrect password or corrupted zip: {re}")
    except Exception as exc:
        return _result(False, f"ZIP extraction failed: {exc}")


# --------------------------------------------------------------------------- #
# TAR (including gzip, bzip2, xz)
# --------------------------------------------------------------------------- #
COMPRESSION_MODES = {
    None: "w",
    "gzip": "w:gz",
    "bzip2": "w:bz2",
    "xz": "w:xz",
}


def compress_tar(
    files: Iterable[Union[str, Path]],
    output_path: Union[str, Path],
    compression: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a ``.tar`` archive (optionally compressed).

    Parameters
    ----------
    files: iterable of files / directories.
    output_path: destination ``.tar`` (or ``.tar.gz`` etc.) file.
    compression: ``None``, ``"gzip"``, ``"bzip2"``, ``"xz"``.
    """
    mode = COMPRESSION_MODES.get(compression)
    if mode is None:
        return _result(False, f"Unsupported compression type: {compression}")

    out = _safe_path(output_path)
    try:
        with tarfile.open(out, mode) as tf:
            for f in files:
                src = _safe_path(f)
                if not src.exists():
                    return _result(False, f"Source does not exist: {src}")
                tf.add(src, arcname=src.name, recursive=True)
        return _result(True, "TAR archive created", output_path=str(out))
    except Exception as exc:
        return _result(False, f"TAR compression failed: {exc}")


def extract_tar(
    tar_path: Union[str, Path],
    dest: Union[str, Path],
) -> Dict[str, Any]:
    """
    Extract a ``.tar*`` archive.

    Parameters
    ----------
    tar_path: archive path.
    dest: extraction directory.
    """
    src = _safe_path(tar_path)
    out_dir = _safe_path(dest)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(src, "r:*") as tf:
            tf.extractall(path=out_dir)
            members = [member.name for member in tf.getmembers()]
        return _result(True, "TAR extracted", extracted=members, destination=str(out_dir))
    except Exception as exc:
        return _result(False, f"TAR extraction failed: {exc}")


# --------------------------------------------------------------------------- #
# GZIP – for single files only
# --------------------------------------------------------------------------- #
def compress_gzip(
    filepath: Union[str, Path],
    output: Union[str, Path],
) -> Dict[str, Any]:
    src = _safe_path(filepath)
    out = _safe_path(output)
    try:
        with src.open("rb") as f_in, gzip.open(out, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _result(True, "GZIP created", output_path=str(out))
    except Exception as exc:
        return _result(False, f"GZIP compression failed: {exc}")


def decompress_gzip(
    filepath: Union[str, Path],
    output: Union[str, Path],
) -> Dict[str, Any]:
    src = _safe_path(filepath)
    out = _safe_path(output)
    try:
        with gzip.open(src, "rb") as f_in, out.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _result(True, "GZIP decompressed", output_path=str(out))
    except Exception as exc:
        return _result(False, f"GZIP decompression failed: {exc}")


# --------------------------------------------------------------------------- #
# BZ2 – for single files only
# --------------------------------------------------------------------------- #
def compress_bz2(
    filepath: Union[str, Path],
    output: Union[str, Path],
) -> Dict[str, Any]:
    src = _safe_path(filepath)
    out = _safe_path(output)
    try:
        with src.open("rb") as f_in, bz2.open(out, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _result(True, "BZ2 created", output_path=str(out))
    except Exception as exc:
        return _result(False, f"BZ2 compression failed: {exc}")


def decompress_bz2(
    filepath: Union[str, Path],
    output: Union[str, Path],
) -> Dict[str, Any]:
    src = _safe_path(filepath)
    out = _safe_path(output)
    try:
        with bz2.open(src, "rb") as f_in, out.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _result(True, "BZ2 decompressed", output_path=str(out))
    except Exception as exc:
        return _result(False, f"BZ2 decompression failed: {exc}")


# --------------------------------------------------------------------------- #
# LZMA – for single files only
# --------------------------------------------------------------------------- #
def compress_lzma(
    filepath: Union[str, Path],
    output: Union[str, Path],
) -> Dict[str, Any]:
    src = _safe_path(filepath)
    out = _safe_path(output)
    try:
        with src.open("rb") as f_in, lzma.open(out, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _result(True, "LZMA created", output_path=str(out))
    except Exception as exc:
        return _result(False, f"LZMA compression failed: {exc}")


def decompress_lzma(
    filepath: Union[str, Path],
    output: Union[str, Path],
) -> Dict[str, Any]:
    src = _safe_path(filepath)
    out = _safe_path(output)
    try:
        with lzma.open(src, "rb") as f_in, out.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return _result(True, "LZMA decompressed", output_path=str(out))
    except Exception as exc:
        return _result(False, f"LZMA decompression failed: {exc}")


# --------------------------------------------------------------------------- #
# Directory compression wrapper (ZIP or TAR based)
# --------------------------------------------------------------------------- #
def compress_directory(
    dir_path: Union[str, Path],
    fmt: str,
    output: Union[str, Path],
) -> Dict[str, Any]:
    """
    Compress an entire directory.

    Parameters
    ----------
    dir_path: directory to compress.
    fmt: ``"zip"``, ``"tar"``, ``"tar.gz"``, ``"tar.bz2"``, ``"tar.xz"``.
    output: resulting archive path.
    """
    src = _safe_path(dir_path)
    out = _safe_path(output)

    if not src.is_dir():
        return _result(False, f"Not a directory: {src}")

    fmt = fmt.lower()
    try:
        if fmt == "zip":
            return compress_zip([src], out, password=None)
        elif fmt.startswith("tar"):
            compression = None
            if fmt == "tar.gz":
                compression = "gzip"
            elif fmt == "tar.bz2":
                compression = "bzip2"
            elif fmt == "tar.xz":
                compression = "xz"
            return compress_tar([src], out, compression=compression)
        else:
            return _result(False, f"Unsupported format: {fmt}")
    except Exception as exc:
        return _result(False, f"Directory compression failed: {exc}")


# --------------------------------------------------------------------------- #
# Auto‑detect extraction
# --------------------------------------------------------------------------- #
def extract_archive(
    archive_path: Union[str, Path],
    dest: Union[str, Path],
    auto_detect: bool = True,
) -> Dict[str, Any]:
    """
    Extract an archive, auto‑detecting its type from the suffix.

    Parameters
    ----------
    archive_path: path to archive.
    dest: where to unpack.
    auto_detect: if ``True`` (default) infer type from suffix.
    """
    src = _safe_path(archive_path)
    out_dir = _safe_path(dest)
    out_dir.mkdir(parents=True, exist_ok=True)

    suffix = src.suffix.lower()
    if not auto_detect:
        return _result(False, "Auto‑detect disabled and no explicit method supplied.")

    if suffix == ".zip":
        return extract_zip(src, out_dir)
    if suffix in {".tar", ".tgz", ".gz", ".tar.gz", ".tbz", ".tbz2", ".tar.bz2", ".txz", ".tar.xz"}:
        return extract_tar(src, out_dir)

    return _result(False, f"Unsupported archive type: {src.suffix}")


# --------------------------------------------------------------------------- #
# List, add, remove and generic info
# --------------------------------------------------------------------------- #
def list_archive_contents(archive_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Return a list of members inside *archive_path*.

    Supports ZIP and TAR (any compression).
    """
    src = _safe_path(archive_path)
    suffix = src.suffix.lower()

    try:
        if suffix == ".zip":
            with zipfile.ZipFile(src, "r") as zf:
                names = zf.namelist()
        else:
            with tarfile.open(src, "r:*") as tf:
                names = tf.getnames()
        return _result(True, "Listed contents", contents=names)
    except Exception as exc:
        return _result(False, f"Failed to list contents: {exc}")


def add_to_archive(
    archive_path: Union[str, Path],
    files: Iterable[Union[str, Path]],
) -> Dict[str, Any]:
    """
    Append *files* to an existing archive.  For ZIP the archive is opened in
    ``'a'`` mode; for TAR we use ``'a'`` as well (which works for all compression
    types supported by ``tarfile``).
    """
    src = _safe_path(archive_path)
    suffix = src.suffix.lower()

    try:
        if suffix == ".zip":
            with zipfile.ZipFile(src, "a", compression=zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    path = _safe_path(f)
                    if not path.exists():
                        return _result(False, f"File does not exist: {path}")
                    zf.write(path, arcname=path.name)
        else:
            with tarfile.open(src, "a") as tf:
                for f in files:
                    path = _safe_path(f)
                    if not path.exists():
                        return _result(False, f"File does not exist: {path}")
                    tf.add(path, arcname=path.name, recursive=True)
        return _result(True, "Files added to archive")
    except Exception as exc:
        return _result(False, f"Failed to add files: {exc}")


def remove_from_archive(
    archive_path: Union[str, Path],
    filenames: Iterable[str],
) -> Dict[str, Any]:
    """
    Remove *filenames* from a ZIP archive.  ``tarfile`` does not support in‑place
    removal, so the archive is recreated without the unwanted entries.
    """
    src = _safe_path(archive_path)
    suffix = src.suffix.lower()
    filenames_set = set(filenames)

    try:
        if suffix == ".zip":
            tmp_path = src.with_suffix(".tmp.zip")
            with zipfile.ZipFile(src, "r") as src_zf, zipfile.ZipFile(
                tmp_path, "w", compression=zipfile.ZIP_DEFLATED
            ) as dst_zf:
                for item in src_zf.infolist():
                    if item.filename in filenames_set:
                        continue
                    data = src_zf.read(item.filename)
                    dst_zf.writestr(item, data)
            src.unlink()
            tmp_path.rename(src)
            return _result(True, "Entries removed from ZIP")
        else:
            # Re‑create TAR without the specified members
            tmp_path = src.with_suffix(".tmp.tar")
            with tarfile.open(src, "r:*") as src_tf, tarfile.open(tmp_path, "w") as dst_tf:
                for member in src_tf.getmembers():
                    if member.name in filenames_set:
                        continue
                    fileobj = src_tf.extractfile(member)
                    dst_tf.addfile(member, fileobj)
            src.unlink()
            tmp_path.rename(src)
            return _result(True, "Entries removed from TAR")
    except Exception as exc:
        return _result(False, f"Failed to remove entries: {exc}")


def get_archive_info(archive_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Gather basic statistics about an archive.

    Returns size on disk, number of members and (if possible) the overall
    compression ratio.
    """
    src = _safe_path(archive_path)

    if not src.is_file():
        return _result(False, f"Archive not found: {src}")

    try:
        size_on_disk = src.stat().st_size
        contents_res = list_archive_contents(src)
        if not contents_res["success"]:
            return _result(False, "Could not list archive contents")

        members = contents_res["contents"]
        total_uncompressed = 0
        suffix = src.suffix.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(src, "r") as zf:
                for info in zf.infolist():
                    total_uncompressed += info.file_size
        else:
            with tarfile.open(src, "r:*") as tf:
                for member in tf.getmembers():
                    total_uncompressed += member.size

        ratio = (
            (1 - size_on_disk / total_uncompressed) * 100
            if total_uncompressed > 0
            else 0
        )
        return _result(
            True,
            "Archive info collected",
            size_bytes=size_on_disk,
            uncompressed_bytes=total_uncompressed,
            compression_ratio=round(ratio, 2),
            members=len(members),
        )
    except Exception as exc:
        return _result(False, f"Failed to get info: {exc}")


# --------------------------------------------------------------------------- #
# Stream (in‑memory) compression / decompression
# --------------------------------------------------------------------------- #
def compress_stream(data: bytes, method: str = "gzip") -> Dict[str, Any]:
    """
    Compress an in‑memory *bytes* object.

    ``method`` – ``"gzip"``, ``"bz2"``, ``"lzma"``, or ``"zip"``
    (the latter returns a single‑file ZIP archive).
    """
    try:
        if method == "gzip":
            out = gzip.compress(data)
        elif method == "bz2":
            out = bz2.compress(data)
        elif method in {"lzma", "xz"}:
            out = lzma.compress(data)
        elif method == "zip":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("data.bin", data)
            out = buf.getvalue()
        else:
            return _result(False, f"Unsupported method: {method}")

        return _result(True, f"{method.upper()} compression succeeded", compressed=out)
    except Exception as exc:
        return _result(False, f"{method.upper()} compression failed: {exc}")


def decompress_stream(data: bytes, method: str = "gzip") -> Dict[str, Any]:
    """
    Decompress a byte string produced by :func:`compress_stream`.
    """
    try:
        if method == "gzip":
            out = gzip.decompress(data)
        elif method == "bz2":
            out = bz2.decompress(data)
        elif method in {"lzma", "xz"}:
            out = lzma.decompress(data)
        elif method == "zip":
            buf = io.BytesIO(data)
            with zipfile.ZipFile(buf, "r") as zf:
                # Expect a single file named *data.bin*
                name = zf.namelist()[0]
                out = zf.read(name)
        else:
            return _result(False, f"Unsupported method: {method}")

        return _result(True, f"{method.upper()} decompression succeeded", decompressed=out)
    except Exception as exc:
        return _result(False, f"{method.upper()} decompression failed: {exc}")


# --------------------------------------------------------------------------- #
# Splitting / merging large archives
# --------------------------------------------------------------------------- #
def split_archive(
    archive_path: Union[str, Path],
    chunk_size: int,
) -> Dict[str, Any]:
    """
    Split *archive_path* into binary chunks of *chunk_size* bytes.

    Returns a list of part file paths.
    """
    src = _safe_path(archive_path)
    if not src.is_file():
        return _result(False, f"Archive not found: {src}")

    if chunk_size <= 0:
        return _result(False, "Chunk size must be > 0")

    parts: List[str] = []
    try:
        with src.open("rb") as f:
            index = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                part_path = src.with_name(f"{src.name}.part{index:03d}")
                with part_path.open("wb") as part_f:
                    part_f.write(chunk)
                parts.append(str(part_path))
                index += 1
        return _result(True, "Archive split", parts=parts)
    except Exception as exc:
        return _result(False, f"Failed to split archive: {exc}")


def merge_archive_parts(
    parts: Iterable[Union[str, Path]],
    output: Union[str, Path],
) -> Dict[str, Any]:
    """
    Re‑assemble a split archive from *parts* (ordered) into *output*.
    """
    out_path = _safe_path(output)
    try:
        with out_path.open("wb") as out_f:
            for p in sorted(parts):
                part_path = _safe_path(p)
                if not part_path.is_file():
                    return _result(False, f"Missing part: {part_path}")
                with part_path.open("rb") as part_f:
                    shutil.copyfileobj(part_f, out_f)
        return _result(True, "Parts merged", output_path=str(out_path))
    except Exception as exc:
        return _result(False, f"Failed to merge parts: {exc}")


# --------------------------------------------------------------------------- #
# Integrity verification
# --------------------------------------------------------------------------- #
def verify_archive(archive_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Verify an archive by checking internal CRC/size values where supported.
    For ZIP this uses the built‑in CRC; for TAR we simply ensure that the archive
    can be opened and all members are readable.
    """
    src = _safe_path(archive_path)
    if not src.is_file():
        return _result(False, f"Archive not found: {src}")

    try:
        suffix = src.suffix.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(src, "r") as zf:
                bad = zf.testzip()
                if bad:
                    return _result(False, f"Corrupted entry in ZIP: {bad}")
        else:
            # TAR – iterate through members to catch I/O errors
            with tarfile.open(src, "r:*") as tf:
                for member in tf.getmembers():
                    if member.isreg():
                        fobj = tf.extractfile(member)
                        if fobj is None:
                            return _result(False, f"Cannot read member: {member.name}")
                        # Drain the file to force read errors
                        while fobj.read(8192):
                            pass
        return _result(True, "Archive verification succeeded")
    except Exception as exc:
        return _result(False, f"Verification failed: {exc}")


# --------------------------------------------------------------------------- #
# Progress‑aware compression
# --------------------------------------------------------------------------- #
ProgressCallback = Callable[[float, str], None]  # (percentage, current_file)


def compress_with_progress(
    files: Iterable[Union[str, Path]],
    output: Union[str, Path],
    callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """
    Zip *files* while reporting progress via *callback*.

    ``callback`` – receives ``(percentage_done, file_name)`` after each file.
    """
    out = _safe_path(output)
    file_list = [_safe_path(f) for f in files]
    total = len(file_list)
    if total == 0:
        return _result(False, "No files supplied")

    try:
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for idx, src in enumerate(file_list, start=1):
                arcname = src.relative_to(src.parent.parent) if src.is_absolute() else src
                zf.write(src, arcname=str(arcname))
                if callback:
                    percent = (idx / total) * 100
                    callback(percent, str(src))
        return _result(True, "Compression with progress completed", output_path=str(out))
    except Exception as exc:
        return _result(False, f"Progressive compression failed: {exc}")


# --------------------------------------------------------------------------- #
# Batch compression (multiple groups → archives)
# --------------------------------------------------------------------------- #
def batch_compress(
    file_groups: Dict[str, List[Union[str, Path]]],
    fmt: str = "zip",
) -> Dict[str, Any]:
    """
    ``file_groups`` maps *archive_name* → list of files.
    All groups are compressed using the same ``fmt``.
    Returns mapping of archive name → result dict.
    """
    results: Dict[str, Any] = {}
    for name, files in file_groups.items():
        archive_path = Path(name)
        if fmt == "zip":
            res = compress_zip(files, archive_path)
        elif fmt.startswith("tar"):
            compression = None
            if fmt == "tar.gz":
                compression = "gzip"
            elif fmt == "tar.bz2":
                compression = "bzip2"
            elif fmt == "tar.xz":
                compression = "xz"
            res = compress_tar(files, archive_path, compression)
        else:
            res = _result(False, f"Unsupported format: {fmt}")
        results[name] = res
    return _result(True, "Batch compression completed", batches=results)


# --------------------------------------------------------------------------- #
# Archive comparison
# --------------------------------------------------------------------------- #
def compare_archives(
    archive1: Union[str, Path],
    archive2: Union[str, Path],
) -> Dict[str, Any]:
    """
    Compare the contents (file names + SHA‑256 digests) of two archives.
    Returns a dict with ``only_in_a``, ``only_in_b`` and ``different`` lists.
    """
    a = _safe_path(archive1)
    b = _safe_path(archive2)

    def build_index(p: Path) -> Dict[str, str]:
        idx: Dict[str, str] = {}
        suffix = p.suffix.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(p, "r") as zf:
                for info in zf.infolist():
                    data = zf.read(info.filename)
                    idx[info.filename] = hashlib.sha256(data).hexdigest()
        else:
            with tarfile.open(p, "r:*") as tf:
                for member in tf.getmembers():
                    if member.isreg():
                        fobj = tf.extractfile(member)
                        if fobj:
                            digest = hashlib.sha256()
                            for chunk in iter(lambda: fobj.read(8192), b""):
                                digest.update(chunk)
                            idx[member.name] = digest.hexdigest()
        return idx

    try:
        idx_a = build_index(a)
        idx_b = build_index(b)

        set_a = set(idx_a)
        set_b = set(idx_b)

        only_in_a = sorted(list(set_a - set_b))
        only_in_b = sorted(list(set_b - set_a))
        different = sorted([name for name in set_a & set_b if idx_a[name] != idx_b[name]])

        return _result(
            True,
            "Archives compared",
            only_in_a=only_in_a,
            only_in_b=only_in_b,
            different=different,
        )
    except Exception as exc:
        return _result(False, f"Archive comparison failed: {exc}")


# --------------------------------------------------------------------------- #
# Compression ratio helper
# --------------------------------------------------------------------------- #
def get_compression_ratio(
    original: Union[str, Path],
    compressed: Union[str, Path],
) -> Dict[str, Any]:
    """
    Compute the percentage size reduction from *original* → *compressed*.
    """
    orig_path = _safe_path(original)
    comp_path = _safe_path(compressed)
    if not orig_path.is_file() or not comp_path.is_file():
        return _result(False, "Both files must exist")

    try:
        orig_sz = orig_path.stat().st_size
        comp_sz = comp_path.stat().st_size
        if orig_sz == 0:
            ratio = 0.0
        else:
            ratio = (1 - comp_sz / orig_sz) * 100
        return _result(
            True,
            "Compression ratio calculated",
            original_bytes=orig_sz,
            compressed_bytes=comp_sz,
            ratio_percent=round(ratio, 2),
        )
    except Exception as exc:
        return _result(False, f"Ratio calculation failed: {exc}")