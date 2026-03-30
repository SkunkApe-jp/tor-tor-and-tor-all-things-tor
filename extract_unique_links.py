#!/usr/bin/env python3
"""
extract_unique_links.py
=======================
Scans a directory recursively for .txt files, extracts all HTTP/HTTPS URLs,
deduplicates them, and computes the set of URLs not already present in a
targets.yaml file.

Usage
-----
    python extract_unique_links.py [OPTIONS]

Options
-------
    --links-dir PATH        Directory to scan for .txt files.
                            Default: discovered_links
    --targets PATH          Path to existing targets.yaml.
                            Default: targets.yaml
    --output PATH           File to write new/unique URLs into.
                            Default: new_links.txt
    --append-to-targets     Append unique URLs to targets.yaml (list-of-strings
                            format). Falls back to --output if incompatible.
    --dry-run               Print what would be written; do not modify files.
    --resume-log PATH       Log file to track processed URLs for resume support.
                            Default: config/resume_log.txt
    --verbose               Print progress, file counts, and URL counts.

Examples
--------
    # Basic usage — scan ./discovered_links, diff against ./targets.yaml
    python extract_unique_links.py

    # Custom paths
    python extract_unique_links.py --links-dir scraped_data --targets ../targets.yaml --output unique.txt

    # Append directly into targets.yaml
    python extract_unique_links.py --append-to-targets --verbose

    # Dry-run: preview without touching any files
    python extract_unique_links.py --dry-run --verbose
"""

