# FileCompressor Studio

<p align="center">
  <strong>Fast, eye-friendly, cross-platform file archiving and media engine for Windows, macOS, Linux, and Vercel.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Vercel-success?style=flat" alt="Platforms" />
  <img src="https://img.shields.io/badge/Deployment-Vercel%20Serverless%20Ready-black?style=flat&logo=vercel&logoColor=white" alt="Vercel Ready" />
  <img src="https://img.shields.io/badge/Formats-ZIP%20%7C%20TAR.GZ%20%7C%20TAR.BZ2%20%7C%20TAR.XZ%20%7C%20DMG-blue?style=flat" alt="Formats" />
  <img src="https://img.shields.io/badge/UI-Clean%20Light%20%26%20Dark%20Theme-6366f1?style=flat" alt="UI Theme" />
</p>

---

## Overview

**FileCompressor Studio** is a distraction-free, high-performance file compression utility and media downloader built with zero bloat. It runs seamlessly as a **local desktop app** (with native OS dialogs and Explorer/Finder integration) or as a **cloud web application** deployed to Vercel with client-side hybrid acceleration.

### Highlights

- **Eye-Friendly Clean Interface**: Designed specifically without distracting neon gradients or visual clutter. Includes both Light and Dark modes.
- **Cross-Platform Local Workflows**:
  - **Windows**: Native File Explorer pickers, Windows file highlight integration (`explorer.exe /select`), and `copy /b` recombine scripts.
  - **macOS**: Native AppleScript dialogs, "Show in Finder" integration, and `.dmg` Apple UDZO creation.
  - **Linux**: Automatic fallback to Tkinter / Zenity file choosers and standard Unix commands.
- **Zero-Dependency Built-In Engine**:
  - Automatically falls back to Python's standard library `zipfile` and `tarfile` when system command-line utilities (`zip`, `tar`) are absent (e.g. on clean Windows installations).
- **Under 25 MB Limit Guarantee & Multi-Part Splitting**:
  - Guarantees archives respect attachment ceilings for Gmail, Outlook, and Discord.
  - Level 9 / Ultra maximum compression algorithms.
  - Oversized files/directories are automatically split into sequentially numbered parts (`.part01`, `.part02`, etc.) strictly under 25 MB each.
  - Instant one-click terminal commands to recombine parts on any OS.
- **Instagram Reels, YouTube & Pinterest Video Downloader**:
  - Extracts and downloads high-resolution videos from Instagram (Reels & Posts), YouTube (Videos & Shorts), and Pinterest (Video Pins).
  - **Strictly preserves exact native pixel dimensions** (e.g. 1080×1920 vertical reels/shorts, 1920×1080 Full HD, 4K) without downscaling or letterboxing.
  - User-selected extensions: `.mp4`, `.webm`, `.mkv`, `.mov`, or audio extraction (`.mp3`, `.m4a`, `.wav`).
- **Vercel Serverless Ready (Hybrid In-Browser Engine)**:
  - Deploys to Vercel in 1 click.
  - Incorporates **JSZip** client-side acceleration: files dragged into the browser are compressed directly on the user's CPU, completely bypassing Vercel's strict **4.5 MB serverless upload limit**!

---

## Format & Compatibility Matrix

| Format | Extension | Algorithm | Windows | macOS | Linux | Cloud / Vercel |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **ZIP** | `.zip` | Deflate (Level 9) | Yes | Yes | Yes | Yes (Zero-limit browser engine) |
| **Tar Gzip** | `.tar.gz` | Gzip (Max) | Yes | Yes | Yes | Yes (< 4.5 MB serverless) |
| **Tar Bzip2** | `.tar.bz2` | Bzip2 (Max) | Yes | Yes | Yes | Yes (< 4.5 MB serverless) |
| **Tar XZ** | `.tar.xz` | LZMA2 (Ultra) | Yes | Yes | Yes | Yes (< 4.5 MB serverless) |
| **Disk Image** | `.dmg` | Apple UDZO | No | Yes | No | Local macOS only |

---

## Quick Start

### 1. Launch the Desktop Web Studio

#### On Windows:
Double-click `start.bat` or run:
```cmd
start.bat
:: or
python server.py
```

#### On macOS & Linux:
```bash
./start.sh
# or
python3 server.py
```

This starts the local web server at `http://localhost:8080` and opens your default browser automatically.

#### Server Options:
```bash
python server.py --port 8085       # Run on custom port
python server.py --no-browser      # Do not auto-launch browser window
```

---

### 2. Command-Line Interface (CLI)

The CLI tool (`cli.py`) offers full terminal automation for compression and video downloading:

#### Compression Examples:

```bash
# Basic ZIP compression (Windows)
python cli.py C:\path\to\folder

# Basic ZIP compression (macOS/Linux)
./cli.py /path/to/folder

# Guarantee output stays strictly under 25 MB (auto-splits if exceeded)
python cli.py C:\path\to\folder --max-size 25

# Exclude build caches (node_modules, .git, __pycache__, .venv)
python cli.py C:\path\to\folder --max-size 25 --exclude-junk

# High-ratio .tar.xz format with custom destination
python cli.py C:\path\to\folder -f tar.xz -o C:\Backups
```

