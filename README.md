# Pyxils Open

Pyxils Open is a small, clean-room open-source desktop download manager MVP.
It is inspired only by a high-level feature summary: URL probing, streamed
downloads, pause/cancel controls, progress, speed and ETA, and resumable
metadata. It does **not** copy proprietary source code, assets, branding, or
user-interface strings from any existing application.

## Features

- Python 3.12+ and Tkinter desktop UI.
- URL probe using `HEAD`, with a safe `GET` fallback.
- Streaming downloads with HTTP range resume where the server supports it.
- Optional multi-connection segmented downloads for new files when the server
  advertises byte ranges.
- Thread-safe pause and cancel state.
- Progress callbacks containing bytes, total size, speed, and ETA.
- JSON metadata stored next to a download for restart/resume.
- Slow or temporarily stalled range requests are retried from the last byte
  position before the transfer is reported as failed.
- A modern dark Tkinter interface with URL/destination fields, connection
  selection, progress details, and accessible pause/cancel controls.
- Public MEGA file-link downloads with client-side decryption and resumable
  encrypted transfer support.
- A small pinned runtime dependency on PyCryptodome for MEGA AES decryption.

## Setup

Install Python 3.12 or newer, then from this directory run:

```text
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
```

Tkinter is included with the standard Windows Python installer. On Debian-like
Linux distributions, install the system package `python3-tk` if needed.

## Run

```text
python -m pyxils_open
```

Paste a URL, choose a destination, select the connection count, then click
**Probe URL** or **Download**. The dark interface keeps transfer status, speed,
ETA, and resume guidance visible while the download runs. The command `make
run` is equivalent on systems with Make.

Public MEGA file links are accepted directly. Pyxils Open resolves the link
through MEGA's public file API, decrypts the file locally, and saves the
original file name when the destination is still `download.bin`. Account-only
links, folders, uploads, and MEGA login are not included yet.

## Test

The complete offline test command is:

```text
make test
```

It uses only the Python standard library and a local in-process HTTP server;
no internet access is required.

## Windows app

The repository can be packaged as a double-clickable Windows executable. From
PowerShell on Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The result is `dist\PyxilsOpen.exe`. It runs without requiring Python to be
installed on the target Windows machine. The same build is available through
`make package` when GNU Make is installed. GitHub Actions can build the
executable manually or for a version tag such as `v0.1.0`.

## Docker

Build and run the package with:

```text
docker build -t pyxils-open .
docker run --rm -it pyxils-open
```

The container is suitable for core/CLI checks. A graphical Tkinter window
requires a host display integration that is intentionally outside this MVP.

## Clean-room and limitations

This repository was implemented independently from behavior-level requirements
only. It contains no copied proprietary code or assets. Probe and resume
behavior depends on the remote server: servers that omit length headers or do
not honor byte ranges cannot provide exact totals or true resume. Pause is
cooperative (the stream is stopped between chunks), and an interrupted download
can be resumed by starting it again with the same destination. Authentication,
checksums, and a production-grade job queue are out of scope. Segmented
transfers use a temporary `.segments` file and restart from the beginning if
paused or cancelled; ordinary single-connection downloads retain their
existing resumable behavior.
