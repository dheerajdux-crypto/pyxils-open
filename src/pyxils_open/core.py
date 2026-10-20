"""Reusable standard-library downloader core."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .persistence import load_metadata, remove_metadata, save_metadata


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
                 timeout: float = 30) -> Path:
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