#### Video Downloader Examples:

```bash
# Download Instagram Reel in exact native vertical 1080x1920 (.mp4)
python cli.py --video "https://www.instagram.com/reel/..." --video-ext mp4 -o ~/Downloads

# Download YouTube video or Short in original resolution (.mp4)
python cli.py --video "https://www.youtube.com/watch?v=..." --video-ext mp4 -o ~/Downloads

# Download Pinterest Video Pin (.webm)
python cli.py --video "https://pin.it/..." --video-ext webm -o ~/Desktop

# Extract high-quality MP3 audio from any supported video URL
python cli.py --video "https://www.instagram.com/reel/..." --video-ext mp3 -o ~/Downloads
```

---

## Deploying to Vercel

FileCompressor Studio includes full configuration for immediate zero-config deployment to Vercel.

### Step-by-Step Deployment

1. **Push your repository to GitHub**:
   ```bash
   git add .
   git commit -m "Configure Vercel deployment and cross-platform support"
   git push origin main
   ```

2. **Connect to Vercel**:
   - Go to [vercel.com/new](https://vercel.com/new).
   - Import your **`FileCompressor`** repository.
   - Leave the **Framework Preset** as **Other** (Vercel will detect `vercel.json` automatically).
   - Click **Deploy**.

3. **Enjoy your live web app**:
   - Your application will be live at `https://your-project.vercel.app`.

### How Cloud Mode Works
- **Hybrid In-Browser Archiver**: Vercel Serverless Functions have a strict **4.5 MB request payload limit**. To overcome this, FileCompressor Studio automatically detects cloud deployment and uses client-side **JSZip** inside the user's browser. Files of any size (50 MB, 500 MB, 1 GB+) are compressed directly on the user's device with zero server latency and zero upload limits!
- **Serverless API**: Routes `/api/upload-compress`, `/api/info`, `/api/history`, and `/api/video/*` run seamlessly on `@vercel/python` Serverless Functions.
- **Adaptive UI**: In cloud mode, the studio defaults to the **Drag & Drop** tab and presents informative status indicators.

---

## Reassembling Multi-Part Archives

When an archive exceeds the 25 MB limit and is split into parts (`archive_part01.zip`, `archive_part02.zip`, etc.), recombine them with a single terminal command:

#### On Windows (Command Prompt / PowerShell):
```cmd
copy /b "archive_part"*.zip "archive.zip"
```

#### On macOS & Linux:
```bash
cat "archive_part"*.zip > "archive.zip"
```

---

## CLI Options Reference

| Argument / Flag | Default | Description |
| :--- | :---: | :--- |
| `source` | `None` | Path to file or folder to compress (omitted if using `--video`). |
| `-o`, `--output` | `None` | Target output file or destination directory. |
| `-f`, `--format` | `zip` | Archive format (`zip`, `tar.gz`, `tar.bz2`, `tar.xz`, `dmg`). |
| `--max-size` | `None` | Maximum archive budget in MB (e.g. `25` for Gmail/Discord limit). |
| `--split` | `True` | Automatically split into parts if size exceeds `--max-size`. |
| `--exclude-junk` | `False` | Omit `node_modules`, `.git`, `.DS_Store`, `__pycache__`, and `.venv`. |
| `--optimize-media` | `True` | Automatically resample and compress photos/images inside folder. |
| `--absolute` | `False` | Store absolute filesystem paths inside the archive. |
| `--no-overwrite` | `False` | Prevent overwriting if destination archive already exists. |
| `--video` | `None` | URL from Instagram Reels, YouTube, or Pinterest. |
| `--video-ext` | `mp4` | Format for video/audio (`mp4`, `webm`, `mkv`, `mov`, `mp3`, `m4a`, `wav`). |

---

## Project Structure

```
FileCompressor/
├── api/
│   └── index.py               # Vercel serverless function entrypoint
├── cli.py                     # Standalone CLI tool for compression & media download
├── core/
│   ├── compressor.py          # Cross-platform compression & multi-part engine
│   └── video_downloader.py    # YouTube & Pinterest downloader (exact pixel preservation)
├── server.py                  # Local HTTP server with native Windows & macOS integration
├── start.bat                  # One-click Windows launch script
├── start.sh                   # One-click macOS & Linux launch script
├── vercel.json                # Vercel deployment routing configuration
├── requirements.txt           # Python dependencies for local & Vercel runtime
└── static/
    ├── app.js                 # Frontend interactive logic & client-side compression
    ├── index.html             # Semantic HTML layout with adaptive platform detection
    └── style.css              # Pure flat light & dark styling
```

---

## License

MIT License. Open source and free for personal and commercial use.
