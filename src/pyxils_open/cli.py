"""Tkinter application entry point."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import DownloadCancelled, DownloadManager, DownloadPaused, Progress, format_bytes, format_duration
from .mega import fetch_file


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Pyxils Open")
        self.geometry("820x600")
        self.minsize(700, 520)
        self.configure(bg="#101419")
        self.manager = DownloadManager()
        self.url = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "Downloads" / "download.bin"))
        self.connections = tk.StringVar(value="4 connections")
        self.status = tk.StringVar(value="Ready for a download")
        self.status_detail = tk.StringVar(value="Paste a URL to get started")
        self.progress = tk.DoubleVar()
        self._running = False
        self._build()

    def _build(self) -> None:
        colors = {
            "bg": "#101419", "surface": "#171d24", "surface2": "#1d252e",
            "text": "#edf2f7", "muted": "#9aa8b6", "accent": "#4dd4a8",
            "accent_active": "#72e3bc", "border": "#2b3743", "danger": "#f38b8b",
        }
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=colors["bg"])
        style.configure("Card.TFrame", background=colors["surface"])
        style.configure("Header.TLabel", background=colors["bg"], foreground=colors["text"], font=("TkDefaultFont", 22, "bold"))
        style.configure("Subtitle.TLabel", background=colors["bg"], foreground=colors["muted"], font=("TkDefaultFont", 10))
        style.configure("Section.TLabel", background=colors["surface"], foreground=colors["text"], font=("TkDefaultFont", 10, "bold"))
        style.configure("Field.TLabel", background=colors["surface"], foreground=colors["muted"], font=("TkDefaultFont", 9, "bold"))
        style.configure("Body.TLabel", background=colors["surface"], foreground=colors["muted"], font=("TkDefaultFont", 9))
        style.configure("Status.TLabel", background=colors["surface2"], foreground=colors["text"], font=("TkDefaultFont", 10, "bold"))
        style.configure("Detail.TLabel", background=colors["surface2"], foreground=colors["muted"], font=("TkDefaultFont", 9))
        style.configure("TEntry", fieldbackground="#202932", foreground=colors["text"], insertcolor=colors["text"], bordercolor=colors["border"], lightcolor=colors["border"], darkcolor=colors["border"], padding=9)
        style.map("TEntry", bordercolor=[("focus", colors["accent"])])
        style.configure("TCombobox", fieldbackground="#202932", background="#202932", foreground=colors["text"], arrowcolor=colors["muted"], bordercolor=colors["border"], padding=7)
        style.configure("Secondary.TButton", background=colors["surface2"], foreground=colors["text"], bordercolor=colors["border"], padding=(12, 8))
        style.map("Secondary.TButton", background=[("active", colors["border"]), ("disabled", colors["surface2"])])
        style.configure("Accent.TButton", background=colors["accent"], foreground="#07130f", bordercolor=colors["accent"], padding=(20, 10), font=("TkDefaultFont", 10, "bold"))
        style.map("Accent.TButton", background=[("active", colors["accent_active"]), ("disabled", "#36584d")])
        style.configure("Danger.TButton", background=colors["surface2"], foreground=colors["danger"], bordercolor=colors["border"], padding=(12, 8))
        style.map("Danger.TButton", background=[("active", colors["border"])])
        style.configure("Dark.Horizontal.TProgressbar", troughcolor="#26313b", background=colors["accent"], bordercolor="#26313b", lightcolor=colors["accent"], darkcolor=colors["accent"], thickness=10)

        root = ttk.Frame(self, style="App.TFrame", padding=(30, 26, 30, 24))
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root, style="App.TFrame")
        header.pack(fill="x", pady=(0, 22))
        ttk.Label(header, text="Pyxils Open", style="Header.TLabel").pack(anchor="w")
        ttk.Label(header, text="A focused, resilient downloader for your desktop", style="Subtitle.TLabel").pack(anchor="w", pady=(4, 0))

        card = ttk.Frame(root, style="Card.TFrame", padding=22)
        card.pack(fill="x")
        ttk.Label(card, text="NEW DOWNLOAD", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 18))
        ttk.Label(card, text="URL", style="Field.TLabel").grid(row=1, column=0, columnspan=3, sticky="w")
        self.url_entry = ttk.Entry(card, textvariable=self.url)
        self.url_entry.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 16))
        ttk.Label(card, text="DESTINATION", style="Field.TLabel").grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="CONNECTIONS", style="Field.TLabel").grid(row=3, column=2, sticky="w", padx=(18, 0))
        ttk.Entry(card, textvariable=self.destination).grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(card, text="Choose…", style="Secondary.TButton", command=self.choose).grid(row=4, column=1, sticky="w", padx=(10, 0))
        ttk.Combobox(card, textvariable=self.connections, values=("1 connection", "4 connections", "8 connections", "16 connections"), state="readonly", width=16).grid(row=4, column=2, sticky="ew", padx=(18, 0))
        card.columnconfigure(0, weight=1)
        card.columnconfigure(2, weight=1)

        actions = ttk.Frame(root, style="App.TFrame")
        actions.pack(fill="x", pady=(16, 0))
        self.probe_button = ttk.Button(actions, text="Probe URL", style="Secondary.TButton", command=self.probe)
        self.probe_button.pack(side="left")
        self.download_button = ttk.Button(actions, text="↓  Download", style="Accent.TButton", command=self.start)
        self.download_button.pack(side="right")
        self.pause_button = ttk.Button(actions, text="Pause", style="Secondary.TButton", command=self.manager.pause, state="disabled")
        self.pause_button.pack(side="right", padx=(0, 10))
        self.cancel_button = ttk.Button(actions, text="Cancel", style="Danger.TButton", command=self.manager.cancel, state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 10))

        status_card = ttk.Frame(root, style="Card.TFrame", padding=18)
        status_card.pack(fill="x", pady=(22, 0))
        status_line = ttk.Frame(status_card, style="Card.TFrame")
        status_line.pack(fill="x")
        ttk.Label(status_line, text="STATUS", style="Field.TLabel").pack(side="left")
        ttk.Label(status_line, textvariable=self.status, style="Status.TLabel").pack(side="right")
        ttk.Progressbar(status_card, variable=self.progress, maximum=100, style="Dark.Horizontal.TProgressbar").pack(fill="x", pady=(14, 10))
        ttk.Label(status_card, textvariable=self.status_detail, style="Detail.TLabel", wraplength=720).pack(anchor="w")

        info = ttk.Frame(root, style="Card.TFrame", padding=(18, 14))
        info.pack(fill="x", pady=(14, 0))
        ttk.Label(info, text="ABOUT THIS DOWNLOAD", style="Field.TLabel").pack(anchor="w")
        ttk.Label(info, text="Probe checks server support before transfer. Downloads can be paused, cancelled, and resumed with the same destination.", style="Body.TLabel", wraplength=720).pack(anchor="w", pady=(6, 0))
        self.url_entry.focus_set()

    def choose(self) -> None:
        chosen = filedialog.asksaveasfilename()
        if chosen:
            self.destination.set(chosen)

    def probe(self) -> None:
        try:
            if "mega.nz/file/" in self.url.get() and "#" in self.url.get():
                mega_file = fetch_file(self.url.get().strip())
                self.status.set("MEGA link ready")
                self.status_detail.set(f"{mega_file.name} · {format_bytes(mega_file.size)} · encrypted public file")
                return
            result = self.manager.probe(self.url.get().strip())
            length = format_bytes(result.content_length) if result.content_length is not None else "unknown size"
            self.status.set("URL ready")
            self.status_detail.set(f"HTTP {result.status} · {length} · range requests: {'supported' if result.accepts_ranges else 'not advertised'}")
        except Exception as exc:
            self.status.set("Probe failed")
            self.status_detail.set(str(exc))
            messagebox.showerror("Probe failed", str(exc))

    def start(self) -> None:
        self.manager.reset()
        url = self.url.get().strip()
        destination = self.destination.get().strip()
        if not url or not destination:
            self.status.set("URL and destination required")
            self.status_detail.set("Enter a URL and choose where to save the file.")
            return
        self._running = True
        self._set_running_state(True)
        self.progress.set(0)
        self.status.set("Starting…")
        self.status_detail.set("Connecting to server")
        connections = int(self.connections.get().split()[0])
        threading.Thread(target=self._download, args=(url, destination, connections), daemon=True).start()

    def _download(self, url: str, destination: str, connections: int) -> None:
        def update(value: Progress) -> None:
            percent = value.downloaded / value.total * 100 if value.total else 0
            self.after(0, self.progress.set, percent)
            self.after(0, self.status.set, f"{percent:.0f}% complete")
            self.after(0, self.status_detail.set, f"{format_bytes(value.downloaded)} · {format_bytes(value.speed_bytes_per_second)}/s · ETA {format_duration(value.eta_seconds)}")
        try:
            path = self.manager.download(url, destination, update, connections=max(1, connections))
            self.after(0, self._finished, f"Complete: {path}", "Download saved successfully")
        except DownloadPaused:
            self.after(0, self._finished, "Paused", "Click Download to resume from the existing file")
        except DownloadCancelled:
            self.after(0, self._finished, "Cancelled", "Partial file retained so it can be resumed")
        except Exception as exc:
            self.after(0, self._finished, "Download failed", str(exc))
            self.after(0, messagebox.showerror, "Download failed", str(exc))

    def _set_running_state(self, running: bool) -> None:
        self.download_button.configure(state="disabled" if running else "normal")
        self.probe_button.configure(state="disabled" if running else "normal")
        self.pause_button.configure(state="normal" if running else "disabled")
        self.cancel_button.configure(state="normal" if running else "disabled")

    def _finished(self, status: str, detail: str) -> None:
        self._running = False
        self._set_running_state(False)
        self.status.set(status)
        self.status_detail.set(detail)


def main() -> None:
    App().mainloop()
