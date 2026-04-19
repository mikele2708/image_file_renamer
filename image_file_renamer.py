"""
image_file_renamer.py
---------------------
Renames JPG, JPEG, and NEF image files based on their EXIF capture date.

New filename format: YYYYMMDD_HHMMSS[_N].EXT
  - The optional _N suffix is appended when a file with the same timestamp
    already exists in the same directory.

Only files whose names begin with well-known camera prefixes (e.g. IMG, DSC, …)
are renamed – all other files are left untouched.

Dependencies:
  pip install exifread
"""

import argparse
import logging
import os
import sys
from time import localtime, mktime, strftime, strptime

import exifread

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# File extensions that will be processed (case-insensitive).
SUPPORTED_EXTENSIONS = {"JPG", "JPEG", "NEF"}

# Common camera filename prefixes used to identify auto-generated camera files.
# Comparison is case-insensitive.
CAMERA_PREFIXES = ("IMG", "CIMG", "P10", "DSC", "CSC", "_DSC", "DSCN", "DSCF")

# Expected date/time format used in EXIF tags.
EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

# Directory (relative to the script's working directory) where log files are stored.
LOG_DIR = "log"

# Log filename format: rename_YYYYMMDD_HHMMSS.log
LOG_FILENAME_FORMAT = "rename_%Y%m%d_%H%M%S.log"

# Shared format used for both the console handler and the file handler.
LOG_FORMAT = "%(asctime)s  %(levelname)-8s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

log = logging.getLogger(__name__)


def setup_logging(verbose: bool, write_to_file: bool) -> str | None:
    """
    Configure the root logger with a console handler and, for real runs,
    an additional file handler that writes to the log/ directory.

    Args:
        verbose:       When True, set the log level to DEBUG; otherwise INFO.
        write_to_file: When True, create a timestamped log file in LOG_DIR.

    Returns:
        The path of the log file that was created, or None for dry-run / console-only.
    """
    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Console handler – always active.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=[console_handler])
    log.setLevel(level)

    if not write_to_file:
        return None

    # Create the log directory if it does not exist yet.
    os.makedirs(LOG_DIR, exist_ok=True)

    from time import strftime as _strftime
    log_filename = _strftime(LOG_FILENAME_FORMAT)
    log_path = os.path.join(LOG_DIR, log_filename)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_handler)

    return log_path


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_earliest_exif_date(exif_data: dict) -> str | None:
    """
    Return the earliest available EXIF timestamp from the given tag dictionary.

    Priority order (earliest date wins):
      1. EXIF DateTimeOriginal  – moment the photo was taken (preferred)
      2. EXIF DateTimeDigitized – moment the image was digitised
      3. Image DateTime         – last file modification time stored by the camera

    Returns None if none of the three tags are present or parseable.
    """
    candidates = {
        "EXIF DateTimeOriginal": exif_data.get("EXIF DateTimeOriginal"),
        "EXIF DateTimeDigitized": exif_data.get("EXIF DateTimeDigitized"),
        "Image DateTime": exif_data.get("Image DateTime"),
    }

    parsed_dates = {}
    for tag, value in candidates.items():
        if value is None:
            continue
        try:
            parsed_dates[tag] = strptime(str(value), EXIF_DATE_FORMAT)
        except ValueError:
            log.debug("Unrecognised date format for tag '%s': %s", tag, value)

    if not parsed_dates:
        return None

    # Pick the tag whose parsed date is the earliest point in time.
    earliest_tag = min(parsed_dates, key=lambda t: mktime(parsed_dates[t]))
    return str(candidates[earliest_tag])


def has_camera_prefix(filename_stem: str) -> bool:
    """Return True if the filename stem starts with a known camera prefix."""
    upper = filename_stem.upper()
    return any(upper.startswith(prefix) for prefix in CAMERA_PREFIXES)


def build_new_filename(creation_time_str: str, extension: str) -> str | None:
    """
    Build a new filename in the format YYYYMMDD_HHMMSS.EXT.

    Returns None if the date string cannot be parsed.
    """
    try:
        t = localtime(mktime(strptime(creation_time_str, EXIF_DATE_FORMAT)))
        return strftime("%Y%m%d_%H%M%S", t) + "." + extension
    except ValueError as exc:
        log.warning("Could not parse date string '%s': %s", creation_time_str, exc)
        return None


