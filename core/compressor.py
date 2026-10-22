"""
Core compression engine for FileCompressor.
Supports zip, tar.gz, tar.bz2, tar.xz, and dmg.
Handles:
- Both single files and directories
- Relative or absolute internal paths
- Maximum compression levels (-9 / ultra)
- Excluding bulky junk (node_modules, .git, .DS_Store, __pycache__, .venv)
- Smart image/media optimization (resampling and compressing photos to fit under target size)
- Multi-part volumes that ALWAYS retain the chosen extension (e.g. NZ_part01.zip, NZ_part02.zip)
- Standalone independent archives for folders so each part can be opened directly
"""

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from typing import Dict, Any, Optional, List, Tuple


def get_path_size(path: str) -> int:
    """Calculate total size of a file or directory in bytes."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return 0
    if os.path.isfile(path) or os.path.islink(path):
        return os.path.getsize(path)

    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp) and os.path.exists(fp):
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return total


def format_bytes(size_bytes: int) -> str:
    """Format bytes into human-readable string (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_default_extension(fmt: str) -> str:
    """Return standard file extension for a compression format."""
    fmt = fmt.lower().strip()
    mapping = {
        "zip": ".zip",
        "tar.gz": ".tar.gz",
        "tar.bz2": ".tar.bz2",
        "tar.xz": ".tar.xz",
        "dmg": ".dmg",
    }
    return mapping.get(fmt, f".{fmt}")


def strip_known_extension(path: str) -> str:
    """Strip known archive extensions from a file path."""
    cur_lower = path.lower()
    known_exts = [".tar.gz", ".tar.bz2", ".tar.xz", ".zip", ".dmg"]
    for k_ext in known_exts:
        if cur_lower.endswith(k_ext):
            return path[:-len(k_ext)]
    # Fallback standard extension strip
    root, _ = os.path.splitext(path)
    return root or path


def build_output_path(source: str, output: Optional[str], fmt: str) -> str:
    """
    Generate appropriate output path if output is empty or a directory.
    Ensures output ends with the correct extension for the chosen format.
    """
    source = os.path.abspath(os.path.expanduser(source))
    ext = get_default_extension(fmt)
    base_name = os.path.basename(source.rstrip(os.sep))
    if not base_name:
        base_name = "archive"

    if os.path.isfile(source):
        base_name = strip_known_extension(base_name)

    if not output or not output.strip():
        parent_dir = os.path.dirname(source)
        return os.path.join(parent_dir, f"{base_name}{ext}")

    output = os.path.abspath(os.path.expanduser(output.strip()))
    if os.path.isdir(output) or output.endswith(os.sep):
        return os.path.join(output, f"{base_name}{ext}")

    base_without_ext = strip_known_extension(output)
    return f"{base_without_ext}{ext}"


def get_part_path(base_output_path: str, part_num: int, fmt: str) -> str:
    """
    Constructs a part filename that ALWAYS ends with the chosen archive extension.
    Example:
      NZ.zip, part 1 -> NZ_part01.zip
      archive.tar.gz, part 2 -> archive_part02.tar.gz
    """
    ext = get_default_extension(fmt)
    base_without_ext = strip_known_extension(base_output_path)
    return f"{base_without_ext}_part{part_num:02d}{ext}"


def split_file(file_path: str, max_chunk_bytes: int, fmt: str = "zip") -> List[str]:
    """
    Split a binary file into parts each strictly <= max_chunk_bytes,
    with every part ending in the chosen extension (e.g. NZ_part01.zip, NZ_part02.zip).
    """
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        return []

    size = os.path.getsize(file_path)
    if size <= max_chunk_bytes:
        return [file_path]

    parts: List[str] = []
    chunk_num = 1
    with open(file_path, "rb") as f_in:
        while True:
            chunk = f_in.read(max_chunk_bytes)
            if not chunk:
                break
            part_name = get_part_path(file_path, chunk_num, fmt)
            with open(part_name, "wb") as f_out:
                f_out.write(chunk)
            parts.append(part_name)
            chunk_num += 1

    return parts


def optimize_tree_images(source_dir: str, max_dim: int = 1920, quality: int = 70) -> str:
    """
    Creates an optimized temporary copy of source_dir where images (JPG, PNG, HEIC)
    are resampled and compressed using macOS native sips to drastically shrink size.
    Returns path to temporary directory.
    """
    temp_dir = tempfile.mkdtemp(prefix="opt_media_")
    img_exts = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
    for root, dirs, files in os.walk(source_dir):
        rel_root = os.path.relpath(root, source_dir)
        dest_root = os.path.join(temp_dir, rel_root) if rel_root != "." else temp_dir
        os.makedirs(dest_root, exist_ok=True)
        for f in files:
            src_file = os.path.join(root, f)
            dest_file = os.path.join(dest_root, f)
            _, ext = os.path.splitext(f.lower())
            if ext in img_exts and sys.platform == "darwin":
                cmd = ["sips", "-s", "formatOptions", str(quality), "--resampleHeightWidthMax", str(max_dim), src_file, "--out", dest_file]
                res = subprocess.run(cmd, capture_output=True)
                if res.returncode != 0 or not os.path.exists(dest_file):
                    shutil.copy2(src_file, dest_file)
            else:
                shutil.copy2(src_file, dest_file)
    return temp_dir


def create_standalone_volume_archives(
    source_dir: str,
    output_path: str,
    fmt: str,
    max_chunk_bytes: int,
    exclude_junk: bool = False,
) -> Optional[List[str]]:
    """
    Groups files in source_dir into multiple independent, valid standalone archives
    where each part ends in the target extension (e.g. NZ_part01.zip, NZ_part02.zip)
    and strictly stays <= max_chunk_bytes.
    Returns list of part file paths, or None if a single file alone exceeds max_chunk_bytes.
    """
    junk_patterns = {".git", "node_modules", ".ds_store", "__pycache__", ".venv", "venv", ".cache"}
    all_files: List[Tuple[str, str, int]] = []

    for root, _, files in os.walk(source_dir):
        rel_root = os.path.relpath(root, source_dir)
        if exclude_junk:
            parts_lower = [p.lower() for p in rel_root.split(os.sep)]
            if any(j in parts_lower for j in junk_patterns):
                continue

        for f in sorted(files):
            if exclude_junk and f.lower() in junk_patterns:
                continue
            fp = os.path.join(root, f)
            if os.path.islink(fp) or not os.path.exists(fp):
                continue
            rel = os.path.relpath(fp, source_dir)
            sz = os.path.getsize(fp)
            if sz > max_chunk_bytes:
                # A single individual file is larger than the entire budget;
                # cannot create standalone volume per file, fallback to binary split
                return None
            all_files.append((fp, rel, sz))

    if not all_files:
        return None

    # Group files into batches targeting max_chunk_bytes
    batches: List[List[Tuple[str, str]]] = []
    cur_batch: List[Tuple[str, str]] = []
    cur_size = 0

    for fp, rel, sz in all_files:
        if cur_size + sz > max_chunk_bytes and cur_batch:
            batches.append(cur_batch)
            cur_batch = []
            cur_size = 0
        cur_batch.append((fp, rel))
        cur_size += sz
    if cur_batch:
        batches.append(cur_batch)

    if len(batches) <= 1:
        return None

    part_paths: List[str] = []

    for idx, batch in enumerate(batches, 1):
        part_name = get_part_path(output_path, idx, fmt)
        if os.path.exists(part_name):
            os.remove(part_name)

        if fmt == "zip":
            with zipfile.ZipFile(part_name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                for fp, rel in batch:
                    zf.write(fp, rel)
        elif fmt in ["tar.gz", "tar.bz2", "tar.xz"]:
            mode_map = {
                "tar.gz": "w:gz",
                "tar.bz2": "w:bz2",
                "tar.xz": "w:xz",
            }
            mode = mode_map.get(fmt, "w:gz")
            with tarfile.open(part_name, mode) as tf:
                for fp, rel in batch:
                    tf.add(fp, arcname=rel)
        else:
            return None

        # Verify size
        if os.path.getsize(part_name) > max_chunk_bytes:
            # Compressed size still somehow exceeded budget
            for p in part_paths:
                if os.path.exists(p): os.remove(p)
            if os.path.exists(part_name): os.remove(part_name)
            return None

        part_paths.append(part_name)

    return part_paths


def compress(
    source: str,
    output: Optional[str] = None,
    fmt: str = "zip",
    relative: bool = True,
    overwrite: bool = True,
    max_compression: bool = True,
    exclude_junk: bool = False,
    target_size_mb: Optional[float] = None,
    split_if_exceeds: bool = True,
    optimize_media: bool = False,
) -> Dict[str, Any]:
    """
    Compress a file or folder into specified format with size optimization.
    Multi-part archives ALWAYS end with the chosen extension (e.g. NZ_part01.zip, NZ_part02.zip).
    """
    start_time = time.time()
    source = os.path.abspath(os.path.expanduser(source))

    if not os.path.exists(source):
        return {
            "success": False,
            "error": f"Source path does not exist: {source}",
            "source": source,
            "output": output or "",
            "format": fmt,
        }

    fmt = fmt.lower().strip()
    supported_formats = ["zip", "tar.gz", "tar.bz2", "tar.xz", "dmg"]
    if fmt not in supported_formats:
        return {
            "success": False,
            "error": f"Unsupported format '{fmt}'. Must be one of: {', '.join(supported_formats)}",
            "source": source,
            "output": output or "",
            "format": fmt,
        }

    output_path = build_output_path(source, output, fmt)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Clean existing file and existing part files
    if overwrite:
        try:
            if os.path.exists(output_path):
                if os.path.isdir(output_path):
                    shutil.rmtree(output_path)
                else:
                    os.remove(output_path)
            base_dir = os.path.dirname(output_path)
            base_prefix = os.path.basename(strip_known_extension(output_path))
            for f in os.listdir(base_dir):
                if f.startswith(f"{base_prefix}_part") or f.startswith(f"{base_prefix}.zip.part"):
                    try:
                        os.remove(os.path.join(base_dir, f))
                    except OSError:
                        pass
        except Exception as e:
            return {
                "success": False,
                "error": f"Could not clean existing output at '{output_path}': {e}",
                "source": source,
                "output": output_path,
                "format": fmt,
            }
    elif os.path.exists(output_path):
        return {
            "success": False,
            "error": f"Output file already exists: {output_path}",
            "source": source,
            "output": output_path,
            "format": fmt,
        }

    original_size = get_path_size(source)
    is_dir = os.path.isdir(source)
    source_parent = os.path.dirname(source)
    source_name = os.path.basename(source.rstrip(os.sep))

    # Media optimization if requested for directory
    media_optimized = False
    temp_opt_dir = None
    working_source = source

    if optimize_media and is_dir and sys.platform == "darwin":
        try:
            temp_opt_dir = optimize_tree_images(source, max_dim=1920, quality=70)
            working_source = temp_opt_dir
            media_optimized = True
        except Exception:
            pass

    # Target size budget calculation
    target_bytes = int(target_size_mb * 1024 * 1024) if target_size_mb else None
    chunk_budget = max(1024 * 1024, target_bytes - (500 * 1024)) if target_bytes else None

    # Check if folder should be packed into standalone volume archives directly
    if is_dir and target_bytes and split_if_exceeds and fmt in ["zip", "tar.gz", "tar.bz2", "tar.xz"]:
        # If original uncompressed size is clearly greater than target
        estimated_source_size = get_path_size(working_source)
        if estimated_source_size > target_bytes:
            standalone_parts = create_standalone_volume_archives(
                source_dir=working_source,
                output_path=output_path,
                fmt=fmt,
                max_chunk_bytes=chunk_budget,
                exclude_junk=exclude_junk,
            )
            if standalone_parts and len(standalone_parts) > 1:
                if temp_opt_dir and os.path.exists(temp_opt_dir):
                    shutil.rmtree(temp_opt_dir, ignore_errors=True)

                duration = time.time() - start_time
                parts_info: List[Dict[str, Any]] = []
                total_comp_size = 0
                for p in standalone_parts:
                    p_size = os.path.getsize(p)
                    total_comp_size += p_size
                    parts_info.append({
                        "path": p,
                        "filename": os.path.basename(p),
                        "size_bytes": p_size,
                        "size_formatted": format_bytes(p_size),
                    })
                saved_bytes = max(0, original_size - total_comp_size)
                saved_percentage = (saved_bytes / original_size * 100) if original_size > 0 else 0.0

                return {
                    "success": True,
                    "source": source,
                    "output": standalone_parts[0],
                    "filename": os.path.basename(standalone_parts[0]),
                    "format": fmt,
                    "original_size": original_size,
                    "compressed_size": total_comp_size,
                    "original_size_formatted": format_bytes(original_size),
                    "compressed_size_formatted": format_bytes(total_comp_size),
                    "saved_bytes": saved_bytes,
                    "saved_bytes_formatted": format_bytes(saved_bytes),
                    "saved_percentage": round(saved_percentage, 1),
                    "duration_seconds": round(duration, 2),
                    "command": f"Built {len(standalone_parts)} independent {fmt.upper()} archives",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "target_size_mb": target_size_mb,
                    "target_size_bytes": target_bytes,
                    "is_under_target": True,
                    "is_split": True,
                    "standalone_parts": True,
                    "parts": parts_info,
                    "join_command": "",  # Independent archives need NO join command!
                    "media_optimized": media_optimized,
                }

    # Standard compression flow
    cmd: List[str] = []
    cwd: Optional[str] = None
    env = os.environ.copy()
    temp_dmg_src = None

    if max_compression:
        env["GZIP"] = "-9"
        env["BZIP2"] = "-9"
        env["XZ_OPT"] = "-9"

    junk_patterns = [
        ".git",
        "node_modules",
        ".DS_Store",
        "__pycache__",
        "*.pyc",
        ".venv",
        "venv",
        ".cache",
    ]

    if fmt == "zip":
        cmd = ["zip"]
        if max_compression:
            cmd.append("-9")
        cmd.append("-q")

        if relative:
            if is_dir:
                cmd.extend(["-r", output_path, "."])
                cwd = working_source
            else:
                cmd.extend([output_path, source_name])
                cwd = source_parent
        else:
            cmd.extend(["-r", output_path, working_source])

        if exclude_junk and is_dir:
            cmd.append("-x")
            for pat in junk_patterns:
                cmd.append(f"*/{pat}/*")
                cmd.append(f"*/{pat}")

    elif fmt in ["tar.gz", "tar.bz2", "tar.xz"]:
        flag_map = {
            "tar.gz": "-czf",
            "tar.bz2": "-cjf",
            "tar.xz": "-cJf",
        }
        tar_flag = flag_map[fmt]
        cmd = ["tar", tar_flag, output_path]

        if exclude_junk and is_dir:
            for pat in junk_patterns:
                cmd.append(f"--exclude={pat}")

        if relative:
            if is_dir:
                cmd.extend(["-C", working_source, "."])
            else:
                cmd.extend(["-C", source_parent, source_name])
        else:
            cmd.append(working_source)

    elif fmt == "dmg":
        if sys.platform != "darwin":
            return {
                "success": False,
                "error": "DMG creation is only supported on macOS",
                "source": source,
                "output": output_path,
                "format": fmt,
            }

        try:
            if not is_dir:
                temp_dmg_src = tempfile.mkdtemp(prefix="dmg_wrap_")
                shutil.copy2(source, os.path.join(temp_dmg_src, source_name))
                dmg_src = temp_dmg_src
            else:
                dmg_src = working_source

            base_dmg = strip_known_extension(output_path)
            final_dmg = base_dmg + ".dmg"
            cmd = ["hdiutil", "create", "-ov", "-format", "UDZO", "-srcfolder", dmg_src, final_dmg]
            output_path = final_dmg
        except Exception as e:
            if temp_dmg_src and os.path.exists(temp_dmg_src):
                shutil.rmtree(temp_dmg_src, ignore_errors=True)
            return {
                "success": False,
                "error": f"Failed to prepare DMG source: {e}",
                "source": source,
                "output": output_path,
                "format": fmt,
            }

    try:
        proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
            if fmt == "dmg" and "Directory not empty" in err_msg:
                err_msg += " (macOS sandbox or missing permissions. Use ZIP or TAR formats instead)."
            return {
                "success": False,
                "error": f"Compression failed: {err_msg}",
                "source": source,
                "output": output_path,
                "format": fmt,
                "command": " ".join(cmd),
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution error: {e}",
            "source": source,
            "output": output_path,
            "format": fmt,
            "command": " ".join(cmd) if cmd else "",
        }
    finally:
        if temp_dmg_src and os.path.exists(temp_dmg_src):
            shutil.rmtree(temp_dmg_src, ignore_errors=True)
        if temp_opt_dir and os.path.exists(temp_opt_dir):
            shutil.rmtree(temp_opt_dir, ignore_errors=True)

    if not os.path.exists(output_path):
        return {
            "success": False,
            "error": f"Output file was not created: {output_path}",
            "source": source,
            "output": output_path,
            "format": fmt,
        }

    duration = time.time() - start_time
    compressed_size = os.path.getsize(output_path)
    saved_bytes = max(0, original_size - compressed_size)
    saved_percentage = (saved_bytes / original_size * 100) if original_size > 0 else 0.0

    is_under_target = (compressed_size <= target_bytes) if target_bytes else True
    is_split = False
    parts_info: List[Dict[str, Any]] = []
    join_command = ""

    # Binary split if compressed archive still exceeds budget
    if target_bytes and compressed_size > target_bytes and split_if_exceeds:
        raw_parts = split_file(output_path, chunk_budget, fmt=fmt)
        if len(raw_parts) > 1:
            is_split = True
            for p in raw_parts:
                p_size = os.path.getsize(p)
                parts_info.append({
                    "path": p,
                    "filename": os.path.basename(p),
                    "size_bytes": p_size,
                    "size_formatted": format_bytes(p_size),
                })
            base_clean = os.path.basename(strip_known_extension(output_path))
            ext = get_default_extension(fmt)
            join_command = f'cat "{base_clean}_part"*{ext} > "{base_clean}{ext}"'

    return {
        "success": True,
        "source": source,
        "output": output_path,
        "filename": os.path.basename(output_path),
        "format": fmt,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "original_size_formatted": format_bytes(original_size),
        "compressed_size_formatted": format_bytes(compressed_size),
        "saved_bytes": saved_bytes,
        "saved_bytes_formatted": format_bytes(saved_bytes),
        "saved_percentage": round(saved_percentage, 1),
        "duration_seconds": round(duration, 2),
        "command": " ".join(cmd),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_size_mb": target_size_mb,
        "target_size_bytes": target_bytes,
        "is_under_target": is_under_target,
        "is_split": is_split,
        "standalone_parts": False,
        "parts": parts_info,
        "join_command": join_command,
        "media_optimized": media_optimized,
    }
