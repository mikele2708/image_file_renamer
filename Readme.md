# 📷 Image File Renamer

A lightweight command-line tool that renames **JPG, JPEG, and NEF** image files based on their **EXIF capture date**, turning cryptic camera-generated names like `IMG_4823.JPG` into human-readable timestamps like `20231015_143205.JPG`.

---

## Features

- Reads EXIF metadata to determine the actual capture date
- Picks the **earliest** available date from `DateTimeOriginal`, `DateTimeDigitized`, or `DateTime`
- Avoids overwriting existing files by appending a numeric suffix (`_1`, `_2`, …)
- Processes directories **recursively**
- **Dry-run mode** to preview changes safely before applying them
- Skips files that do not match known camera-generated filename prefixes
- Cross-platform: works on Windows, macOS, and Linux

---

## Supported File Types

| Extension | Description          |
|-----------|----------------------|
| `.jpg`    | JPEG image           |
| `.jpeg`   | JPEG image           |
| `.nef`    | Nikon RAW image      |

---

## Filename Patterns Processed

Only files whose names begin with one of the following well-known camera prefixes are renamed. All other files are left untouched.

`IMG`, `CIMG`, `P10`, `DSC`, `CSC`, `_DSC`, `DSCN`, `DSCF`

---

## Output Format

```
YYYYMMDD_HHMMSS.EXT
```

If a file with the same timestamp already exists in the same folder, a counter is appended:

```
20231015_143205.JPG
20231015_143205_1.JPG
20231015_143205_2.JPG
```

---

## Requirements

- Python 3.10 or higher
- [`exifread`](https://pypi.org/project/ExifRead/)

Install the dependency with:

```bash
pip install exifread
```

---

## Usage

```bash
python image_file_renamer.py SOURCE_DIR [--dry-run] [--verbose]
```

### Arguments

| Argument         | Description                                                              |
|------------------|--------------------------------------------------------------------------|
| `SOURCE_DIR`     | Root directory to search for image files (searched recursively)          |
| `--dry-run`      | Preview what would be renamed without modifying any files                |
| `--verbose`, `-v`| Show detailed output including skipped files and debug information       |

### Examples

**Preview changes without renaming anything:**
```bash
python image_file_renamer.py /path/to/photos --dry-run
```

**Rename all matching files:**
```bash
python image_file_renamer.py /path/to/photos
```

**Rename with detailed output:**
```bash
python image_file_renamer.py /path/to/photos --verbose
```

---

## How It Works

1. The tool walks the source directory recursively.
2. For each file with a supported extension and a known camera prefix, it opens the file and reads its EXIF metadata using `exifread`.
3. It selects the earliest available date from the three standard EXIF date tags.
4. It constructs a new filename in `YYYYMMDD_HHMMSS.EXT` format.
5. If the file is not already correctly named, it is renamed in place (no files are moved between directories).
6. If a naming collision occurs, a numeric suffix is added automatically.

---

## Notes

- Files are renamed **in place** – they stay in their original subdirectory.
- Files without readable EXIF date information are skipped with a warning.
- Files already matching the target naming format are skipped silently.
- The tool does **not** delete, copy, or move any files.

---

## License

MIT License – feel free to use, modify, and distribute.