import argparse
import os
import re
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Generator, Iterable, List, Optional, Set

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Robust URL regex — handles query strings, fragments, trailing punctuation.
# Intentionally conservative about what counts as a URL terminator so that
# URLs embedded inside brackets / quotes are captured cleanly.
_URL_RE = re.compile(
    r"https?://"  # scheme
    r"[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"  # everything valid in a URL
    r"(?<![.,;:!?\"')>\]}])",  # strip common trailing punctuation
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# URL extraction helpers
# ---------------------------------------------------------------------------


def extract_urls_from_line(line: str) -> List[str]:
    """Return all HTTP/HTTPS URLs found on a single line."""
    return _URL_RE.findall(line)


def extract_urls_from_file(
    path: Path, verbose: bool = False
) -> Generator[str, None, None]:
    """
    Stream URLs from a single file line-by-line.
    Skips unreadable files gracefully.
    """
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                for url in extract_urls_from_line(line):
                    yield url
    except (OSError, PermissionError) as exc:
        if verbose:
            print(f"  [SKIP] Cannot read {path}: {exc}", file=sys.stderr)


def scan_directory(
    directory: Path, verbose: bool = False, pattern: str = "*_links.txt"
) -> Generator[str, None, None]:
    """
    Recursively walk *directory*, yielding every URL found in every file
    matching *pattern* (default: *_links.txt — onion link files only).
    Gracefully handles missing directories.
    """
    if not directory.exists():
        print(f"[WARN] Links directory not found: {directory}", file=sys.stderr)
        return
    if not directory.is_dir():
        print(f"[WARN] Not a directory: {directory}", file=sys.stderr)
        return

    txt_files = sorted(directory.rglob(pattern))
    if verbose:
        print(f"[INFO] Found {len(txt_files)} '{pattern}' file(s) under {directory}")

    for i, path in enumerate(txt_files, 1):
        if verbose:
            print(f"  [{i}/{len(txt_files)}] Scanning {path.relative_to(directory)}")
        yield from extract_urls_from_file(path, verbose=verbose)


def collect_unique_urls(url_stream: Iterable[str]) -> List[str]:
    """
    Consume a URL stream and return an ordered, deduplicated list
    (first-appearance order preserved).
    """
    seen: Set[str] = set()
    result: List[str] = []
    for url in url_stream:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


# ---------------------------------------------------------------------------
# Resume log helpers
# ---------------------------------------------------------------------------


def load_resume_log(path: Path, verbose: bool = False) -> Set[str]:
    """
    Load URLs from the resume log file.
    """
    if not path.exists():
        if verbose:
            print(f"[INFO] Resume log not found: {path}")
        return set()
    try:
        urls = set()
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.add(line)
        if verbose:
            print(f"[INFO] Loaded {len(urls)} URL(s) from resume log")
        return urls
    except (OSError, PermissionError) as exc:
        if verbose:
            print(f"[WARN] Could not read resume log: {exc}")
        return set()


def save_resume_log(urls: Set[str], path: Path, verbose: bool = False) -> None:
    """
    Save processed URLs to the resume log file.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"# Saved at {datetime.now().isoformat()}\n")
            for url in sorted(urls):
                fh.write(f"{url}\n")
        if verbose:
            print(f"[OK] Saved {len(urls)} URL(s) to resume log: {path}")
    except (OSError, PermissionError) as exc:
        print(f"[ERROR] Could not write resume log: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# targets.yaml helpers
# ---------------------------------------------------------------------------


def _try_import_yaml():
    """Import PyYAML or fall back to a minimal line-based parser."""
    try:
        import yaml  # type: ignore

        return yaml
    except ImportError:
        return None


def _extract_urls_from_value(value, results: Set[str]) -> None:
    """
    Recursively walk any YAML value (dict / list / str) and collect URL strings.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("http://") or stripped.startswith("https://"):
            results.add(stripped)
        # Also try regex in case URL is embedded in a longer string
        for url in extract_urls_from_line(stripped):
            results.add(url)
    elif isinstance(value, list):
        for item in value:
            _extract_urls_from_value(item, results)
    elif isinstance(value, dict):
        for v in value.values():
            _extract_urls_from_value(v, results)


def _fallback_yaml_urls(path: Path) -> Set[str]:
    """
    Minimal line-based fallback when PyYAML is not installed.
    Extracts any line that looks like a URL (possibly prefixed with '- ').
    """
    results: Set[str] = set()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip().lstrip("- ").strip()
                if line.startswith("http://") or line.startswith("https://"):
                    results.add(line)
                else:
                    for url in extract_urls_from_line(line):
                        results.add(url)
    except (OSError, PermissionError) as exc:
        print(f"[WARN] Cannot read {path}: {exc}", file=sys.stderr)
    return results


def load_existing_targets(path: Path, verbose: bool = False) -> Set[str]:
    """
    Load targets.yaml and return a set of all URLs found within it.
    Supports: top-level list of strings, nested mappings, arbitrary YAML shapes.
    Falls back to line-based parsing if PyYAML is not available.
    """
    if not path.exists():
        if verbose:
            print(f"[INFO] targets.yaml not found at {path} — treating as empty.")
        return set()

    yaml = _try_import_yaml()
    results: Set[str] = set()

    if yaml is None:
        print(
            "[WARN] PyYAML not installed. Using fallback line-based parser for targets.yaml.\n"
            "       Install with: pip install pyyaml",
            file=sys.stderr,
        )
        results = _fallback_yaml_urls(path)
    else:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                data = yaml.safe_load(fh)
            _extract_urls_from_value(data, results)
        except Exception as exc:  # yaml.YAMLError or any IO error
            print(
                f"[WARN] Could not parse {path} as YAML: {exc}. Using fallback.",
                file=sys.stderr,
            )
            results = _fallback_yaml_urls(path)

    if verbose:
        print(f"[INFO] Loaded {len(results)} existing URL(s) from {path}")
    return results


# ---------------------------------------------------------------------------
# YAML append helper
# ---------------------------------------------------------------------------


def _is_yaml_list_of_strings(path: Path) -> bool:
    """
    Return True only if the YAML file is a top-level list of strings
    (the only shape we can safely append to).
    """
    yaml = _try_import_yaml()
    if yaml is None:
        # Fallback: check if every non-comment, non-empty line starts with '- '
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or stripped == "urls:":
                        continue
                    if not stripped.startswith("- "):
                        return False
            return True
        except (OSError, PermissionError):
            return False
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return isinstance(data, list) and all(isinstance(x, str) for x in data)
    except Exception:
        return False


def append_to_targets(
    urls: List[str],
    targets_path: Path,
    output_path: Path,
    dry_run: bool,
    verbose: bool,
) -> None:
    """
    Append *urls* to targets.yaml if it is a simple list of strings.
    On incompatible structure, fall back to writing output_path and warn.
    """
    if targets_path.exists() and not _is_yaml_list_of_strings(targets_path):
        print(
            f"[WARN] {targets_path} is not a simple list-of-strings YAML. "
            f"Falling back to writing {output_path}.",
            file=sys.stderr,
        )
        write_output(urls, output_path, dry_run=dry_run, verbose=verbose)
        return

    lines_to_add = ["- " + url + "\n" for url in urls]

    if dry_run:
        print(f"\n[DRY-RUN] Would append {len(urls)} URL(s) to {targets_path}:")
        for line in lines_to_add[:20]:
            print("  " + line, end="")
        if len(lines_to_add) > 20:
            print(f"  ... and {len(lines_to_add) - 20} more.")
        return

    try:
        with targets_path.open("a", encoding="utf-8") as fh:
            fh.writelines(lines_to_add)
        if verbose:
            print(f"[OK] Appended {len(urls)} URL(s) to {targets_path}")
    except (OSError, PermissionError) as exc:
        print(f"[ERROR] Could not append to {targets_path}: {exc}", file=sys.stderr)
        print(f"        Falling back to writing {output_path}.", file=sys.stderr)
        write_output(urls, output_path, dry_run=False, verbose=verbose)


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------


def write_output(
    urls: List[str],
    output_path: Path,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Write one URL per line to *output_path*."""
    content = "\n".join(urls) + "\n" if urls else ""

    if dry_run:
        print(f"\n[DRY-RUN] Would write {len(urls)} URL(s) to {output_path}:")
        for url in urls[:20]:
            print("  " + url)
        if len(urls) > 20:
            print(f"  ... and {len(urls) - 20} more.")
        return

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            fh.write(content)
        if verbose:
            print(f"[OK] Wrote {len(urls)} URL(s) to {output_path}")
    except (OSError, PermissionError) as exc:
        print(f"[ERROR] Could not write to {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="extract_unique_links.py",
        description=(
            "Scan .txt files for HTTP/HTTPS URLs, deduplicate them, "
            "diff against targets.yaml, and write truly new URLs to an output file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--links-dir",
        default="scraped_data",
        metavar="PATH",
        help="Directory to scan recursively for .txt files. (default: scraped_data)",
    )
    parser.add_argument(
        "--targets",
        default="targets.yaml",
        metavar="PATH",
        help="Path to existing targets.yaml. (default: targets.yaml)",
    )
    parser.add_argument(
        "--pattern",
        default="*_links.txt",
        metavar="GLOB",
        help="Glob pattern for link files to scan. (default: *_links.txt)",
    )
    parser.add_argument(
        "--output",
        default="new_links.txt",
        metavar="PATH",
        help="Output file for unique new URLs. (default: new_links.txt)",
    )
    parser.add_argument(
        "--append-to-targets",
        action="store_true",
        help="Append unique URLs directly to targets.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview output without writing any files.",
    )
    parser.add_argument(
        "--resume-log",
        default="config/resume_log.txt",
        metavar="PATH",
        help="Log file to track processed URLs for resume support. (default: config/resume_log.txt)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress information.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    links_dir = Path(args.links_dir)
    targets = Path(args.targets)
    output = Path(args.output)
    resume_log = Path(args.resume_log)
    verbose = args.verbose
    dry_run = args.dry_run

    if dry_run and verbose:
        print("[INFO] Dry-run mode — no files will be modified.")

    # -----------------------------------------------------------------------
    # Step 1: Collect all unique URLs from .txt files
    # -----------------------------------------------------------------------
    if verbose:
        print(f"\n[STEP 1] Scanning {links_dir} for URLs...")

    url_stream = scan_directory(links_dir, verbose=verbose, pattern=args.pattern)
    discovered = collect_unique_urls(url_stream)

    if verbose:
        print(f"[INFO] Discovered {len(discovered)} unique URL(s) total.")

    if not discovered:
        print("[INFO] No URLs found in the links directory. Nothing to do.")
        return

    # -----------------------------------------------------------------------
    # Step 2: Load existing targets and resume log
    # -----------------------------------------------------------------------
    if verbose:
        print(f"\n[STEP 2] Loading existing URLs from {targets}...")

    existing = load_existing_targets(targets, verbose=verbose)

    processed = load_resume_log(resume_log, verbose=verbose)

    # -----------------------------------------------------------------------
    # Step 3: Compute difference (preserve order)
    # -----------------------------------------------------------------------
    new_urls = [u for u in discovered if u not in existing and u not in processed]

    if verbose:
        print(f"\n[SUMMARY]")
        print(f"  Discovered     : {len(discovered)}")
        print(f"  Already in targets: {len(existing)}")
        print(f"  Already in resume : {len(processed)}")
        print(f"  New / unique      : {len(new_urls)}")

    if not new_urls:
        print("[INFO] No new URLs found — targets.yaml is already up to date.")
        return

    print(f"\n[RESULT] {len(new_urls)} new URL(s) not yet in {targets}")

    # -----------------------------------------------------------------------
    # Step 4: Write output
    # -----------------------------------------------------------------------
    if args.append_to_targets:
        append_to_targets(new_urls, targets, output, dry_run=dry_run, verbose=verbose)
    else:
        write_output(new_urls, output, dry_run=dry_run, verbose=verbose)
        if not dry_run:
            print(f"[DONE] Written to {output}")

    # -----------------------------------------------------------------------
    # Step 5: Update resume log
    # -----------------------------------------------------------------------
    if not dry_run:
        save_resume_log(set(new_urls), resume_log, verbose=verbose)


if __name__ == "__main__":
    main()
