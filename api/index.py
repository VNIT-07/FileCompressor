#!/usr/bin/env python3
"""
FileCompressor - Vercel Serverless Function API Entrypoint
Provides serverless endpoints for info, file upload compression, history, and video information.
Fully compatible with Vercel's Python Serverless Runtime.
"""

import cgi
import io
import json
import mimetypes
import os
import shutil
import sys
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, List

# Ensure core package is importable in Vercel's lambda container
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.compressor import compress, get_default_extension, format_bytes

try:
    from core.video_downloader import extract_media_info, download_media
except Exception:
    extract_media_info = None
    download_media = None

# In-memory history for serverless container session
SESSION_HISTORY: List[Dict[str, Any]] = []


class handler(BaseHTTPRequestHandler):
    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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

    def get_route_path(self):
        """Resolves the route path handling Vercel rewrites and query params."""
        raw_path = self.headers.get("x-matched-path") or self.path
        parsed = urllib.parse.urlparse(raw_path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Fallback if rewritten to /api/index.py
        if path.endswith("index.py") or path == "/api":
            sub_path = query.get("_path", [""])[0]
            if sub_path:
                path = f"/api/{sub_path.lstrip('/')}"
        return path, query

    def read_json_body(self) -> Dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_data = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw_data)
        except Exception:
            pass
        return {}

    def do_GET(self):
        path, query = self.get_route_path()

        if path == "/api/info":
            self.send_json({
                "platform": "vercel-cloud",
                "cloud_mode": True,
                "provider": "vercel",
                "home_dir": "/tmp",
                "desktop_dir": "/tmp",
                "downloads_dir": "/tmp",
                "documents_dir": "/tmp",
                "current_dir": "/var/task",
                "max_upload_size_mb": 4.5,
                "supported_formats": [
                    {"id": "zip", "name": "ZIP (.zip)", "desc": "Universal compatibility across all OS"},
                    {"id": "tar.gz", "name": "Tar Gzip (.tar.gz)", "desc": "Standard Linux/macOS compressed tarball"},
                    {"id": "tar.bz2", "name": "Tar Bzip2 (.tar.bz2)", "desc": "Higher compression ratio for text & code"},
                    {"id": "tar.xz", "name": "Tar XZ (.tar.xz)", "desc": "Maximum compression for large files"},
                ]
            })
            return

        if path == "/api/history":
            self.send_json({"history": SESSION_HISTORY})
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
            if not download_media:
                self.send_error_json("Video downloader module not available in cloud environment", 500)
                return

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

        self.send_error(404, f"Endpoint not found: {path}")

    def do_POST(self):
        path, _ = self.get_route_path()

        if path == "/api/upload-compress":
            self.handle_upload_compress()
            return

        if path == "/api/video/info":
            if not extract_media_info:
                self.send_error_json("Video downloader module not available in cloud environment", 500)
                return
            data = self.read_json_body()
            url = data.get("url", "").strip()
            if not url:
                self.send_error_json("Video URL is required", 400)
                return

            try:
                res = extract_media_info(url)
                self.send_json(res)
            except Exception as e:
                self.send_error_json(f"Failed to extract video info: {e}", 500)
            return

        if path in ["/api/browse", "/api/open-folder", "/api/path-check", "/api/split-file", "/api/compress", "/api/video/download"]:
            self.send_error_json(
                "Local macOS filesystem operations are not available in cloud mode. "
                "Please use the Drag & Drop tab for instant browser compression, "
                "or run FileCompressor locally on your Mac via 'python server.py'.",
                400
            )
            return

        self.send_error(404, f"Endpoint not found: {path}")

    def handle_upload_compress(self):
        """Handle browser multipart file upload and compress in serverless /tmp."""
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error_json("Invalid content type, multipart/form-data required", 400)
            return

        temp_dir = tempfile.mkdtemp(prefix="upload_pack_")
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length)

            fmt = "zip"
            files_to_save = []

            # Try parsing with cgi.FieldStorage or fallback to boundary parser
            try:
                environ = {
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": str(content_length),
                }
                form = cgi.FieldStorage(
                    fp=io.BytesIO(raw_body),
                    headers=self.headers,
                    environ=environ,
                    keep_blank_values=True,
                )
                fmt = form.getvalue("format", "zip")
                items = form["files"] if "files" in form else []
                if not isinstance(items, list):
                    items = [items]
                for item in items:
                    if getattr(item, "filename", None):
                        fname = os.path.basename(item.filename)
                        if fname:
                            files_to_save.append((fname, item.file.read()))
            except Exception:
                # Boundary parsing fallback
                boundary = content_type.split("boundary=")[-1].strip().encode()
                parts = raw_body.split(b"--" + boundary)
                for part in parts:
                    if b"Content-Disposition" in part:
                        header_data, _, body_data = part.partition(b"\r\n\r\n")
                        header_str = header_data.decode("utf-8", errors="ignore")
                        body_data = body_data.rstrip(b"\r\n")
                        if 'name="format"' in header_str:
                            fmt = body_data.decode("utf-8", errors="ignore").strip()
                        elif 'name="files"' in header_str and 'filename="' in header_str:
                            fn_start = header_str.find('filename="') + 10
                            fn_end = header_str.find('"', fn_start)
                            if fn_start != -1 and fn_end != -1:
                                fname = os.path.basename(header_str[fn_start:fn_end])
                                if fname:
                                    files_to_save.append((fname, body_data))

            if not files_to_save:
                self.send_error_json("No valid files uploaded", 400)
                return

            upload_dir = os.path.join(temp_dir, "files")
            os.makedirs(upload_dir, exist_ok=True)

            archive_basename = os.path.splitext(files_to_save[0][0])[0] if len(files_to_save) == 1 else "compressed_files"
            for fname, data_bytes in files_to_save:
                dest_file = os.path.join(upload_dir, fname)
                with open(dest_file, "wb") as f_out:
                    f_out.write(data_bytes)

            source_to_compress = os.path.join(upload_dir, files_to_save[0][0]) if len(files_to_save) == 1 else upload_dir
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

            # Record in session history
            SESSION_HISTORY.insert(0, {
                "source_name": filename,
                "output_name": filename,
                "format": fmt,
                "original_size": res.get("original_size", file_size),
                "compressed_size": file_size,
                "saved_bytes": res.get("saved_bytes", 0),
                "saved_percentage": res.get("saved_percentage", 0),
                "time_taken": res.get("time_taken", 0.1),
                "timestamp": res.get("timestamp", ""),
            })
            if len(SESSION_HISTORY) > 50:
                SESSION_HISTORY.pop()

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(file_size))
            self.send_header("X-Saved-Percentage", str(res.get("saved_percentage", 0)))
            self.send_header("X-Saved-Bytes", str(res.get("saved_bytes", 0)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with open(final_file, "rb") as f:
                shutil.copyfileobj(f, self.wfile)

        except Exception as e:
            self.send_error_json(f"Upload error: {e}", 500)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# Export standard Vercel serverless entrypoint aliases
app = handler
application = handler

