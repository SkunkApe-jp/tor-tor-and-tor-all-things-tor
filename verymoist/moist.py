#!/usr/bin/env python3
"""
populate_yaml.py

Selects a *single* text file from the `split_output` folder each day,
writes its content into `../targets.yaml`, and cycles through the files
over time. The day‑0 (epoch) can be overridden with `--epoch YYYY-MM-DD`.
"""

# ------------------------------------------------------------
# Standard library
# ------------------------------------------------------------
import argparse
import pathlib
import sys
import datetime

# ------------------------------------------------------------
# Third‑party
# ------------------------------------------------------------
import yaml   # pip install pyyaml


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def write_yaml(data, yaml_path: pathlib.Path) -> None:
    """Dump *data* to *yaml_path* using PyYAML (kept for possible future use)."""
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
        )

def write_raw(text: str, yaml_path: pathlib.Path) -> None:
    """Write *text* verbatim to *yaml_path* (no YAML quoting)."""
    yaml_path.write_text(text, encoding="utf-8")


# ------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------
def main() -> int:
    # --------------------------------------------------------
    # 0️⃣ CLI arguments (epoch override optional)
    # --------------------------------------------------------
    parser = argparse.ArgumentParser(
        description=(
            "Automates the daily selection and copying of a single split-output "
            "text file to targets.yaml, cycling through available files."
        )
    )
    parser.add_argument(
        "--epoch",
        type=lambda d: datetime.datetime.strptime(d, "%Y-%m-%d").date(),
        help=(
            "Date that should be considered day 0 (format YYYY-MM-DD). "
            "If omitted, defaults to 2023-01-01."
        ),
    )
    args = parser.parse_args()
    # If --epoch is not provided, it defaults to 2023-01-01.
    # To start at 001.txt *today*, you must provide --epoch with today's date.
    epoch_date = args.epoch or datetime.date(2026, 2, 20)

    print(f"ℹ️  Using epoch date: {epoch_date.strftime('%Y-%m-%d')}")  # debugging

    # --------------------------------------------------------
    # 1️⃣ Determine relevant paths (relative to this script)
    # --------------------------------------------------------
    script_path = pathlib.Path(__file__).resolve()
    script_dir = script_path.parent                # e.g. /home/kappa/gooseswork
    txt_dir = script_dir / "split_output"
    yaml_path = script_dir.parent / "targets.yaml"

    # --------------------------------------------------------
    # 2️⃣ Sanity checks
    # --------------------------------------------------------
    if not txt_dir.is_dir():
        print(f"❌ Expected folder not found: {txt_dir}", file=sys.stderr)
        return 1

    # --------------------------------------------------------
    # 3️⃣ Pick today’s file
    # --------------------------------------------------------
    file_pattern = "*_part_*.txt"
    all_candidate_files = sorted(txt_dir.glob(file_pattern))

    if not all_candidate_files:
        print(
            f"⚠️ No matching text files in {txt_dir} (pattern {file_pattern}). "
            "Writing an empty targets.yaml."
        )
        write_raw("", yaml_path)   # Empty file, no quoting
        return 0

    total_files = len(all_candidate_files)
    current_date = datetime.date.today()
    days_since_epoch = (current_date - epoch_date).days
    file_index = days_since_epoch % total_files

    print(
        f"✅ {current_date} → picking file "
        f"{all_candidate_files[file_index].name} (index {file_index} from {total_files} files)"
    )

    selected_file = all_candidate_files[file_index]

    # --------------------------------------------------------
    # 4️⃣ Read the file content directly (no dictionary needed)
    # --------------------------------------------------------
    file_content = selected_file.read_text(encoding="utf-8")

    # --------------------------------------------------------
    # 5️⃣ Write (or overwrite) the YAML file – *verbatim* (no stray quotes)
    # --------------------------------------------------------
    write_raw(file_content, yaml_path)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"🗒️  {yaml_path} updated at {now}")
    return 0


# ------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
