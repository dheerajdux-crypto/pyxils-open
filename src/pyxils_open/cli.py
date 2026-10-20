"""Tkinter application entry point.

The UI intentionally stays within Tkinter/ttk so the desktop app remains easy
to package and run on a clean Python installation.  Download behavior lives in
``core`` and ``mega``; this module only coordinates the presentation layer.
"""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .core import DownloadCancelled, DownloadManager, DownloadPaused, Progress, format_bytes, format_duration
from .mega import fetch_file, fetch_folder, is_public_folder_link


class App(tk.Tk):
    """Dark, single-window Pyxils desktop shell."""

    COLORS = {
        "window": "#171312",
        "rail": "#211a18",
        "sidebar": "#2a211f",
        "surface": "#332723",
        "surface_alt": "#3b2d28",
        "field": "#241c1a",
        "border": "#4a3932",
        "text": "#f6eee9",
        "muted": "#ad9990",
        "faint": "#806f68",
        "accent": "#f47b3a",
        "accent_hover": "#ff9250",
        "accent_dark": "#6b321e",
        "success": "#8fd4a9",
        "danger": "#ef9a8b",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("Pyxils Open")
        self.geometry("1100x700")
        self.minsize(900, 620)
        self.configure(bg=self.COLORS["window"])

        self.manager = DownloadManager()
        self.url = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / "Downloads" / "download.bin"))
        self.connections = tk.StringVar(value="4 connections")
        self.status = tk.StringVar(value="Ready for a download")
        self.status_detail = tk.StringVar(value="Paste a URL to get started")
        self.progress = tk.DoubleVar()
        self._running = False
        self._page = "downloads"
        self._nav_buttons: dict[str, tk.Button] = {}
        self._settings_buttons: dict[str, tk.Button] = {}
        self._content: tk.Frame | None = None
        self._build_styles()
        self._build_shell()
        self.show_page("downloads")

    def _build_styles(self) -> None:
        c = self.COLORS
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background=c["window"])
        style.configure("Sidebar.TFrame", background=c["sidebar"])
        style.configure("Card.TFrame", background=c["surface"])
        style.configure("Inner.TFrame", background=c["surface_alt"])
        style.configure("Title.TLabel", background=c["window"], foreground=c["text"], font=("TkDefaultFont", 22, "bold"))
        style.configure("Subtitle.TLabel", background=c["window"], foreground=c["muted"], font=("TkDefaultFont", 10))
        style.configure("CardTitle.TLabel", background=c["surface"], foreground=c["text"], font=("TkDefaultFont", 11, "bold"))
        style.configure("CardBody.TLabel", background=c["surface"], foreground=c["muted"], font=("TkDefaultFont", 9))
        style.configure("PanelTitle.TLabel", background=c["surface_alt"], foreground=c["text"], font=("TkDefaultFont", 10, "bold"))
        style.configure("PanelBody.TLabel", background=c["surface_alt"], foreground=c["muted"], font=("TkDefaultFont", 9))
        style.configure("Field.TLabel", background=c["surface"], foreground=c["muted"], font=("TkDefaultFont", 8, "bold"))
        style.configure("Status.TLabel", background=c["surface_alt"], foreground=c["text"], font=("TkDefaultFont", 10, "bold"))
        style.configure("Detail.TLabel", background=c["surface_alt"], foreground=c["muted"], font=("TkDefaultFont", 9))
        style.configure("TEntry", fieldbackground=c["field"], foreground=c["text"], insertcolor=c["text"], bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"], padding=9)
        style.map("TEntry", bordercolor=[("focus", c["accent"])])
        style.configure("TCombobox", fieldbackground=c["field"], background=c["field"], foreground=c["text"], arrowcolor=c["muted"], bordercolor=c["border"], padding=7)
        style.configure("Treeview", background=c["surface_alt"], fieldbackground=c["surface_alt"], foreground=c["muted"], bordercolor=c["border"], rowheight=28)
        style.configure("Treeview.Heading", background=c["surface"], foreground=c["muted"], bordercolor=c["border"], font=("TkDefaultFont", 8, "bold"))
        style.map("Treeview", background=[("selected", c["accent_dark"])], foreground=[("selected", c["text"])])
        style.configure("Dark.Horizontal.TProgressbar", troughcolor=c["field"], background=c["accent"], bordercolor=c["field"], lightcolor=c["accent"], darkcolor=c["accent"], thickness=9)

    def _build_shell(self) -> None:
        c = self.COLORS
        shell = tk.Frame(self, bg=c["window"])
        shell.pack(fill="both", expand=True)
        self.rail = tk.Frame(shell, bg=c["rail"], width=68)
        self.rail.pack(side="left", fill="y")
        self.rail.pack_propagate(False)
        tk.Label(self.rail, text="P", bg=c["accent"], fg="#25120b", font=("TkDefaultFont", 17, "bold"), width=2, height=1).pack(pady=(20, 26))
        self._rail_button("⌂", "downloads", "Downloads").pack(pady=4)
        self._rail_button("↗", "downloads", "New download").pack(pady=4)
        tk.Frame(self.rail, bg=c["rail"]).pack(fill="both", expand=True)
        self._rail_button("⚙", "settings", "Settings").pack(pady=(4, 18))

        self.sidebar = tk.Frame(shell, bg=c["sidebar"], width=206)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_workspace_sidebar()
        self.workspace = tk.Frame(shell, bg=c["window"])
        self.workspace.pack(side="left", fill="both", expand=True)

    def _rail_button(self, glyph: str, page: str, tooltip: str) -> tk.Button:
        button = tk.Button(self.rail, text=glyph, command=lambda: self.show_page(page), bg=self.COLORS["rail"], fg=self.COLORS["muted"], activebackground=self.COLORS["surface"], activeforeground=self.COLORS["text"], relief="flat", borderwidth=0, font=("TkDefaultFont", 17), width=3, cursor="hand2")
        return button

    def _build_workspace_sidebar(self) -> None:
        c = self.COLORS
        tk.Label(self.sidebar, text="PYXILS OPEN", bg=c["sidebar"], fg=c["faint"], font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=22, pady=(25, 27))
        tk.Label(self.sidebar, text="WORKSPACE", bg=c["sidebar"], fg=c["faint"], font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=22, pady=(0, 8))
        self._sidebar_button("downloads", "▣  Downloads").pack(fill="x", padx=12)
        self._sidebar_button("completed", "✓  Completed").pack(fill="x", padx=12)
        self._sidebar_button("favorites", "☆  Favorites").pack(fill="x", padx=12)

    def _sidebar_button(self, page: str, text: str) -> tk.Button:
        button = tk.Button(self.sidebar, text=text, anchor="w", command=lambda: self.show_page(page), bg=self.COLORS["sidebar"], fg=self.COLORS["muted"], activebackground=self.COLORS["surface"], activeforeground=self.COLORS["text"], relief="flat", borderwidth=0, padx=12, pady=9, font=("TkDefaultFont", 10), cursor="hand2")
        self._nav_buttons[page] = button
        return button

    def show_page(self, page: str) -> None:
        self._page = page
        if self._content is not None:
            self._content.destroy()
        for name, button in self._nav_buttons.items():
            button.configure(bg=self.COLORS["surface"] if name == page else self.COLORS["sidebar"], fg=self.COLORS["text"] if name == page else self.COLORS["muted"])
        self._content = tk.Frame(self.workspace, bg=self.COLORS["window"])
        self._content.pack(fill="both", expand=True)
        if page == "settings":
            self._build_settings(self._content)
        else:
            self._build_downloads(self._content, page)

    def _build_topbar(self, parent: tk.Frame, title: str, subtitle: str) -> tk.Frame:
        c = self.COLORS
        top = tk.Frame(parent, bg=c["window"])
        top.pack(fill="x", padx=34, pady=(22, 18))
        title_box = tk.Frame(top, bg=c["window"])
        title_box.pack(side="left")
        tk.Label(title_box, text=title, bg=c["window"], fg=c["text"], font=("TkDefaultFont", 21, "bold")).pack(anchor="w")
        tk.Label(title_box, text=subtitle, bg=c["window"], fg=c["muted"], font=("TkDefaultFont", 9)).pack(anchor="w", pady=(3, 0))
        actions = tk.Frame(top, bg=c["window"])
        actions.pack(side="right", fill="y")
        search = tk.Entry(actions, bg=c["field"], fg=c["muted"], insertbackground=c["text"], relief="flat", highlightthickness=1, highlightbackground=c["border"], highlightcolor=c["accent"], width=24)
        search.insert(0, "⌕  Search downloads")
        search.pack(side="left", ipady=7, padx=(0, 10))
        tk.Button(actions, text="＋  New link", command=self._focus_url, bg=c["accent"], fg="#2a130a", activebackground=c["accent_hover"], relief="flat", borderwidth=0, padx=13, pady=8, font=("TkDefaultFont", 9, "bold"), cursor="hand2").pack(side="left")
        tk.Button(actions, text="▣  Open MEGA folder", command=self._open_mega_folder, bg=c["surface_alt"], fg=c["text"], activebackground=c["border"], relief="flat", borderwidth=0, padx=13, pady=8, font=("TkDefaultFont", 9, "bold"), cursor="hand2").pack(side="left", padx=(8, 0))
        return top

    def _build_downloads(self, parent: tk.Frame, page: str) -> None:
        self._build_topbar(parent, "Downloads" if page == "downloads" else page.title(), "Keep every transfer close at hand")
        body = tk.Frame(parent, bg=self.COLORS["window"])
        body.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        empty = tk.Frame(body, bg=self.COLORS["surface"])
        empty.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        tk.Label(empty, text="◌", bg=self.COLORS["surface"], fg=self.COLORS["accent"], font=("TkDefaultFont", 29)).pack(side="left", padx=(22, 14), pady=16)
        copy = tk.Frame(empty, bg=self.COLORS["surface"])
        copy.pack(side="left", pady=13)
        tk.Label(copy, text="Your download shelf is clear", bg=self.COLORS["surface"], fg=self.COLORS["text"], font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        tk.Label(copy, text="Paste a link above or add one below to get started.", bg=self.COLORS["surface"], fg=self.COLORS["muted"], font=("TkDefaultFont", 9)).pack(anchor="w", pady=(3, 0))

        form = tk.Frame(body, bg=self.COLORS["surface"], padx=20, pady=17)
        form.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        self._build_download_form(form)
        right = tk.Frame(body, bg=self.COLORS["window"])
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        self._build_folder_card(right)
        self._build_status_card(right)

    def _build_download_form(self, card: tk.Frame) -> None:
        c = self.COLORS
        tk.Label(card, text="NEW DOWNLOAD", bg=c["surface"], fg=c["text"], font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        tk.Label(card, text="URL", bg=c["surface"], fg=c["muted"], font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(20, 6))
        self.url_entry = ttk.Entry(card, textvariable=self.url)
        self.url_entry.pack(fill="x")
        row = tk.Frame(card, bg=c["surface"])
        row.pack(fill="x", pady=(15, 0))
        left = tk.Frame(row, bg=c["surface"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="DESTINATION", bg=c["surface"], fg=c["muted"], font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(0, 6))
        destination_row = tk.Frame(left, bg=c["surface"])
        destination_row.pack(fill="x")
        ttk.Entry(destination_row, textvariable=self.destination).pack(side="left", fill="x", expand=True)
        tk.Button(destination_row, text="Choose", command=self.choose, bg=c["surface_alt"], fg=c["text"], activebackground=c["border"], relief="flat", borderwidth=0, padx=10, pady=7, cursor="hand2").pack(side="left", padx=(7, 0))
        conn = tk.Frame(row, bg=c["surface"])
        conn.pack(side="left", padx=(14, 0))
        tk.Label(conn, text="CONNECTIONS", bg=c["surface"], fg=c["muted"], font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Combobox(conn, textvariable=self.connections, values=("1 connection", "4 connections", "8 connections", "16 connections"), state="readonly", width=15).pack()
        actions = tk.Frame(card, bg=c["surface"])
        actions.pack(fill="x", pady=(21, 0))
        self.probe_button = tk.Button(actions, text="Probe URL", command=self.probe, bg=c["surface_alt"], fg=c["text"], activebackground=c["border"], relief="flat", borderwidth=0, padx=13, pady=9, cursor="hand2")
        self.probe_button.pack(side="left")
        self.download_button = tk.Button(actions, text="↓  Download", command=self.start, bg=c["accent"], fg="#2a130a", activebackground=c["accent_hover"], relief="flat", borderwidth=0, padx=18, pady=9, font=("TkDefaultFont", 9, "bold"), cursor="hand2")
        self.download_button.pack(side="right")
        self.pause_button = tk.Button(actions, text="Pause", command=self.manager.pause, state="disabled", bg=c["surface_alt"], fg=c["muted"], activebackground=c["border"], relief="flat", borderwidth=0, padx=11, pady=9)
        self.pause_button.pack(side="right", padx=(0, 7))
        self.cancel_button = tk.Button(actions, text="Cancel", command=self.manager.cancel, state="disabled", bg=c["surface_alt"], fg=c["danger"], activebackground=c["border"], relief="flat", borderwidth=0, padx=11, pady=9)
        self.cancel_button.pack(side="right", padx=(0, 7))
        tk.Label(card, text="Supports HTTP links and public MEGA file/folder links.", bg=c["surface"], fg=c["faint"], font=("TkDefaultFont", 8)).pack(anchor="w", pady=(18, 0))
        self.url_entry.focus_set()

    def _build_folder_card(self, parent: tk.Frame) -> None:
        c = self.COLORS
        card = tk.Frame(parent, bg=c["surface"], padx=14, pady=12)
        card.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        tk.Label(card, text="FOLDER CONTENTS", bg=c["surface"], fg=c["muted"], font=("TkDefaultFont", 8, "bold")).pack(anchor="w")
        list_frame = tk.Frame(card, bg=c["surface"])
        list_frame.pack(fill="both", expand=True, pady=(7, 0))
        self.folder_empty = tk.Frame(list_frame, bg=c["surface_alt"], padx=12, pady=20)
        self.folder_empty.pack(fill="both", expand=True)
        tk.Label(self.folder_empty, text="▱", bg=c["surface_alt"], fg=c["accent"], font=("TkDefaultFont", 34)).pack()
        self.folder_empty_title = tk.Label(self.folder_empty, text="No MEGA folder loaded", bg=c["surface_alt"], fg=c["text"], font=("TkDefaultFont", 10, "bold"))
        self.folder_empty_title.pack(pady=(3, 3))
        self.folder_empty_detail = tk.Label(self.folder_empty, text="Enter a public folder URL, then click Probe URL.", bg=c["surface_alt"], fg=c["muted"], font=("TkDefaultFont", 8), wraplength=280, justify="center")
        self.folder_empty_detail.pack()
        self.folder_tree = ttk.Treeview(list_frame, columns=("name", "size"), show="headings", height=5)
        self.folder_tree.heading("name", text="Name", anchor="w")
        self.folder_tree.heading("size", text="Size", anchor="e")
        self.folder_tree.column("name", anchor="w", width=270, stretch=True)
        self.folder_tree.column("size", anchor="e", width=75, stretch=False)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.folder_tree.yview)
        self.folder_tree.configure(yscrollcommand=scroll.set)
        self.folder_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._clear_folder_files()

    def _build_status_card(self, parent: tk.Frame) -> None:
        c = self.COLORS
        card = tk.Frame(parent, bg=c["surface_alt"], padx=15, pady=13)
        card.grid(row=1, column=0, sticky="nsew")
        line = tk.Frame(card, bg=c["surface_alt"])
        line.pack(fill="x")
        tk.Label(line, text="TRANSFER STATUS", bg=c["surface_alt"], fg=c["muted"], font=("TkDefaultFont", 8, "bold")).pack(side="left")
        tk.Label(line, textvariable=self.status, bg=c["surface_alt"], fg=c["text"], font=("TkDefaultFont", 9, "bold")).pack(side="right")
        ttk.Progressbar(card, variable=self.progress, maximum=100, style="Dark.Horizontal.TProgressbar").pack(fill="x", pady=(13, 9))
        tk.Label(card, textvariable=self.status_detail, bg=c["surface_alt"], fg=c["muted"], font=("TkDefaultFont", 8), wraplength=350, justify="left").pack(anchor="w")

    def _build_settings(self, parent: tk.Frame) -> None:
        c = self.COLORS
        self._build_topbar(parent, "Settings", "Make Pyxils Open feel like yours")
        body = tk.Frame(parent, bg=c["window"])
        body.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        nav = tk.Frame(body, bg=c["surface"], width=190, padx=10, pady=14)
        nav.pack(side="left", fill="y", padx=(0, 16))
        nav.pack_propagate(False)
        tk.Label(nav, text="PREFERENCES", bg=c["surface"], fg=c["faint"], font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=8, pady=(2, 9))
        for name, label in (("general", "General"), ("downloads", "Downloads"), ("screenshot", "Screenshot")):
            button = tk.Button(nav, text=label, anchor="w", command=lambda key=name: self._show_settings_panel(panel, key), bg=c["surface"], fg=c["muted"], activebackground=c["surface_alt"], activeforeground=c["text"], relief="flat", borderwidth=0, padx=10, pady=9, font=("TkDefaultFont", 9), cursor="hand2")
            button.pack(fill="x", pady=1)
            self._settings_buttons[name] = button
        panel = tk.Frame(body, bg=c["surface_alt"], padx=24, pady=22)
        panel.pack(side="left", fill="both", expand=True)
        self._show_settings_panel(panel, "general")

    def _show_settings_panel(self, panel: tk.Frame, key: str) -> None:
        for child in panel.winfo_children():
            child.destroy()
        c = self.COLORS
        for name, button in self._settings_buttons.items():
            button.configure(bg=c["accent_dark"] if name == key else c["surface"], fg=c["text"] if name == key else c["muted"])
        headings = {
            "general": ("General", "A few simple defaults for your workspace."),
            "downloads": ("Downloads", "Choose how new transfers should behave."),
            "screenshot": ("Screenshot", "Preview the visual language used by this shell."),
        }
        title, subtitle = headings[key]
        tk.Label(panel, text=title, bg=c["surface_alt"], fg=c["text"], font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        tk.Label(panel, text=subtitle, bg=c["surface_alt"], fg=c["muted"], font=("TkDefaultFont", 9)).pack(anchor="w", pady=(4, 22))
        if key == "screenshot":
            preview = tk.Frame(panel, bg=c["window"], padx=16, pady=16)
            preview.pack(fill="x", pady=(4, 15))
            tk.Label(preview, text="Pyxils Open", bg=c["window"], fg=c["text"], font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
            tk.Label(preview, text="Dark brown surfaces · orange actions · quiet empty states", bg=c["window"], fg=c["muted"], font=("TkDefaultFont", 9)).pack(anchor="w", pady=(7, 10))
            tk.Frame(preview, bg=c["accent"], height=4).pack(fill="x")
            tk.Label(panel, text="The interface uses standard Tkinter widgets so it stays portable and accessible across desktop platforms.", bg=c["surface_alt"], fg=c["muted"], font=("TkDefaultFont", 9), wraplength=500, justify="left").pack(anchor="w")
            return
        rows = [("Open downloads folder on finish", "Automatically reveal completed files"), ("Keep window open", "Leave Pyxils available after a transfer")]
        if key == "downloads":
            rows = [("Default connections", "4 connections"), ("Resume partial files", "Enabled"), ("Confirm before cancel", "Enabled")]
        for label, detail in rows:
            item = tk.Frame(panel, bg=c["surface"], padx=14, pady=12)
            item.pack(fill="x", pady=(0, 9))
            tk.Label(item, text=label, bg=c["surface"], fg=c["text"], font=("TkDefaultFont", 9, "bold")).pack(side="left")
            tk.Label(item, text=detail, bg=c["surface"], fg=c["muted"], font=("TkDefaultFont", 9)).pack(side="right")
        tk.Label(panel, text="Preferences are kept intentionally lightweight in this open-source build.", bg=c["surface_alt"], fg=c["faint"], font=("TkDefaultFont", 8)).pack(anchor="w", pady=(8, 0))

    def _focus_url(self) -> None:
        self.show_page("downloads")
        self.after(50, lambda: self.url_entry.focus_set())

    def _open_mega_folder(self) -> None:
        """Bring the public MEGA folder workflow into focus."""
        self.show_page("downloads")
        self.status.set("Ready for a MEGA folder")
        self.status_detail.set("Paste a public MEGA folder URL, then click Probe URL to browse its files.")
        self.after(50, self.url_entry.focus_set)

    def choose(self) -> None:
        if is_public_folder_link(self.url.get().strip()):
            chosen = filedialog.askdirectory(title="Choose folder for MEGA files")
        else:
            chosen = filedialog.asksaveasfilename()
        if chosen:
            self.destination.set(chosen)

    def _clear_folder_files(self) -> None:
        for item in self.folder_tree.get_children():
            self.folder_tree.delete(item)
        self.folder_tree.pack_forget()
        self.folder_empty_title.configure(text="No MEGA folder loaded")
        self.folder_empty_detail.configure(text="Enter a public folder URL, then click Probe URL.")
        self.folder_empty.pack(fill="both", expand=True)

    def _show_folder_files(self, files) -> None:
        for item in self.folder_tree.get_children():
            self.folder_tree.delete(item)
        if not files:
            self.folder_tree.pack_forget()
            self.folder_empty_title.configure(text="No downloadable files found")
            self.folder_empty_detail.configure(text="This public MEGA folder did not contain downloadable files.")
            self.folder_empty.pack(fill="both", expand=True)
            return
        self.folder_empty.pack_forget()
        self.folder_tree.pack(side="left", fill="both", expand=True)
        for mega_file in files:
            self.folder_tree.insert("", "end", values=(mega_file.name, format_bytes(mega_file.size)))

    def probe(self) -> None:
        try:
            self._clear_folder_files()
            if "mega.nz/file/" in self.url.get() and "#" in self.url.get():
                mega_file = fetch_file(self.url.get().strip())
                self.status.set("MEGA link ready")
                self.status_detail.set(f"{mega_file.name} · {format_bytes(mega_file.size)} · encrypted public file")
                return
            if is_public_folder_link(self.url.get().strip()):
                files = fetch_folder(self.url.get().strip())
                self._show_folder_files(files)
                self.status.set("MEGA folder ready")
                self.status_detail.set(f"{len(files)} downloadable file(s) · choose a destination folder")
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
