import io
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pyxils_open.core import DownloadCancelled, DownloadManager, DownloadPaused, format_bytes, format_duration
from pyxils_open.persistence import load_metadata, metadata_path


class Handler(BaseHTTPRequestHandler):
    payload = b"pyxils-open-test-data" * 500

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        start = 0
        if self.headers.get("Range", "").startswith("bytes="):
            start = int(self.headers["Range"].split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(self.payload)-1}/{len(self.payload)}")
        else:
            self.send_response(200)
        body = self.payload[start:]
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/file.bin"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()

    def test_formatters(self):
        self.assertEqual(format_bytes(512), "512 B")
        self.assertEqual(format_bytes(2048), "2.0 KB")
        self.assertEqual(format_duration(65), "1m 05s")

    def test_probe_and_download_persist_cleanup(self):
        manager = DownloadManager(chunk_size=17)
        result = manager.probe(self.url)
        self.assertEqual(result.content_length, len(Handler.payload))
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "file.bin"
            updates = []
            manager.download(self.url, destination, updates.append)
            self.assertEqual(destination.read_bytes(), Handler.payload)
            self.assertGreater(len(updates), 1)
            self.assertIsNone(load_metadata(destination))

    def test_resume_from_partial_file(self):
        manager = DownloadManager(chunk_size=31)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "file.bin"
            destination.write_bytes(Handler.payload[:25])
            manager.download(self.url, destination)
            self.assertEqual(destination.read_bytes(), Handler.payload)
            self.assertFalse(metadata_path(destination).exists())

    def test_pause_and_cancel_leave_resumable_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            paused_path = Path(tmp) / "paused.bin"
            paused = DownloadManager(chunk_size=11)

            def pause_after_first(progress):
                paused.pause()

            with self.assertRaises(DownloadPaused):
                paused.download(self.url, paused_path, pause_after_first)
            self.assertIsNotNone(load_metadata(paused_path))

            cancelled_path = Path(tmp) / "cancelled.bin"
            cancelled = DownloadManager(chunk_size=11)

            def cancel_after_first(progress):
                cancelled.cancel()

            with self.assertRaises(DownloadCancelled):
                cancelled.download(self.url, cancelled_path, cancel_after_first)
            self.assertIsNotNone(load_metadata(cancelled_path))


if __name__ == "__main__":
    unittest.main()
