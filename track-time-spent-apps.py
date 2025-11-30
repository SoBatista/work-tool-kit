#!/usr/bin/env python3
import subprocess
import time
import datetime
import json
import os
import shutil
import sys
import argparse

CHECK_INTERVAL_SECONDS = 2
STATS_FILE = "activity_stats.json"

# Ignore file managers only
IGNORE_CLASSES = {
    "Nemo", "nemo",
    "Nautilus", "nautilus",
    "Thunar", "thunar",
    "Caja", "caja",
    "Pcmanfm", "pcmanfm",
}

REQUIRED_BINARIES = ["xdotool", "xprop"]


# -----------------------------
# REQUIREMENTS
# -----------------------------

def check_requirements():
    missing = [b for b in REQUIRED_BINARIES if shutil.which(b) is None]

    if not missing:
        return

    print("[!] Missing required tools:", ", ".join(missing))
    choice = input("[?] Install missing tools with apt? [Y/n]: ").strip().lower()
    if choice == "n":
        print("[!] Cannot continue without installing requirements.")
        sys.exit(1)

    try:
        print("[*] Updating package lists...")
        subprocess.run(["sudo", "apt", "update"], check=True)
        print("[*] Installing:", " ".join(missing))
        subprocess.run(["sudo", "apt", "install", "-y"] + missing, check=True)
        print("[+] Requirements installed.")
    except subprocess.CalledProcessError:
        print("[!] Failed to install requirements. Please install manually:")
        print("    sudo apt install " + " ".join(missing))
        sys.exit(1)


# -----------------------------
# HELPERS
# -----------------------------

def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except subprocess.CalledProcessError:
        return ""


def get_active_window_id():
    return run_cmd(["xdotool", "getactivewindow"])


def get_window_title(wid: str) -> str:
    if not wid:
        return ""
    return run_cmd(["xdotool", "getwindowname", wid])


def get_window_class(wid: str) -> str:
    """
    Use xprop to get WM_CLASS, parse last quoted string.
    Example output:
        WM_CLASS(STRING) = "Parrot-terminal", "Parrot Terminal"
    We'll take the last quoted field: Parrot Terminal
    """
    if not wid:
        return ""
    out = run_cmd(["xprop", "-id", wid, "WM_CLASS"])
    if "WM_CLASS" not in out:
        return ""
    # Split by quotes and take last non-empty quoted chunk
    parts = out.split('"')
    # parts looks like: ['WM_CLASS(STRING) = ', 'Parrot-terminal', ', ', 'Parrot Terminal', '']
    # Take the last non-empty quoted string
    quoted = [p for p in parts[1::2] if p.strip()]
    if not quoted:
        return ""
    return quoted[-1]


def normalize_label(wm_class: str, title: str) -> str | None:
    if not wm_class:
        return None
    if wm_class in IGNORE_CLASSES:
        return None

    app = wm_class.lower()
    clean_title = title.strip()

    # Trim common browser suffixes
    if " - Mozilla Firefox" in clean_title:
        clean_title = clean_title.replace(" - Mozilla Firefox", "")
    if " - Google Chrome" in clean_title:
        clean_title = clean_title.replace(" - Google Chrome", "")

    if len(clean_title) > 60:
        clean_title = clean_title[:57] + "..."

    if not clean_title:
        clean_title = "(no title)"

    return f"{app}: {clean_title}"


def load_stats(path: str) -> dict:
    if not os.path.exists(path):
        return {"per_day": {}}
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"per_day": {}}


def save_stats(path: str, stats: dict):
    with open(path, "w") as f:
        json.dump(stats, f, indent=2)


def format_duration(seconds: int) -> str:
    return str(datetime.timedelta(seconds=int(seconds)))


# -----------------------------
# MAIN
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description="Desktop activity tracker")
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose debug output (window IDs, wm_class, titles)")
    args = parser.parse_args()

    DEBUG_MODE = args.debug

    check_requirements()

    stats = load_stats(STATS_FILE)
    per_day = stats.get("per_day", {})

    print("[*] Desktop activity tracker started.")
    print(f"[*] Ignoring window classes: {sorted(IGNORE_CLASSES)}")
    if DEBUG_MODE:
        print("[*] Debug mode enabled.")
    print("[*] Press Ctrl+C to stop.\n")

    try:
        while True:
            today = datetime.date.today().isoformat()
            if today not in per_day:
                per_day[today] = {}

            wid = get_active_window_id()
            wm_class = get_window_class(wid)
            title = get_window_title(wid)
            label = normalize_label(wm_class, title)

            # DEBUG only printed when --debug is used
            if DEBUG_MODE:
                print(f"[DEBUG] wid={wid!r}, wm_class={wm_class!r}, title={title!r}, label={label!r}")

            if label is not None:
                per_day[today].setdefault(label, 0)
                per_day[today][label] += CHECK_INTERVAL_SECONDS

            now_str = datetime.datetime.now().strftime("%H:%M:%S")

            if label is None:
                current_label = "(ignored)"
                current_time = "0:00:00"
            else:
                current_label = label
                current_time = format_duration(per_day[today][label])

            today_total_secs = sum(per_day[today].values())
            today_total_str = format_duration(today_total_secs)

            # Clean live status line (no debug spam)
            print(
                f"[{now_str}] Active: {current_label[:60]:60} | "
                f"Current: {current_time:>8} | Today total: {today_total_str:>8}",
                end="\r",
                flush=True
            )

            time.sleep(CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n[*] Stopping and saving stats...")

    stats["per_day"] = per_day
    stats["last_updated"] = datetime.datetime.now().isoformat()
    save_stats(STATS_FILE, stats)

    print("[*] Per-day breakdown (summary):")
    for day, buckets in sorted(per_day.items()):
        total = sum(buckets.values())
        print(f"  {day} (total {format_duration(total)}):")
        top = sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)[:5]
        for label, secs in top:
            print(f"    - {label}: {format_duration(secs)}")
    print(f"[*] Full stats saved to {STATS_FILE}")

if __name__ == "__main__":
    main()

