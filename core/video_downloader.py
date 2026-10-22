"""
Core Video Downloader for Instagram Reels, YouTube, and Pinterest.
Extracts media information and downloads videos in user-selected extensions
while strictly preserving exact native pixel dimensions (width x height).
Uses yt-dlp + imageio-ffmpeg for maximum format compatibility and high quality.
"""

import os
import re
import ssl
import sys
import json
import shutil
import tempfile
import urllib.request
import urllib.parse
import subprocess
from typing import Dict, Any, Optional, List, Tuple

# Automatically resolve virtualenv site-packages if running with system python
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_venv_lib = os.path.join(_project_root, ".venv", "lib")
if os.path.isdir(_venv_lib):
    for _d in os.listdir(_venv_lib):
        _sp = os.path.join(_venv_lib, _d, "site-packages")
        if os.path.isdir(_sp) and _sp not in sys.path:
            sys.path.insert(0, _sp)

try:
    import certifi
    SSL_CA_BUNDLE = certifi.where()
except ImportError:
    SSL_CA_BUNDLE = None

try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = shutil.which("ffmpeg")

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_duration(seconds: Optional[float]) -> str:
    """Format seconds into MM:SS or HH:MM:SS."""
    if not seconds or seconds < 0:
        return "Unknown"
    sec = int(seconds)
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    rem_sec = sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{rem_sec:02d}"
    return f"{minutes:02d}:{rem_sec:02d}"


