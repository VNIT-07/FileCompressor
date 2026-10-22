#!/usr/bin/env python3
"""
FileCompressor CLI - Fast, versatile compression utility for files and folders.
Supports: zip, tar.gz, tar.bz2, tar.xz, and dmg.
"""

import argparse
import os
import sys

# Ensure local core package and .venv packages are importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

_venv_lib = os.path.join(BASE_DIR, ".venv", "lib")
if os.path.isdir(_venv_lib):
    for _d in os.listdir(_venv_lib):
        _sp = os.path.join(_venv_lib, _d, "site-packages")
        if os.path.isdir(_sp) and _sp not in sys.path:
            sys.path.insert(0, _sp)

from core.compressor import compress


def main():
    parser = argparse.ArgumentParser(
        description="Compress files or folders with customizable output location, formats, and target sizes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("source", nargs="?", default=None, help="Path to file or folder to compress (or omit if using --video)")
    parser.add_argument(
        "--video",
        metavar="URL",
        default=None,
        help="Download video/reel from Instagram Reels, YouTube, or Pinterest in native pixel dimensions",
    )
    parser.add_argument(
        "--video-ext",
        choices=["mp4", "webm", "mkv", "mov", "mp3", "m4a", "wav"],
        default="mp4",
        help="Target extension for video/audio download (default: mp4)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Optional destination path or directory (defaults to source parent or downloads)",
    )
    parser.add_argument(
        "dest",
        nargs="?",
        default=None,
        help="Positional destination path (alternative to -o/--output)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["zip", "tar.gz", "tar.bz2", "tar.xz", "dmg"],
        default="zip",
        help="Archive compression format",
    )
    parser.add_argument(
        "--max-size",
        type=float,
        default=None,
        help="Target maximum size in MB (e.g. 25 for 25MB email/discord limit)",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        default=True,
        help="Automatically split into parts if archive exceeds --max-size",
    )
    parser.add_argument(
        "--exclude-junk",
        action="store_true",
        help="Exclude bulky build cache (.git, node_modules, .DS_Store, __pycache__, .venv)",
    )
    parser.add_argument(
        "--optimize-media",
        action="store_true",
        default=True,
        help="Optimize photos & images inside folder to fit under target size (default: True)",
    )
    parser.add_argument(
        "--absolute",
        action="store_true",
        help="Store absolute paths inside the archive (default: relative paths)",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Do not overwrite existing destination file if it already exists",
    )

    args = parser.parse_args()

    if args.video:
        from core.video_downloader import extract_media_info, download_media
        print(f"\n[INSPECTING] Fetching media info from: {args.video}")
        info = extract_media_info(args.video)
        if not info.get("success"):
            print(f"[ERROR] {info.get('error', 'Failed to inspect media')}")
            sys.exit(1)

        print(f"  Platform:    {info.get('platform')}")
        print(f"  Title:       {info.get('title')}")
        print(f"  Dimensions:  {info.get('dimensions')} ({info.get('aspect_label')})")
        print(f"  Duration:    {info.get('duration_formatted')}")
        print(f"  Target Ext:  .{args.video_ext}")

        dest_dir = args.output or args.dest or os.getcwd()
        if os.path.exists(dest_dir) and not os.path.isdir(dest_dir):
            dest_dir = os.path.dirname(dest_dir) or os.getcwd()

        print(f"\n[DOWNLOADING] Downloading media to: {dest_dir}...")
        dl_res = download_media(
            url=args.video,
            output_dir=dest_dir,
            target_ext=args.video_ext,
        )
        if dl_res.get("success"):
            print(f"\n[SUCCESS] Media downloaded successfully:")
            print(f"  Saved file:  {dl_res['output_path']}")
            print(f"  File size:   {dl_res['size_formatted']}")
            print(f"  Dimensions:  {dl_res['dimensions']}")
            print(f"  Format:      {dl_res['target_ext']}")
            sys.exit(0)
        else:
            print(f"\n[ERROR] Download failed: {dl_res.get('error')}")
            sys.exit(1)

    if not args.source:
        print("Error: 'source' argument is required when not using --video.")
        parser.print_help()
        sys.exit(1)

    print(f"Compressing: {os.path.abspath(args.source)}")
    print(f"Format:      {args.format}")
    if args.max_size:
        print(f"Target size: < {args.max_size} MB")

    result = compress(
        source=args.source,
        output=args.output or args.dest,
        fmt=args.format,
        relative=not args.absolute,
        overwrite=not args.no_overwrite,
        max_compression=True,
        exclude_junk=args.exclude_junk,
        target_size_mb=args.max_size,
        split_if_exceeds=args.split,
        optimize_media=args.optimize_media,
    )

    if result.get("success"):
        print(f"\n[SUCCESS] Archive generated successfully:")
        print(f"  Location:     {result['output']}")
        print(f"  Original:     {result['original_size_formatted']}")
        print(f"  Compressed:   {result['compressed_size_formatted']}")
        print(f"  Space saved:  {result['saved_bytes_formatted']} ({result['saved_percentage']}%)")
        print(f"  Time taken:   {result['duration_seconds']}s")

        if result.get("target_size_mb"):
            if result.get("is_under_target"):
                print(f"  Target Check: Under {result['target_size_mb']} MB limit (OK)")
            else:
                print(f"  Target Check: Exceeds {result['target_size_mb']} MB limit")

        if result.get("is_split") and result.get("parts"):
            print(f"\n[MULTI-PART] Archive was split into {len(result['parts'])} parts (< {result['target_size_mb']} MB each):")
            for p in result["parts"]:
                print(f"    - {p['filename']} ({p['size_formatted']})")
            print(f"\n  To reassemble:")
            print(f"    {result['join_command']}")
    else:
        print(f"\n[ERROR] Compression failed:")
        print(f"  {result.get('error', 'Unknown error')}")
        if "command" in result and result["command"]:
            print(f"  Command: {result['command']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
