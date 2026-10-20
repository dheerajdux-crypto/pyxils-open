"""Tkinter application entry point."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import DownloadCancelled, DownloadManager, DownloadPaused, Progress, format_bytes, format_duration


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Pyxils Open")
        self.geometry("700x360")
        self.manager = DownloadManager()
        self.url = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "Downloads" / "download.bin"))
        self.status = tk.StringVar(value="Ready")
        self.progress = tk.DoubleVar()
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.url).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 12))
        ttk.Label(frame, text="Destination").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.destination).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        ttk.Button(frame, text="Choose…", command=self.choose).grid(row=3, column=2, padx=(8, 0))
        ttk.Button(frame, text="Probe", command=self.probe).grid(row=4, column=0, sticky="w")
        ttk.Button(frame, text="Download", command=self.start).grid(row=4, column=1, sticky="w")
        ttk.Button(frame, text="Pause", command=self.manager.pause).grid(row=4, column=2, sticky="e")
        ttk.Button(frame, text="Cancel", command=self.manager.cancel).grid(row=5, column=2, sticky="e", pady=8)
        ttk.Progressbar(frame, variable=self.progress, maximum=100).grid(row=5, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(frame, textvariable=self.status, wraplength=640).grid(row=6, column=0, columnspan=3, sticky="w")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def choose(self) -> None:
        chosen = filedialog.asksaveasfilename()
        if chosen:
            self.destination.set(chosen)

    def probe(self) -> None:
        try:
            result = self.manager.probe(self.url.get().strip())
            length = format_bytes(result.content_length) if result.content_length is not None else "unknown size"
            self.status.set(f"{result.status} · {length} · ranges: {'yes' if result.accepts_ranges else 'no'}")
        except Exception as exc:
            messagebox.showerror("Probe failed", str(exc))

    def start(self) -> None:
        self.manager.reset()
        self.status.set("Starting…")
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self) -> None:
        def update(value: Progress) -> None:
            percent = value.downloaded / value.total * 100 if value.total else 0
            self.after(0, self.progress.set, percent)
            self.after(0, self.status.set, f"{format_bytes(value.downloaded)} · {format_bytes(value.speed_bytes_per_second)}/s · ETA {format_duration(value.eta_seconds)}")
        try:
            path = self.manager.download(self.url.get().strip(), self.destination.get().strip(), update)
            self.after(0, self.status.set, f"Complete: {path}")
        except DownloadPaused:
            self.after(0, self.status.set, "Paused; click Download to resume")
        except DownloadCancelled:
            self.after(0, self.status.set, "Cancelled; partial file retained")
        except Exception as exc:
            self.after(0, messagebox.showerror, "Download failed", str(exc))


def main() -> None:
    App().mainloop()
