#!/usr/bin/env python3
"""
FileCompressor Local Web Server
Provides a clean, lightweight web interface for compressing files and folders.
Zero external dependencies - built using Python's standard library.
"""

import cgi
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Dict, Any, List

# Ensure local core package and .venv packages are importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

_venv_lib = os.path.join(BASE_DIR, ".venv", "lib")
if os.path.isdir(_venv_lib):
    for _d in os.listdir(_venv_lib):
        _sp = os.path.join(_venv_lib, _d, "site-packages")
        if os.path.isdir(_sp) and _sp not in sys.path:
            sys.path.insert(0, _sp)

from core.compressor import compress, get_path_size, format_bytes, get_default_extension
from core.video_downloader import extract_media_info, download_media

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# In-memory history for current server session
COMPRESSION_HISTORY: List[Dict[str, Any]] = []


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class CompressorRequestHandler(BaseHTTPRequestHandler):
    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: int = 400):
        self.send_json({"success": False, "error": message}, status=status)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static assets
        if path == "/" or path == "/index.html":
            self.serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return

        if path == "/favicon.ico":
            self.serve_file(os.path.join(STATIC_DIR, "favicon.ico"), "image/x-icon")
            return

        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            safe_path = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
            if safe_path.startswith(STATIC_DIR) and os.path.isfile(safe_path):
                mime, _ = mimetypes.guess_type(safe_path)
                self.serve_file(safe_path, mime or "application/octet-stream")
                return
            self.send_error(404, "File not found")
            return

        # API Endpoints
        if path == "/api/info":
            home = os.path.expanduser("~")
            self.send_json({
                "platform": sys.platform,
                "home_dir": home,
                "desktop_dir": os.path.join(home, "Desktop"),
                "downloads_dir": os.path.join(home, "Downloads"),
                "documents_dir": os.path.join(home, "Documents"),
                "current_dir": os.getcwd(),
                "supported_formats": [
                    {"id": "zip", "name": "ZIP (.zip)", "desc": "Universal compatibility across all OS"},
                    {"id": "tar.gz", "name": "Tar Gzip (.tar.gz)", "desc": "Standard Linux/macOS compressed tarball"},
                    {"id": "tar.bz2", "name": "Tar Bzip2 (.tar.bz2)", "desc": "Higher compression ratio for text & code"},
                    {"id": "tar.xz", "name": "Tar XZ (.tar.xz)", "desc": "Maximum compression for large files"},
                    {"id": "dmg", "name": "Apple Disk Image (.dmg)", "desc": "macOS read-only compressed UDZO image"},
                ]
            })
            return

        if path == "/api/history":
            self.send_json({"history": COMPRESSION_HISTORY})
            return

        if path == "/api/download":
            target_path = query.get("path", [""])[0]
            if not target_path or not os.path.exists(target_path):
                self.send_error_json("File not found for download", 404)
                return

            filename = os.path.basename(target_path)
            file_size = os.path.getsize(target_path)
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(file_size))
            self.end_headers()

            with open(target_path, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        if path == "/api/video/download-browser":
            import importlib, core.video_downloader
            importlib.reload(core.video_downloader)
            from core.video_downloader import download_media
            url = query.get("url", [""])[0]
            target_ext = query.get("target_ext", ["mp4"])[0]
            res_val = query.get("resolution", [None])[0]
            resolution = int(res_val) if (res_val and res_val.isdigit()) else None

            if not url:
                self.send_error_json("Missing video URL", 400)
                return

            temp_dir = tempfile.mkdtemp(prefix="browser_vdl_")
            try:
                dl_res = download_media(
                    url=url,
                    output_dir=temp_dir,
                    target_ext=target_ext,
                    resolution=resolution
                )
                if not dl_res.get("success"):
                    self.send_error_json(dl_res.get("error", "Download failed"), 500)
                    return

                file_path = dl_res["output_path"]
                file_size = dl_res["size_bytes"]
                filename = dl_res["filename"]

                self.send_response(200)
                mime, _ = mimetypes.guess_type(file_path)
                self.send_header("Content-Type", mime or "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(file_size))
                self.end_headers()

                with open(file_path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
            except Exception as e:
                self.send_error_json(f"Download error: {e}", 500)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/browse":
            data = self.read_json_body()
            browse_type = data.get("type", "folder")  # 'file', 'folder'
            prompt = data.get("prompt", "Select item")

            chosen_path = self.run_macos_picker(browse_type, prompt)
            if chosen_path:
                size_bytes = get_path_size(chosen_path)
                self.send_json({
                    "success": True,
                    "path": chosen_path,
                    "name": os.path.basename(chosen_path.rstrip(os.sep)),
                    "is_dir": os.path.isdir(chosen_path),
                    "size_bytes": size_bytes,
                    "size_formatted": format_bytes(size_bytes),
                })
            else:
                self.send_json({"success": False, "cancelled": True})
            return

        if path == "/api/path-check":
            data = self.read_json_body()
            target_path = data.get("path", "").strip()
            if not target_path:
                self.send_json({"exists": False})
                return

            full_path = os.path.abspath(os.path.expanduser(target_path))
            if os.path.exists(full_path):
                size_bytes = get_path_size(full_path)
                self.send_json({
                    "exists": True,
                    "path": full_path,
                    "name": os.path.basename(full_path.rstrip(os.sep)),
                    "is_dir": os.path.isdir(full_path),
                    "size_bytes": size_bytes,
                    "size_formatted": format_bytes(size_bytes),
                })
            else:
                self.send_json({"exists": False, "path": full_path})
            return

        if path == "/api/compress":
            import importlib
            import core.compressor
            importlib.reload(core.compressor)
            from core.compressor import compress

            data = self.read_json_body()
            source = data.get("source", "").strip()
            output = data.get("output", "").strip() or None
            fmt = data.get("format", "zip")
            relative = bool(data.get("relative", True))
            overwrite = bool(data.get("overwrite", True))
            max_compression = bool(data.get("max_compression", True))
            exclude_junk = bool(data.get("exclude_junk", False))
            optimize_media = bool(data.get("optimize_media", False))
            target_size_mb = data.get("target_size_mb")
            if target_size_mb is not None:
                try:
                    target_size_mb = float(target_size_mb)
                except (ValueError, TypeError):
                    target_size_mb = None
            split_if_exceeds = bool(data.get("split_if_exceeds", True))

            if not source:
                self.send_error_json("Source path is required", 400)
                return

            res = compress(
                source=source,
                output=output,
                fmt=fmt,
                relative=relative,
                overwrite=overwrite,
                max_compression=max_compression,
                exclude_junk=exclude_junk,
                target_size_mb=target_size_mb,
                split_if_exceeds=split_if_exceeds,
                optimize_media=optimize_media,
            )

            if res.get("success"):
                COMPRESSION_HISTORY.insert(0, res)
                # Keep max 50 history entries
                if len(COMPRESSION_HISTORY) > 50:
                    COMPRESSION_HISTORY.pop()

            self.send_json(res)
            return

        if path == "/api/split-file":
            import importlib
            import core.compressor
            importlib.reload(core.compressor)
            from core.compressor import split_file, strip_known_extension, get_default_extension
            data = self.read_json_body()
            target_path = data.get("path", "").strip()
            chunk_mb = float(data.get("chunk_mb", 24.5))

            if not target_path or not os.path.exists(target_path):
                self.send_error_json("Target file does not exist", 404)
                return

            fmt = "zip"
            for k in ["tar.gz", "tar.bz2", "tar.xz", "zip", "dmg"]:
                if target_path.lower().endswith(k):
                    fmt = k
                    break

            max_bytes = int(chunk_mb * 1024 * 1024)
            parts = split_file(target_path, max_bytes, fmt=fmt)
            parts_info = []
            for p in parts:
                sz = os.path.getsize(p)
                parts_info.append({
                    "path": p,
                    "filename": os.path.basename(p),
                    "size_bytes": sz,
                    "size_formatted": format_bytes(sz),
                })
            base_clean = os.path.basename(strip_known_extension(target_path))
            ext = get_default_extension(fmt)
            self.send_json({
                "success": True,
                "parts": parts_info,
                "join_command": f'cat "{base_clean}_part"*{ext} > "{base_clean}{ext}"',
            })
            return

        if path == "/api/open-folder":
            data = self.read_json_body()
            target_path = data.get("path", "").strip()
            if not target_path or not os.path.exists(target_path):
                self.send_error_json("Target path does not exist", 404)
                return

            try:
                if sys.platform == "darwin":
                    # Reveal file in Finder
                    subprocess.run(["open", "-R", target_path], check=True)
                else:
                    folder = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
                    subprocess.run(["open", folder], check=True)
                self.send_json({"success": True})
            except Exception as e:
                self.send_error_json(f"Failed to open in file manager: {e}", 500)
            return

        if path == "/api/video/info":
            import importlib, core.video_downloader
            importlib.reload(core.video_downloader)
            from core.video_downloader import extract_media_info
            data = self.read_json_body()
            url = data.get("url", "").strip()
            if not url:
                self.send_error_json("Video URL is required", 400)
                return

            res = extract_media_info(url)
            self.send_json(res)
            return

        if path == "/api/video/download":
            import importlib, core.video_downloader
            importlib.reload(core.video_downloader)
            from core.video_downloader import download_media
            data = self.read_json_body()
            url = data.get("url", "").strip()
            output_dir = data.get("output_dir", "").strip()
            target_ext = data.get("target_ext", "mp4").strip()
            res_val = data.get("resolution")
            custom_name = data.get("custom_name", "").strip() or None

            if not url:
                self.send_error_json("Video URL is required", 400)
                return

            if not output_dir:
                home = os.path.expanduser("~")
                output_dir = os.path.join(home, "Downloads")
                if not os.path.isdir(output_dir):
                    output_dir = os.path.join(home, "Desktop")

            resolution = None
            if res_val is not None:
                try:
                    resolution = int(res_val)
                except (ValueError, TypeError):
                    resolution = None

            try:
                res = download_media(
                    url=url,
                    output_dir=output_dir,
                    target_ext=target_ext,
                    resolution=resolution,
                    custom_name=custom_name,
                )
                self.send_json(res)
            except Exception as e:
                self.send_error_json(str(e), 500)
            return

        if path == "/api/upload-compress":
            self.handle_upload_compress()
            return

        self.send_error(404, "Endpoint not found")

    def read_json_body(self) -> Dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_data = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw_data)
        except Exception:
            pass
        return {}

    def run_macos_picker(self, picker_type: str, prompt: str) -> str:
        """Invoke native macOS AppleScript file/folder chooser."""
        if sys.platform != "darwin":
            return ""

        if picker_type == "file":
            script = f'POSIX path of (choose file with prompt "{prompt}")'
        else:
            script = f'POSIX path of (choose folder with prompt "{prompt}")'

        try:
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            if res.returncode == 0:
                return res.stdout.strip().rstrip(os.sep)
        except Exception:
            pass
        return ""

    def handle_upload_compress(self):
        """Handle browser multipart file upload and compress on the fly."""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error_json("Invalid content type, multipart/form-data required", 400)
            return

        temp_dir = tempfile.mkdtemp(prefix="upload_pack_")
        try:
            # cgi module parsing for multipart data
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type"),
                "CONTENT_LENGTH": self.headers.get("Content-Length"),
            }
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ=environ,
                keep_blank_values=True,
            )

            fmt = form.getvalue("format", "zip")
            files = form["files"] if "files" in form else None
            if not files:
                self.send_error_json("No files uploaded", 400)
                return

            if not isinstance(files, list):
                files = [files]

            upload_dir = os.path.join(temp_dir, "files")
            os.makedirs(upload_dir, exist_ok=True)

            archive_basename = "compressed_files"
            saved_count = 0

            for item in files:
                if item.filename:
                    # Sanitize filename
                    fname = os.path.basename(item.filename)
                    if not fname:
                        continue
                    if saved_count == 0:
                        archive_basename = os.path.splitext(fname)[0]
                    dest_file = os.path.join(upload_dir, fname)
                    with open(dest_file, "wb") as f_out:
                        shutil.copyfileobj(item.file, f_out)
                    saved_count += 1

            if saved_count == 0:
                self.send_error_json("Uploaded files were empty", 400)
                return

            # If only 1 file was uploaded, compress that single file directly
            if saved_count == 1:
                source_to_compress = os.path.join(upload_dir, os.listdir(upload_dir)[0])
            else:
                source_to_compress = upload_dir

            out_archive = os.path.join(temp_dir, f"{archive_basename}{get_default_extension(fmt)}")
            res = compress(
                source=source_to_compress,
                output=out_archive,
                fmt=fmt,
                relative=True,
                overwrite=True,
            )

            if not res.get("success"):
                self.send_error_json(res.get("error", "Compression failed"), 500)
                return

            final_file = res["output"]
            file_size = os.path.getsize(final_file)
            filename = os.path.basename(final_file)

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(file_size))
            self.send_header("X-Saved-Percentage", str(res.get("saved_percentage", 0)))
            self.send_header("X-Saved-Bytes", str(res.get("saved_bytes", 0)))
            self.end_headers()

            with open(final_file, "rb") as f:
                shutil.copyfileobj(f, self.wfile)

        except Exception as e:
            self.send_error_json(f"Upload error: {e}", 500)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def serve_file(self, file_path: str, content_type: str):
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def log_message(self, format, *args):
        # Clean logging
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def run_server(port: int = 8080, open_browser: bool = True):
    # Try preferred port, or increment if busy
    server = None
    for p in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), CompressorRequestHandler)
            port = p
            break
        except OSError:
            continue

    if not server:
        sys.exit("Error: Could not bind server to any local port in range 8080-8100.")

    url = f"http://127.0.0.1:{port}"
    print(f"\n==========================================")
    print(f"  FileCompressor Web UI is running!")
    print(f"  Local URL: {url}")
    print(f"  Press Ctrl+C to stop the server.")
    print(f"==========================================\n")

    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping FileCompressor server.")
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Start FileCompressor Web Interface")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind server (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    run_server(port=args.port, open_browser=not args.no_browser)
