# FileCompressor

A lightweight, clean file and folder compression utility for macOS with a simple, soothing light user interface.

## Highlights
- **Simple, Eye-Friendly Light UI**: Designed specifically without gradients, neon colors, or distracting elements.
- **Dual Workflows**:
  - **Local Filesystem Mode**: Compress any file or folder directly on your Mac using native macOS file/folder picker dialogs or quick path shortcuts (`Desktop`, `Downloads`, `Documents`).
  - **Browser Upload & Drag-Drop Mode**: Drag and drop files directly into the web interface and download the compressed archive immediately.
- **Multiple Formats**:
  - `.zip` (Universal compatibility)
  - `.tar.gz` (Standard Unix/Linux gzip)
  - `.tar.bz2` (High compression bzip2)
  - `.tar.xz` (Ultra compression LZMA2)
  - `.dmg` (Apple UDZO disk image)
- **Under 25 MB Limit & Multi-Part Splitting**:
  - Built-in **Target Maximum Size** control (default: 25 MB for Gmail/Outlook/Discord).
  - Uses maximum Level 9 / Ultra compression algorithms.
  - Automatically splits oversized archives into multi-volume parts (`.part01`, `.part02`, etc.) each guaranteed to be under 25 MB.
  - Provides a one-click copy command to easily recombine (`cat archive.part* > archive.zip`).
- **Exclude Bulky Cache & Junk**:
  - Option to strip `node_modules`, `.git`, `.DS_Store`, `__pycache__`, and `.venv` to drastically reduce file sizes.
- **Instagram Reels, YouTube & Pinterest Video Downloader**:
  - Download high-resolution videos directly from Instagram (Reels & Posts), YouTube (Videos & Shorts), and Pinterest (Video Pins).
  - **Preserves Exact Native Pixel Dimensions** (e.g. 1080×1920 vertical reels/shorts, 1920×1080 HD, 4K) without downscaling or distortion.
  - User-selected extensions: `.mp4` (H.264/AAC), `.webm` (VP9/Opus), `.mkv` (Matroska), `.mov` (QuickTime), or high-quality audio extraction (`.mp3`, `.m4a`, `.wav`).
  - Seamless integration: Download directly to any folder on your Mac or via browser, and one-click "Compress this Video" into an archive under 25 MB!
- **Direct macOS Integration**:
  - Native macOS file/folder picker dialogs triggered right from the browser.
  - "Show in Finder" button to reveal generated archives and downloaded videos instantly.
  - Calculation of original size, compressed size, space saved (MB and %), and elapsed time.

---

## Quick Start

### 1. Launch the Web Interface
Run the start script or execute `server.py`:
```bash
./start.sh
# or
python3 server.py
```
This automatically starts the local server at `http://localhost:8080` and opens your browser.

Options:
```bash
python3 server.py --port 8085       # Run on custom port
python3 server.py --no-browser      # Run without auto-opening the browser
```

### 2. Command-Line Usage (CLI)
You can also use the CLI directly in the terminal:
```bash
# Basic ZIP compression
./cli.py /path/to/folder

# Keep archive strictly under 25 MB (auto-splits if larger)
./cli.py /path/to/folder --max-size 25

# Exclude bulky build cache (.git, node_modules, etc.)
./cli.py /path/to/folder --max-size 25 --exclude-junk

# High-ratio .tar.xz format
./cli.py /path/to/folder -f tar.xz

# Download Instagram Reel in exact native resolution (.mp4)
./cli.py --video "https://www.instagram.com/reel/..." --video-ext mp4 -o ~/Downloads

# Download YouTube video in exact native resolution (.mp4)
./cli.py --video "https://www.youtube.com/watch?v=..." --video-ext mp4 -o ~/Downloads

# Download Pinterest video pin in exact native pixel dimensions (.webm)
./cli.py --video "https://pin.it/..." --video-ext webm -o ~/Desktop

# Extract high quality MP3 audio from an Instagram Reel or YouTube video
./cli.py --video "https://www.instagram.com/reel/..." --video-ext mp3 -o ~/Downloads
```

---

## Project Structure
```
FileCompressor/
├── cli.py                     # Standalone CLI tool with compression & video download
├── core/
│   ├── compressor.py          # Robust compression & multi-part engine
│   └── video_downloader.py    # YouTube & Pinterest downloader (exact pixel preservation)
├── server.py                  # Local HTTP server with native macOS integration
├── start.sh                   # One-click start script
└── static/
    ├── app.js                 # Frontend interactive logic
    ├── index.html             # Semantic HTML layout
    └── style.css              # Pure flat light styling (zero gradients)
```
