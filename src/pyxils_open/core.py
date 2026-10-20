"""Reusable standard-library downloader core."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .persistence import load_metadata, remove_metadata, save_metadata
from .mega import download_file as download_mega_file, fetch_file


@dataclass(frozen=True)
class ProbeResult:
    url: str
    status: int
    content_length: int | None
    content_type: str | None
    accepts_ranges: bool
    final_url: str


@dataclass(frozen=True)
class Progress:
    downloaded: int
    total: int | None
    speed_bytes_per_second: float
    eta_seconds: float | None


class DownloadPaused(Exception):
    """Raised when a cooperative pause stops a transfer."""


class DownloadCancelled(Exception):
    """Raised when a transfer is cancelled."""


def format_bytes(value: float) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(value)
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TB"


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


class DownloadManager:
    def __init__(self, opener: Callable = urllib.request.urlopen, chunk_size: int = 64 * 1024):
        self.opener = opener
        self.chunk_size = chunk_size
        self._pause = threading.Event()
        self._cancel = threading.Event()

    def pause(self) -> None:
        self._pause.set()

    def cancel(self) -> None:
        self._cancel.set()

    def resume(self) -> None:
        self._pause.clear()

    def reset(self) -> None:
        self._pause.clear()
        self._cancel.clear()

    def probe(self, url: str, timeout: float = 15) -> ProbeResult:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Pyxils-Open/0.1"})
        try:
            response = self.opener(request, timeout=timeout)
        except (urllib.error.HTTPError, urllib.error.URLError):
            request = urllib.request.Request(url, headers={"Range": "bytes=0-0", "User-Agent": "Pyxils-Open/0.1"})
            response = self.opener(request, timeout=timeout)
        with response:
            length = response.headers.get("Content-Length")
            return ProbeResult(url, response.status, int(length) if length and length.isdigit() else None,
                               response.headers.get_content_type(),
                               response.headers.get("Accept-Ranges", "").lower() == "bytes",
                               response.geturl())

    def download(self, url: str, destination: str | Path, callback: Callable[[Progress], None] | None = None,
                 timeout: float = 120, connections: int = 1) -> Path:
        if "mega.nz/file/" in url and "#" in url:
            mega_file = fetch_file(url, timeout=timeout)
            mega_destination = Path(destination)
            if mega_destination.name == "download.bin":
                mega_destination = mega_destination.with_name(mega_file.name)
            return download_mega_file(
                mega_file,
                mega_destination,
                lambda done, total, speed, eta: callback(Progress(done, total, speed, eta)) if callback else None,
                timeout=timeout,
                chunk_size=self.chunk_size,
            )
        if connections > 1:
            result = self.probe(url, timeout=timeout)
            if result.content_length and result.accepts_ranges:
                return self._download_segmented(url, destination, result.content_length, callback, timeout, connections)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        existing = destination.stat().st_size if destination.exists() else 0
        metadata = load_metadata(destination) or {}
        if metadata.get("url") not in (None, url):
            existing = 0
        headers = {"User-Agent": "Pyxils-Open/0.1"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        request = urllib.request.Request(url, headers=headers)
        response = self.opener(request, timeout=timeout)
        with response:
            status = getattr(response, "status", 200)
            if existing and status != 206:
                existing = 0
            content_length = response.headers.get("Content-Length")
            body_size = int(content_length) if content_length and content_length.isdigit() else None
            total = existing + body_size if body_size is not None and status == 206 else body_size
            mode = "ab" if existing and status == 206 else "wb"
            downloaded = existing if mode == "ab" else 0
            started = time.monotonic()
            save_metadata(destination, {"url": url, "bytes": downloaded, "total": total, "updated": time.time()})
            with destination.open(mode) as output:
                while True:
                    if self._cancel.is_set():
                        save_metadata(destination, {"url": url, "bytes": downloaded, "total": total, "updated": time.time()})
                        raise DownloadCancelled()
                    if self._pause.is_set():
                        save_metadata(destination, {"url": url, "bytes": downloaded, "total": total, "updated": time.time()})
                        raise DownloadPaused()
                    chunk = response.read(self.chunk_size)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    elapsed = max(time.monotonic() - started, 1e-6)
                    speed = max(downloaded - existing, 0) / elapsed
                    remaining = (total - downloaded) / speed if total is not None and speed > 0 else None
                    if callback:
                        callback(Progress(downloaded, total, speed, remaining))
            remove_metadata(destination)
        return destination

    def _download_segmented(self, url: str, destination: str | Path, total: int,
                            callback: Callable[[Progress], None] | None,
                            timeout: float, connections: int) -> Path:
        """Download a new file through independent HTTP byte ranges.

        Segmented transfers use a temporary preallocated file. A cancelled or
        paused transfer never exposes a partially assembled destination, and a
        later call safely starts that segmented transfer again.
        """
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        part_path = destination.with_name(destination.name + ".segments")
        metadata = {"url": url, "bytes": 0, "total": total, "segmented": True, "updated": time.time()}
        if part_path.exists():
            part_path.unlink()
        with part_path.open("wb") as output:
            output.truncate(total)
        save_metadata(destination, metadata)

        workers = max(2, min(int(connections), total))
        chunk = (total + workers - 1) // workers
        ranges = [(start, min(start + chunk, total) - 1) for start in range(0, total, chunk)]
        progress_lock = threading.Lock()
        downloaded = 0
        started = time.monotonic()
        first_error: BaseException | None = None

        def report() -> None:
            elapsed = max(time.monotonic() - started, 1e-6)
            speed = downloaded / elapsed
            eta = (total - downloaded) / speed if speed > 0 else None
            if callback:
                callback(Progress(downloaded, total, speed, eta))

        def worker(start: int, end: int) -> None:
            nonlocal downloaded
            position = start
            for attempt in range(3):
                try:
                    headers = {"User-Agent": "Pyxils-Open/0.1", "Range": f"bytes={position}-{end}"}
                    request = urllib.request.Request(url, headers=headers)
                    response = self.opener(request, timeout=timeout)
                    with response:
                        if getattr(response, "status", 200) != 206:
                            raise urllib.error.HTTPError(url, 200, "server did not honor byte range", response.headers, None)
                        with part_path.open("r+b") as output:
                            output.seek(position)
                            while position <= end:
                                if self._cancel.is_set():
                                    raise DownloadCancelled()
                                if self._pause.is_set():
                                    raise DownloadPaused()
                                block = response.read(min(self.chunk_size, end - position + 1))
                                if not block:
                                    raise IOError(f"range ended early at byte {position}")
                                output.write(block)
                                position += len(block)
                                with progress_lock:
                                    downloaded += len(block)
                                    report()
                    return
                except (TimeoutError, socket.timeout, urllib.error.URLError):
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)

        try:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pyxils-range") as pool:
                futures = [pool.submit(worker, start, end) for start, end in ranges]
                for future in as_completed(futures):
                    try:
                        future.result()
                    except BaseException as exc:
                        first_error = first_error or exc
                        self._cancel.set()
            if first_error:
                raise first_error
            part_path.replace(destination)
            remove_metadata(destination)
            return destination
        except (DownloadPaused, DownloadCancelled):
            save_metadata(destination, {**metadata, "bytes": downloaded, "updated": time.time()})
            raise
        except BaseException:
            save_metadata(destination, {**metadata, "bytes": downloaded, "updated": time.time()})
            raise
        finally:
            self._cancel.clear()