def sanitize_filename(name: str) -> str:
    """Clean filename of illegal characters."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:120] or "video"


def detect_platform(url: str) -> str:
    """Detect platform from URL."""
    url_lower = url.lower()
    if "instagram.com" in url_lower or "instagr.am" in url_lower or "ig.me" in url_lower:
        return "Instagram"
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    if "pinterest.com" in url_lower or "pin.it" in url_lower:
        return "Pinterest"
    return "Web Video"


def extract_instagram_shortcode(url: str) -> Optional[str]:
    """Extract Instagram media shortcode from reel, post, or tv URL."""
    url = url.strip()
    match = re.search(r'/(?:reel|reels|p|tv|share/reel)/([A-Za-z0-9_-]+)', url)
    if match:
        return match.group(1)
    return None


def resolve_url(url: str) -> str:
    """Follow redirects (e.g. for short links like pin.it, ig.me, or youtu.be)."""
    url = url.strip()
    url_lower = url.lower()
    if any(k in url_lower for k in ["pin.it", "ig.me", "youtu.be", "/share/reel/"]):
        try:
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                return resp.geturl()
        except Exception:
            pass
    return url


def get_video_dimensions_ffmpeg(file_path: str) -> Tuple[Optional[int], Optional[int]]:
    """Use FFmpeg to detect actual pixel width and height of a video file."""
    if not FFMPEG_PATH or not os.path.exists(file_path):
        return None, None
    try:
        cmd = [FFMPEG_PATH, "-i", file_path]
        proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, errors="ignore")
        # Find stream video: e.g. 1920x1080 or 1080x1920
        match = re.search(r",\s*(\d{2,5})x(\d{2,5})\b", proc.stderr)
        if match:
            return int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    return None, None


def fetch_page_html(url: str, referer: Optional[str] = None) -> str:
    """Fetch HTML using curl (for macOS native TLS handling) or urllib fallback."""
    try:
        cmd = [
            "curl", "-s", "-L", "--max-time", "12",
            "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H", "Accept-Language: en-US,en;q=0.9",
        ]
        if referer:
            cmd.extend(["-H", f"Referer: {referer}"])
        cmd.append(url)
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
        if proc.returncode == 0 and len(proc.stdout) > 200:
            return proc.stdout
    except Exception:
        pass

    try:
        ctx = ssl._create_unverified_context()
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=12) as res:
            return res.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def extract_media_info(url: str) -> Dict[str, Any]:
    """
    Extract video/media metadata from Instagram Reels, YouTube, Pinterest, or other video platforms.
    Returns title, author, thumbnail, duration, native pixel dimensions, and available formats.
    """
    resolved_url = resolve_url(url)
    platform = detect_platform(resolved_url)

    # For Pinterest, direct HTML extraction is ultra-fast, robust, and bypasses 403 API blocks
    if platform == "Pinterest":
        pin_res = _extract_pinterest_fallback(resolved_url)
        if pin_res.get("success"):
            return pin_res

    # For Instagram, try fallback scraper if yt-dlp is not present
    if yt_dlp is None:
        if platform == "Instagram":
            return _extract_instagram_fallback(resolved_url)
        return {
            "success": False,
            "error": "yt-dlp is not installed in the environment."
        }

    http_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }
    if platform == "Instagram":
        http_headers["Referer"] = "https://www.instagram.com/"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "skip_download": True,
        "http_headers": http_headers,
    }
    if FFMPEG_PATH:
        ydl_opts["ffmpeg_location"] = FFMPEG_PATH
    if SSL_CA_BUNDLE:
        ydl_opts["ca_certs"] = SSL_CA_BUNDLE

    # Try extraction with yt-dlp
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(resolved_url, download=False)
    except Exception as e:
        error_msg = str(e)
        if platform == "Pinterest":
            pinterest_fallback = _extract_pinterest_fallback(resolved_url)
            if pinterest_fallback.get("success"):
                return pinterest_fallback
        if platform == "Instagram":
            insta_fallback = _extract_instagram_fallback(resolved_url)
            if insta_fallback.get("success"):
                return insta_fallback
        return {
            "success": False,
            "error": f"Failed to inspect media: {error_msg}"
        }

    if not info:
        return {"success": False, "error": "No media info found at provided URL."}

    # If it's a playlist or multiple entries, pick the first
    if "entries" in info and info["entries"]:
        info = info["entries"][0]

    title = info.get("title") or "Video"
    uploader = info.get("uploader") or info.get("channel") or info.get("creator") or platform
    duration = info.get("duration")
    thumbnail = info.get("thumbnail") or ""
    webpage_url = info.get("webpage_url") or resolved_url

    # Calculate native width & height
    native_width = info.get("width")
    native_height = info.get("height")

    formats = info.get("formats", [])
    resolutions = set()
    best_w = native_width or 0
    best_h = native_height or 0

    for f in formats:
        w = f.get("width")
        h = f.get("height")
        vcodec = f.get("vcodec")
        if vcodec and vcodec != "none" and h:
            resolutions.add(h)
            if w and h and (w * h > best_w * best_h):
                best_w = w
                best_h = h

    if best_w and best_h:
        native_width = best_w
        native_height = best_h

    sorted_resolutions = sorted(list(resolutions), reverse=True)

    aspect_label = ""
    if native_width and native_height:
        ratio = native_width / native_height
        if abs(ratio - 16 / 9) < 0.05:
            aspect_label = "16:9 Landscape"
        elif abs(ratio - 9 / 16) < 0.05:
            if platform == "Instagram":
                aspect_label = "9:16 Vertical (Instagram Reel)"
            elif platform == "Pinterest":
                aspect_label = "9:16 Vertical (Pin)"
            else:
                aspect_label = "9:16 Vertical (Reel / Short / Pin)"
        elif abs(ratio - 4 / 5) < 0.05:
            aspect_label = "4:5 Portrait (Instagram)"
        elif abs(ratio - 1.0) < 0.05:
            aspect_label = "1:1 Square"
        elif abs(ratio - 4 / 3) < 0.05:
            aspect_label = "4:3 Standard"
        else:
            aspect_label = f"{native_width}:{native_height}"

    dimensions_str = f"{native_width} × {native_height} px" if (native_width and native_height) else "Original Dimension"

    return {
        "success": True,
        "platform": platform,
        "url": webpage_url,
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "duration_formatted": format_duration(duration),
        "thumbnail": thumbnail,
        "width": native_width,
        "height": native_height,
        "dimensions": dimensions_str,
        "aspect_label": aspect_label,
        "available_resolutions": sorted_resolutions,
        "supported_video_exts": [
            {"ext": "mp4", "name": "MP4 (.mp4)", "desc": "Universal compatibility (H.264/AAC)", "badge": "Recommended"},
            {"ext": "webm", "name": "WebM (.webm)", "desc": "Open modern web format (VP9/Opus)", "badge": "High Efficiency"},
            {"ext": "mkv", "name": "MKV (.mkv)", "desc": "Matroska container with all streams", "badge": "Lossless Container"},
            {"ext": "mov", "name": "QuickTime (.mov)", "desc": "Apple QuickTime native format", "badge": "macOS Native"}
        ],
        "supported_audio_exts": [
            {"ext": "mp3", "name": "MP3 (.mp3)", "desc": "Universal audio (320 kbps high quality)", "badge": "Audio Only"},
            {"ext": "m4a", "name": "M4A (.m4a)", "desc": "High quality Apple AAC audio stream", "badge": "Audio Only"},
            {"ext": "wav", "name": "WAV (.wav)", "desc": "Uncompressed lossless PCM audio", "badge": "Lossless Audio"}
        ]
    }


def _extract_pinterest_fallback(url: str) -> Dict[str, Any]:
    """Fallback scraper for Pinterest video pins if yt-dlp encounters an issue."""
    try:
        html = fetch_page_html(url)
        if not html:
            return {"success": False, "error": "Could not connect to Pinterest pin."}

        # Look for direct video URLs (.mp4 or .m3u8 from v.pinimg.com or v1.pinimg.com)
        all_videos = re.findall(r'(https://[^\s"\'<>]*(?:v\.pinimg\.com|v1\.pinimg\.com)[^\s"\'<>]*\.(?:mp4|m3u8))', html)
        og_v = re.search(r'<meta[^>]+property=[\'"]og:video(?::secure_url)?[\'"][^>]+content=[\'"]([^\'"]+)[\'"]', html)
        if not og_v:
            og_v = re.search(r'<meta[^>]+content=[\'"]([^\'"]+)[\'"][^>]+property=[\'"]og:video(?::secure_url)?[\'"]', html)
        if og_v:
            all_videos.insert(0, og_v.group(1))

        if not all_videos:
            return {"success": False, "error": "No video stream found for this Pinterest pin. (It may be an image-only pin)."}

        # Prioritize 1080p > 720p > other .mp4 > .m3u8
        def _score_video(u: str) -> int:
            if ".mp4" in u and "1080p" in u: return 1000
            if ".mp4" in u and "720p" in u: return 800
            if ".mp4" in u and "exp7" in u: return 700
            if ".mp4" in u: return 600
            if ".m3u8" in u: return 400
            return 100

        best_video_url = sorted(set(all_videos), key=_score_video, reverse=True)[0]

        # Check for og:image as thumbnail
        og_image_match = re.search(r'<meta[^>]+property=[\'"]og:image[\'"][^>]+content=[\'"]([^\'"]+)[\'"]', html)
        if not og_image_match:
            og_image_match = re.search(r'<meta[^>]+content=[\'"]([^\'"]+)[\'"][^>]+property=[\'"]og:image[\'"]', html)

        # Check title
        title_match = re.search(r"<title>([^<]+)</title>", html)
        title = title_match.group(1).split("|")[0].strip() if title_match else "Pinterest Video"

        thumbnail = og_image_match.group(1) if og_image_match else ""

        # Calculate dimensions
        width = 720
        height = 1280
        if "1080p" in best_video_url:
            width = 1080
            height = 1920
        elif "720p" in best_video_url or "exp7" in best_video_url:
            width = 720
            height = 1280

        return {
            "success": True,
            "platform": "Pinterest",
            "url": url,
            "title": title,
            "uploader": "Pinterest",
            "duration": None,
            "duration_formatted": "Video Pin",
            "thumbnail": thumbnail,
            "width": width,
            "height": height,
            "dimensions": f"{width} × {height} px",
            "aspect_label": "9:16 Vertical (Pin)",
            "available_resolutions": [height],
            "direct_video_url": best_video_url,
            "supported_video_exts": [
                {"ext": "mp4", "name": "MP4 (.mp4)", "desc": "Universal compatibility (H.264)", "badge": "Recommended"},
                {"ext": "webm", "name": "WebM (.webm)", "desc": "Modern web format", "badge": "High Efficiency"},
                {"ext": "mkv", "name": "MKV (.mkv)", "desc": "Matroska container", "badge": "Lossless Container"},
                {"ext": "mov", "name": "QuickTime (.mov)", "desc": "Apple native container", "badge": "macOS Native"}
            ],
            "supported_audio_exts": [
                {"ext": "mp3", "name": "MP3 (.mp3)", "desc": "Universal audio (320 kbps)", "badge": "Audio Only"},
                {"ext": "m4a", "name": "M4A (.m4a)", "desc": "Apple AAC audio track", "badge": "Audio Only"},
                {"ext": "wav", "name": "WAV (.wav)", "desc": "Lossless uncompressed audio", "badge": "Lossless Audio"}
            ]
        }
    except Exception as e:
        return {"success": False, "error": f"Pinterest extraction error: {e}"}


def _extract_instagram_fallback(url: str) -> Dict[str, Any]:
    """
    Fallback scraper for Instagram Reels and videos if yt-dlp encounters a login wall or rate limit.
    Uses public embed endpoints, oEmbed API, and HTML metadata extraction.
    """
    try:
        resolved_url = resolve_url(url)
        code = extract_instagram_shortcode(resolved_url) or extract_instagram_shortcode(url)
        if not code:
            return {
                "success": False,
                "error": "Could not identify Instagram reel shortcode. Please check the URL."
            }

        canonical_url = f"https://www.instagram.com/reel/{code}/"
        embed_url = f"https://www.instagram.com/p/{code}/embed/captioned/"

        # 1. Fetch captioned embed HTML
        html_content = fetch_page_html(embed_url, referer="https://www.instagram.com/")
        if not html_content:
            # Try non-captioned embed fallback
            html_content = fetch_page_html(f"https://www.instagram.com/reel/{code}/embed/", referer="https://www.instagram.com/")
        if not html_content:
            # Try raw URL with headers
            html_content = fetch_page_html(canonical_url, referer="https://www.instagram.com/")

        video_urls: List[str] = []

        if html_content:
            import html as py_html
            # Look for video src in tag
            m_video = re.search(r'<video[^>]+src=[\'"]([^\'"]+)[\'"]', html_content, re.IGNORECASE)
            if m_video:
                video_urls.append(py_html.unescape(m_video.group(1)))

            # Look for video_url in json
            json_video_matches = re.findall(r'["\'](?:video_url|video_play_url|playback_url)["\']\s*:\s*["\']([^"\']+)["\']', html_content)
            for raw in json_video_matches:
                cleaned = raw.replace('\\/', '/').replace('\\u0026', '&')
                cleaned = py_html.unescape(cleaned)
                if cleaned.startswith("http") and cleaned not in video_urls:
                    video_urls.append(cleaned)

            # Look for og:video meta tags
            og_v = re.findall(r'<meta[^>]+content=[\'"]([^\'"]+)[\'"][^>]+property=[\'"]og:video(?::secure_url)?[\'"]', html_content)
            if not og_v:
                og_v = re.findall(r'<meta[^>]+property=[\'"]og:video(?::secure_url)?[\'"][^>]+content=[\'"]([^\'"]+)[\'"]', html_content)
            for v in og_v:
                cleaned = py_html.unescape(v)
                if cleaned.startswith("http") and cleaned not in video_urls:
                    video_urls.append(cleaned)

            # Look for CDN mp4 patterns
            cdn_matches = re.findall(r'(https://[^\s"\'<>]*(?:cdninstagram\.com|fbcdn\.net)[^\s"\'<>]*\.mp4[^\s"\'<>]*)', html_content)
            for raw in cdn_matches:
                cleaned = raw.replace('\\/', '/').replace('\\u0026', '&')
                cleaned = py_html.unescape(cleaned)
                if cleaned not in video_urls:
                    video_urls.append(cleaned)

        # 2. Extract thumbnail, author, title
        thumbnail = ""
        author = "Instagram Creator"
        title = "Instagram Reel"

        if html_content:
            # Thumbnail
            thumb_match = re.search(r'["\'](?:display_url|thumbnail_src)["\']\s*:\s*["\']([^"\']+)["\']', html_content)
            if thumb_match:
                thumbnail = thumb_match.group(1).replace('\\/', '/').replace('\\u0026', '&')
            if not thumbnail:
                og_img = re.search(r'<meta[^>]+property=[\'"]og:image[\'"][^>]+content=[\'"]([^\'"]+)[\'"]', html_content)
                if not og_img:
                    og_img = re.search(r'<meta[^>]+content=[\'"]([^\'"]+)[\'"][^>]+property=[\'"]og:image[\'"]', html_content)
                if og_img:
                    thumbnail = og_img.group(1)

            # Author
            author_match = re.search(r'["\']username["\']\s*:\s*["\']([^"\']+)["\']', html_content)
            if author_match:
                author = f"@{author_match.group(1)}"
            else:
                og_author = re.search(r'<span class="FeedbackUsername">([^<]+)</span>', html_content)
                if og_author:
                    author = f"@{og_author.group(1).strip()}"

            # Caption / Title
            caption_match = re.search(r'<div class="Caption"[^>]*>(.*?)</div>', html_content, re.DOTALL)
            if caption_match:
                clean_cap = re.sub(r'<[^>]+>', '', caption_match.group(1)).strip()
                if clean_cap:
                    title = clean_cap.split('\n')[0][:100]

        # 3. Check official oEmbed API for enhanced metadata
        try:
            oembed_url = f"https://www.instagram.com/api/v1/oembed/?url={urllib.parse.quote(canonical_url)}"
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(
                oembed_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "application/json"
                }
            )
            with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
                oembed = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if oembed.get("author_name"):
                    author = f"@{oembed['author_name']}"
                if oembed.get("title") and (title == "Instagram Reel" or len(oembed["title"]) > len(title)):
                    title = oembed["title"][:100]
                if oembed.get("thumbnail_url") and not thumbnail:
                    thumbnail = oembed["thumbnail_url"]
        except Exception:
            pass

        if not video_urls:
            return {
                "success": False,
                "error": "Could not extract video stream for this Instagram Reel. (The reel may be private or requires Instagram login)."
            }

        # Select highest quality stream
        best_video_url = video_urls[0]

        return {
            "success": True,
            "platform": "Instagram",
            "url": canonical_url,
            "title": title,
            "uploader": author,
            "duration": None,
            "duration_formatted": "Instagram Reel",
            "thumbnail": thumbnail,
            "width": 1080,
            "height": 1920,
            "dimensions": "1080 × 1920 px",
            "aspect_label": "9:16 Vertical (Instagram Reel)",
            "available_resolutions": [1080, 720],
            "direct_video_url": best_video_url,
            "supported_video_exts": [
                {"ext": "mp4", "name": "MP4 (.mp4)", "desc": "Universal compatibility (H.264)", "badge": "Recommended"},
                {"ext": "webm", "name": "WebM (.webm)", "desc": "Modern web format (VP9/Opus)", "badge": "High Efficiency"},
                {"ext": "mkv", "name": "MKV (.mkv)", "desc": "Matroska lossless container", "badge": "Lossless Container"},
                {"ext": "mov", "name": "QuickTime (.mov)", "desc": "Apple QuickTime native format", "badge": "macOS Native"}
            ],
            "supported_audio_exts": [
                {"ext": "mp3", "name": "MP3 (.mp3)", "desc": "Universal audio (320 kbps high quality)", "badge": "Audio Only"},
                {"ext": "m4a", "name": "M4A (.m4a)", "desc": "Apple AAC audio track", "badge": "Audio Only"},
                {"ext": "wav", "name": "WAV (.wav)", "desc": "Lossless uncompressed audio", "badge": "Lossless Audio"}
            ]
        }
    except Exception as e:
        return {"success": False, "error": f"Instagram extraction error: {e}"}


def download_media(
    url: str,
    output_dir: str,
    target_ext: str = "mp4",
    resolution: Optional[int] = None,
    custom_name: Optional[str] = None,
    progress_hook: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Download video/media in the user-selected extension, strictly preserving
    the exact pixel dimensions (width x height) without downscaling or distortion.
    """
    resolved_url = resolve_url(url)
    platform = detect_platform(resolved_url)

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    is_audio = target_ext.lower() in ["mp3", "m4a", "wav", "aac", "flac"]

    temp_dir = tempfile.mkdtemp(prefix="vdl_temp_")
    try:
        download_success = False
        media_info = None
        raw_media_path = None

        # Special fast-path for Pinterest direct videos
        if platform == "Pinterest":
            fb = _extract_pinterest_fallback(resolved_url)
            if fb.get("success") and fb.get("direct_video_url"):
                direct_url = fb["direct_video_url"]
                if ".mp4" in direct_url:
                    dest_tmp = os.path.join(temp_dir, "source_media.mp4")
                    try:
                        cmd = [
                            "curl", "-s", "-L", "--max-time", "60",
                            "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                            direct_url, "-o", dest_tmp
                        ]
                        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if proc.returncode == 0 and os.path.exists(dest_tmp) and os.path.getsize(dest_tmp) > 1000:
                            download_success = True
                            media_info = fb
                            raw_media_path = dest_tmp
                    except Exception:
                        pass

                    if not download_success:
                        try:
                            ctx = ssl._create_unverified_context()
                            req = urllib.request.Request(direct_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(req, context=ctx, timeout=30) as r, open(dest_tmp, "wb") as f_out:
                                shutil.copyfileobj(r, f_out)
                            if os.path.exists(dest_tmp) and os.path.getsize(dest_tmp) > 1000:
                                download_success = True
                                media_info = fb
                                raw_media_path = dest_tmp
                        except Exception:
                            pass

        # Fast-path for Instagram direct videos
        if platform == "Instagram" and not download_success:
            fb = _extract_instagram_fallback(resolved_url)
            if fb.get("success") and fb.get("direct_video_url"):
                direct_url = fb["direct_video_url"]
                dest_tmp = os.path.join(temp_dir, "source_media.mp4")
                try:
                    cmd = [
                        "curl", "-s", "-L", "--max-time", "90",
                        "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        "-H", "Referer: https://www.instagram.com/",
                        direct_url, "-o", dest_tmp
                    ]
                    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if proc.returncode == 0 and os.path.exists(dest_tmp) and os.path.getsize(dest_tmp) > 1000:
                        download_success = True
                        media_info = fb
                        raw_media_path = dest_tmp
                except Exception:
                    pass

                if not download_success:
                    try:
                        ctx = ssl._create_unverified_context()
                        req = urllib.request.Request(
                            direct_url,
                            headers={
                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                                "Referer": "https://www.instagram.com/"
                            }
                        )
                        with urllib.request.urlopen(req, context=ctx, timeout=45) as r, open(dest_tmp, "wb") as f_out:
                            shutil.copyfileobj(r, f_out)
                        if os.path.exists(dest_tmp) and os.path.getsize(dest_tmp) > 1000:
                            download_success = True
                            media_info = fb
                            raw_media_path = dest_tmp
                    except Exception:
                        pass

        # Standard yt-dlp path for YouTube, Instagram, and general video platforms
        if not download_success:
            if yt_dlp is None:
                raise RuntimeError("yt-dlp is not installed in the environment.")

            if is_audio:
                format_str = "bestaudio/best"
            elif resolution:
                format_str = f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]/best"
            else:
                format_str = "bestvideo+bestaudio/best"

            ydl_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
            if platform == "Instagram":
                ydl_headers["Referer"] = "https://www.instagram.com/"

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "nocheckcertificate": True,
                "outtmpl": os.path.join(temp_dir, "source_media.%(ext)s"),
                "format": format_str,
                "http_headers": ydl_headers,
            }

            if FFMPEG_PATH:
                ydl_opts["ffmpeg_location"] = FFMPEG_PATH
            if SSL_CA_BUNDLE:
                ydl_opts["ca_certs"] = SSL_CA_BUNDLE
            if progress_hook:
                ydl_opts["progress_hooks"] = [progress_hook]

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    media_info = ydl.extract_info(resolved_url, download=True)
                    download_success = True
            except Exception as e:
                # If yt-dlp failed on Instagram, try fallback scraper download
                if platform == "Instagram":
                    fb = _extract_instagram_fallback(resolved_url)
                    if fb.get("success") and fb.get("direct_video_url"):
                        direct_url = fb["direct_video_url"]
                        dest_tmp = os.path.join(temp_dir, "source_media.mp4")
                        cmd = [
                            "curl", "-s", "-L", "--max-time", "90",
                            "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                            "-H", "Referer: https://www.instagram.com/",
                            direct_url, "-o", dest_tmp
                        ]
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if os.path.exists(dest_tmp) and os.path.getsize(dest_tmp) > 1000:
                            download_success = True
                            media_info = fb
                            raw_media_path = dest_tmp
                if not download_success:
                    raise RuntimeError(f"Download failed: {e}")

            downloaded_files = [
                os.path.join(temp_dir, f) for f in os.listdir(temp_dir)
                if not f.endswith(".part") and not f.endswith(".ytdl") and os.path.isfile(os.path.join(temp_dir, f))
            ]
            if not downloaded_files:
                raise RuntimeError("No media file was produced during download.")
            raw_media_path = downloaded_files[0]

        # Extract title and prepare final output filename
        raw_title = custom_name or (media_info.get("title") if media_info else "Video") or "Downloaded_Video"
        clean_title = sanitize_filename(raw_title)
        final_filename = f"{clean_title}.{target_ext.lower().lstrip('.')}"
        final_dest_path = os.path.join(output_dir, final_filename)

        # Counter for existing file names to avoid overwriting unless intended
        counter = 1
        base_stem = clean_title
        while os.path.exists(final_dest_path):
            final_filename = f"{base_stem} ({counter}).{target_ext.lower().lstrip('.')}"
            final_dest_path = os.path.join(output_dir, final_filename)
            counter += 1

        # Check original pixel dimensions before any remuxing
        orig_width, orig_height = None, None
        if not is_audio and FFMPEG_PATH:
            orig_width, orig_height = get_video_dimensions_ffmpeg(raw_media_path)

        # Handle container conversion or stream copy to target extension
        raw_ext = os.path.splitext(raw_media_path)[1].lower().lstrip(".")
        target_clean_ext = target_ext.lower().lstrip(".")

        if is_audio:
            # Audio conversion using FFmpeg
            if FFMPEG_PATH:
                cmd = [FFMPEG_PATH, "-y", "-i", raw_media_path, "-vn"]
                if target_clean_ext == "mp3":
                    cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k"])
                elif target_clean_ext == "m4a":
                    cmd.extend(["-c:a", "aac", "-b:a", "256k"])
                elif target_clean_ext == "wav":
                    cmd.extend(["-c:a", "pcm_s16le"])
                cmd.append(final_dest_path)
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                if res.returncode != 0:
                    shutil.move(raw_media_path, final_dest_path)
            else:
                shutil.move(raw_media_path, final_dest_path)

        elif raw_ext == target_clean_ext:
            # Same extension - direct move without touching streams
            shutil.move(raw_media_path, final_dest_path)

        else:
            # Different video extension requested by user (e.g. mp4 -> mkv, webm -> mp4, etc.)
            # CRITICAL: We preserve the EXACT pixel dimensions!
            if FFMPEG_PATH:
                # Try stream copy first (fastest, 100% lossless pixel preserve)
                copy_cmd = [FFMPEG_PATH, "-y", "-i", raw_media_path, "-c", "copy", final_dest_path]
                res_copy = subprocess.run(copy_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if res_copy.returncode != 0:
                    # Stream copy not possible for this container combination,
                    # Transcode to target container WITHOUT scaling to keep 100% same pixel dimensions!
                    transcode_cmd = [
                        FFMPEG_PATH, "-y", "-i", raw_media_path,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k",
                        final_dest_path
                    ]
                    if target_clean_ext == "webm":
                        transcode_cmd = [
                            FFMPEG_PATH, "-y", "-i", raw_media_path,
                            "-c:v", "libvpx-vp9", "-crf", "28", "-b:v", "0",
                            "-c:a", "libopus", "-b:a", "128k",
                            final_dest_path
                        ]
                    subprocess.run(transcode_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if not os.path.exists(final_dest_path) or os.path.getsize(final_dest_path) == 0:
                    # Fallback to direct move
                    shutil.move(raw_media_path, final_dest_path)
            else:
                shutil.move(raw_media_path, final_dest_path)

        # Verify final file exists and get stats
        if not os.path.exists(final_dest_path):
            raise RuntimeError("Final output file could not be generated.")

        final_size = os.path.getsize(final_dest_path)
        final_w, final_h = None, None
        if not is_audio and FFMPEG_PATH:
            final_w, final_h = get_video_dimensions_ffmpeg(final_dest_path)
            if not final_w:
                final_w = orig_width or (media_info.get("width") if media_info else None)
                final_h = orig_height or (media_info.get("height") if media_info else None)

        dim_str = f"{final_w} × {final_h} px (Exact Native Pixels Preserved)" if (final_w and final_h) else "Audio Track"

        return {
            "success": True,
            "platform": platform,
            "filename": os.path.basename(final_dest_path),
            "output_path": final_dest_path,
            "output_dir": output_dir,
            "size_bytes": final_size,
            "size_formatted": format_bytes(final_size),
            "width": final_w,
            "height": final_h,
            "dimensions": dim_str,
            "target_ext": target_clean_ext,
            "title": raw_title,
            "is_audio": is_audio,
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