def find_unique_path(directory: str, filename: str, reserved: set[str]) -> str:
    """
    Return a unique file path inside *directory* for the given *filename*.

    Checks both files that already exist on disk **and** names that have
    already been reserved during the current run (e.g. burst shots from the
    same second that would otherwise all map to the same timestamp).

    If *filename* is already taken, a numeric suffix (_1, _2, …) is appended
    to the stem until a free name is found. The chosen name is added to
    *reserved* so subsequent calls within the same directory are aware of it.

    Args:
        directory: Directory in which the file will be placed.
        filename:  Desired filename (basename only).
        reserved:  Set of lowercase basenames already allocated in this
                   directory during the current run. Modified in-place.
    """
    stem, ext = os.path.splitext(filename)

    # Check the plain timestamp name first.
    candidate_name = filename
    candidate_path = os.path.join(directory, candidate_name)

    if not os.path.exists(candidate_path) and candidate_name.lower() not in reserved:
        reserved.add(candidate_name.lower())
        return candidate_path

    # Append _1, _2, … until a free slot is found.
    counter = 1
    while True:
        candidate_name = f"{stem}_{counter}{ext}"
        candidate_path = os.path.join(directory, candidate_name)
        if not os.path.exists(candidate_path) and candidate_name.lower() not in reserved:
            reserved.add(candidate_name.lower())
            return candidate_path
        counter += 1


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def rename_images(source: str, dry_run: bool = False) -> tuple[int, int]:
    """
    Recursively walk *source* and rename matching image files.

    A file is renamed when:
      - its extension is in SUPPORTED_EXTENSIONS, and
      - its name starts with a known camera prefix, and
      - valid EXIF date information is available.

    Burst shots (multiple frames captured within the same second) are handled
    by a per-directory registry of already-allocated names. The first frame
    gets the plain timestamp (e.g. 20231015_143205.JPG), subsequent frames
    are numbered sequentially (_1, _2, ...).

    Args:
        source:  Root directory to search.
        dry_run: When True, only log what would happen without touching files.

    Returns:
        A tuple (renamed, skipped) with the respective file counts.
    """
    renamed = 0
    skipped = 0

    for root, _dirs, files in os.walk(source, topdown=False):
        # Per-directory registry of names already allocated in this run.
        # Pre-seeded with existing filenames (lowercase) so we never collide
        # with files that are not being renamed.
        reserved: set[str] = {f.lower() for f in files}

        for file in sorted(files):  # sorted for reproducible, predictable order
            stem, raw_ext = os.path.splitext(file)
            extension = raw_ext.lstrip(".").upper()

            # Skip unsupported file types.
            if extension not in SUPPORTED_EXTENSIONS:
                continue

            # Skip files that do not match any known camera prefix.
            if not has_camera_prefix(stem):
                log.debug("Skipped (no camera prefix): %s", file)
                skipped += 1
                continue

            source_path = os.path.join(root, file)

            # Read EXIF tags from the image file.
            try:
                with open(source_path, "rb") as image_file:
                    exif_tags = exifread.process_file(image_file, details=False)
            except OSError as exc:
                log.warning("Could not open file '%s': %s", source_path, exc)
                skipped += 1
                continue

            creation_time_str = get_earliest_exif_date(exif_tags)

            if creation_time_str is None:
                log.warning("No EXIF date found, skipping: %s", file)
                skipped += 1
                continue

            new_filename = build_new_filename(creation_time_str, extension)
            if new_filename is None:
                skipped += 1
                continue

            # Skip files that are already correctly named.
            if file == new_filename:
                log.debug("Already correctly named: %s", file)
                skipped += 1
                continue

            # Allocate a unique name, aware of both on-disk files and names
            # already assigned in this run (handles burst shots from the same second).
            destination_path = find_unique_path(root, new_filename, reserved)

            if dry_run:
                log.info("[DRY-RUN] %s  →  %s", source_path, destination_path)
                renamed += 1
            else:
                try:
                    os.rename(source_path, destination_path)
                    # Release the old name so the slot can be reused within this directory.
                    reserved.discard(file.lower())
                    log.info("Renamed: %s  →  %s", file, os.path.basename(destination_path))
                    renamed += 1
                except OSError as exc:
                    log.error("Rename failed for '%s': %s", source_path, exc)
                    # Roll back the reserved slot so it is not lost.
                    reserved.discard(os.path.basename(destination_path).lower())
                    skipped += 1

    return renamed, skipped


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def get_args() -> argparse.Namespace:
    description = (
        "Rename JPG, JPEG, and NEF files based on their EXIF capture date.\n"
        "Only files with known camera prefixes (IMG, DSC, …) are processed.\n"
        "Files stay in their original directory – only the filename changes."
    )
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "source",
        metavar="SOURCE_DIR",
        type=str,
        help="Root directory containing the files to rename (searched recursively)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without actually changing any files",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output including skipped files and debug information",
    )
    return parser.parse_args()


def main() -> None:
    args = get_args()

    # File logging is only enabled for real runs (not dry-run).
    log_path = setup_logging(verbose=args.verbose, write_to_file=not args.dry_run)

    if not os.path.isdir(args.source):
        log.error("Source directory not found: %s", args.source)
        sys.exit(1)

    if args.dry_run:
        log.info("=== DRY-RUN mode: no files will be modified ===")
    else:
        log.info("Log file: %s", log_path)

    renamed, skipped = rename_images(args.source, dry_run=args.dry_run)

    suffix = " [DRY-RUN]" if args.dry_run else ""
    summary = f"\n✅ Done: {renamed} file(s) renamed, {skipped} skipped.{suffix}"
    print(summary)

    # Write the summary line to the log file as well.
    if log_path:
        log.info("Done: %d file(s) renamed, %d skipped.", renamed, skipped)


if __name__ == "__main__":
    main()