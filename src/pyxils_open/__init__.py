"""Clean-room download manager MVP."""

__version__ = "0.1.0"

from .core import DownloadCancelled, DownloadManager, DownloadPaused, ProbeResult

__all__ = ["DownloadCancelled", "DownloadManager", "DownloadPaused", "ProbeResult"]
