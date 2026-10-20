"""Clean-room support for public MEGA file links."""

from __future__ import annotations

import base64
import json
import random
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .persistence import load_metadata, remove_metadata, save_metadata


@dataclass(frozen=True)
class MegaFile:
    handle: str
    key: bytes
    name: str
    size: int
    download_url: str


def is_public_folder_link(url: str) -> bool:
    return "mega.nz/folder/" in url and "#" in url


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _encode_api_request(payload: list[dict]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def parse_public_link(url: str) -> tuple[str, bytes]:
    marker = "/file/"
    if "mega.nz" not in url or marker not in url or "#" not in url:
        raise ValueError("Expected a public MEGA file link")
    fragment = url.split("#", 1)[1].split("?", 1)[0]
    handle = url.split(marker, 1)[1].split("#", 1)[0].split("?", 1)[0]
    key = _decode(fragment)
    if not handle or len(key) != 32:
        raise ValueError("Invalid MEGA file link or decryption key")
    return handle, key


def parse_public_folder_link(url: str) -> tuple[str, bytes]:
    marker = "/folder/"
    if "mega.nz" not in url or marker not in url or "#" not in url:
        raise ValueError("Expected a public MEGA folder link")
    handle = url.split(marker, 1)[1].split("#", 1)[0].split("?", 1)[0]
    key = _decode(url.split("#", 1)[1].split("?", 1)[0])
    if not handle or len(key) != 16:
        raise ValueError("Invalid MEGA folder link or decryption key")
    return handle, key


def fetch_file(url: str, timeout: float = 120) -> MegaFile:
    from Crypto.Cipher import AES

    handle, link_key = parse_public_link(url)
    request_url = f"https://g.api.mega.co.nz/cs?id={random.randrange(1 << 30)}"
    request = urllib.request.Request(
        request_url,
        data=_encode_api_request([{"a": "g", "g": 1, "p": handle}]),
        headers={"Content-Type": "application/json", "User-Agent": "Pyxils-Open/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))[0]
    if isinstance(result, int) or "g" not in result or "s" not in result or "at" not in result:
        raise RuntimeError(f"MEGA API error: {result}")

    # MEGA derives the AES file key by XORing the first and second halves of
    # the 256-bit link key. Attributes use AES-CBC with a zero IV.
    file_key = bytes(a ^ b for a, b in zip(link_key[:8], link_key[16:24])) + bytes(
        a ^ b for a, b in zip(link_key[8:16], link_key[24:32])
    )
    attributes = AES.new(file_key, AES.MODE_CBC, b"\0" * 16).decrypt(_decode(result["at"]))
    if not attributes.startswith(b"MEGA"):
        raise RuntimeError("MEGA file attributes could not be decrypted")
    info = json.loads(attributes[4:].rstrip(b"\0").decode("utf-8"))
    return MegaFile(handle, link_key, info.get("n", "mega-download.bin"), int(result["s"]), result["g"])


def fetch_folder(url: str, timeout: float = 120) -> list[MegaFile]:
    """Resolve downloadable files from a public MEGA folder."""
    from Crypto.Cipher import AES

    folder_handle, folder_key = parse_public_folder_link(url)
    api_url = f"https://g.api.mega.co.nz/cs?id={random.randrange(1 << 30)}&n={folder_handle}"
    request = urllib.request.Request(
        api_url,
        data=_encode_api_request([{"a": "f", "c": "1", "r": "1", "ca": "1"}]),
        headers={"Content-Type": "application/json", "User-Agent": "Pyxils-Open/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))[0]
    nodes = result.get("f", [])
    files: list[MegaFile] = []
    for node in nodes:
        if node.get("t") != 0 or not node.get("k") or not node.get("a"):
            continue
        node_key = None
        attributes = None
        for segment in str(node["k"]).split("/"):
            encoded = segment.split(":")[-1]
            try:
                candidate = AES.new(folder_key, AES.MODE_ECB).decrypt(_decode(encoded))
                candidate_attr = AES.new(candidate, AES.MODE_CBC, b"\0" * 16).decrypt(_decode(node["a"]))
                if candidate_attr.startswith(b"MEGA"):
                    attributes = json.loads(candidate_attr[4:].rstrip(b"\0").decode("utf-8"))
                    if attributes.get("n"):
                        node_key = candidate
                        break
            except (ValueError, KeyError, json.JSONDecodeError):
                continue
        if not node_key or not attributes:
            continue
        file_api_url = f"https://g.api.mega.co.nz/cs?id={random.randrange(1 << 30)}&n={folder_handle}"
        file_request = urllib.request.Request(
            file_api_url,
            data=_encode_api_request([{"a": "g", "g": 1, "n": node["h"]}]),
            headers={"Content-Type": "application/json", "User-Agent": "Pyxils-Open/0.1"},
        )
        with urllib.request.urlopen(file_request, timeout=timeout) as response:
            file_result = json.loads(response.read().decode("utf-8"))[0]
        if file_result.get("g") and file_result.get("s") is not None:
            files.append(MegaFile(node["h"], node_key, attributes["n"], int(file_result["s"]), file_result["g"]))
    return files


def download_file(file: MegaFile, destination: str | Path,
                  callback: Callable[[int, int, float, float | None], None] | None = None,
                  timeout: float = 120, chunk_size: int = 64 * 1024) -> Path:
    from Crypto.Cipher import AES

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    existing = destination.stat().st_size if destination.exists() else 0
    metadata = load_metadata(destination) or {}
    if metadata.get("url") != file.download_url or existing >= file.size:
        existing = 0
    headers = {"User-Agent": "Pyxils-Open/0.1"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(file.download_url, headers=headers)
    response = urllib.request.urlopen(request, timeout=timeout)
    with response:
        if existing and getattr(response, "status", 200) != 206:
            existing = 0
        start = existing if existing and getattr(response, "status", 200) == 206 else 0
        mode = "ab" if start else "wb"
        # The MEGA CTR counter advances once per 16-byte block.
        counter = int.from_bytes(file.key[16:24] + b"\0" * 8, "big") + start // 16
        cipher = AES.new(file_key(file.key), AES.MODE_CTR, nonce=b"", initial_value=counter)
        downloaded = start
        started = time.monotonic()
        save_metadata(destination, {"url": file.download_url, "bytes": downloaded, "total": file.size, "mega": True, "updated": time.time()})
        with destination.open(mode) as output:
            while downloaded < file.size:
                block = response.read(min(chunk_size, file.size - downloaded))
                if not block:
                    raise IOError("MEGA download ended before the expected file size")
                output.write(cipher.decrypt(block))
                downloaded += len(block)
                elapsed = max(time.monotonic() - started, 1e-6)
                speed = max(downloaded - start, 0) / elapsed
                eta = (file.size - downloaded) / speed if speed > 0 else None
                if callback:
                    callback(downloaded, file.size, speed, eta)
    remove_metadata(destination)
    return destination


def file_key(link_key: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(link_key[:8], link_key[16:24])) + bytes(
        a ^ b for a, b in zip(link_key[8:16], link_key[24:32])
    )
