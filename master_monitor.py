#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import datetime
import shutil
import argparse
from typing import List, Dict

# -----------------------------
# Severity levels
# -----------------------------
LEVELS = {
    "info": 1,
    "warning": 2,
    "alert": 3,
}

# ANSI colors (simple)
COLORS = {
    "reset": "\033[0m",
    "info": "\033[36m",      # cyan
    "warning": "\033[33m",   # yellow
    "alert": "\033[31m",     # red
    "section": "\033[35m",   # magenta
    "bold": "\033[1m",
}

AUTH_LOG_PATHS = [
    "/var/log/auth.log",       # Debian/Ubuntu/Mint
    "/var/log/secure",         # RHEL/CentOS
]

# -----------------------------
# Small helper functions
# -----------------------------

def run_cmd(cmd: List[str]) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return ""


def human_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def color_text(text: str, level: str) -> str:
    return COLORS.get(level, "") + text + COLORS["reset"]


def get_auth_log_path() -> str:
    for p in AUTH_LOG_PATHS:
        if os.path.exists(p):
            return p
    return ""


# -----------------------------
# Performance monitoring
# -----------------------------

def get_loadavg():
    try:
        with open("/proc/loadavg", "r") as f:
            parts = f.read().split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return 0.0, 0.0, 0.0


def get_mem_usage():
    """
    Returns (used_pct, total_mb, used_mb)
    """
    try:
        meminfo = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                key, value = line.split(":", 1)
                meminfo[key.strip()] = int(value.strip().split()[0])  # in kB
        total = meminfo.get("MemTotal", 0)
        avail = meminfo.get("MemAvailable", 0)
        used = total - avail
        used_pct = (used / total * 100) if total > 0 else 0
        return used_pct, total / 1024, used / 1024  # in MB
    except Exception:
        return 0.0, 0.0, 0.0


def collect_performance() -> List[Dict]:
    """
    Returns list of {level, message} for performance metrics.
    """
    results = []
    load1, load5, load15 = get_loadavg()
    mem_used_pct, mem_total_mb, mem_used_mb = get_mem_usage()

    # CPU load warning thresholds (very rough)
    # If 1-min load > number of cores, that's suspicious
    try:
        cpu_cores = os.cpu_count() or 1
    except Exception:
        cpu_cores = 1

    # CPU
    msg = f"Load avg (1/5/15): {load1:.2f}, {load5:.2f}, {load15:.2f} | Cores: {cpu_cores}"
    if load1 > cpu_cores * 1.5:
        level = "alert"
    elif load1 > cpu_cores:
        level = "warning"
    else:
        level = "info"
    results.append({"level": level, "message": msg})

    # Memory
    msg = f"Memory: {mem_used_mb:.0f}/{mem_total_mb:.0f} MB used ({mem_used_pct:.1f}%)"
    if mem_used_pct > 90:
        level = "alert"
    elif mem_used_pct > 80:
        level = "warning"
    else:
        level = "info"
    results.append({"level": level, "message": msg})

    return results


# -----------------------------
# Top processes (CPU hogs)
# -----------------------------

def collect_top_processes(limit: int = 5) -> List[Dict]:
    """
    Use ps to get top CPU-using processes.
    """
    results = []
    ps_out = run_cmd(["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"])
    if not ps_out:
        return results

    lines = ps_out.splitlines()
    header = lines[0]
    procs = lines[1:limit+1]

    for line in procs:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, comm, cpu_str, mem_str = parts
        try:
            cpu = float(cpu_str)
        except ValueError:
            cpu = 0.0

        if cpu > 80:
            level = "alert"
        elif cpu > 40:
            level = "warning"
        else:
            level = "info"

        msg = f"PID {pid:>6} | {comm:<20} | CPU: {cpu_str:>5}% | MEM: {mem_str:>5}%"
        results.append({"level": level, "message": msg})

    return results


# -----------------------------
# Network monitoring
# -----------------------------

def collect_network() -> List[Dict]:
    """
    Summarize connections using ss (if available).
    """
    results = []

    # Listening sockets
    listen_out = run_cmd(["ss", "-tuln"])
    if listen_out:
        lines = listen_out.splitlines()[1:]  # skip header
        count_listen = len(lines)
        msg = f"Listening sockets: {count_listen}"
        level = "info"
        results.append({"level": level, "message": msg})

    # Established connections
    est_out = run_cmd(["ss", "-tun"])
    if est_out:
        lines = [l for l in est_out.splitlines()[1:] if "ESTAB" in l]
        count_estab = len(lines)
        msg = f"Established TCP/UDP connections: {count_estab}"
        # Heuristic: many connections may be suspicious
        if count_estab > 200:
            level = "alert"
        elif count_estab > 50:
            level = "warning"
        else:
            level = "info"
        results.append({"level": level, "message": msg})

    return results


# -----------------------------
# Auth / security logs
# -----------------------------

def collect_auth_events() -> List[Dict]:
    """
    Parse last N lines of auth log for failed logins, sudo use, etc.
    """
    results = []
    path = get_auth_log_path()
    if not path:
        return [{"level": "info", "message": "No auth.log/secure file found."}]

    try:
        # Tail last 300 lines
        tail_out = run_cmd(["tail", "-n", "300", path])
        if not tail_out:
            return []

        lines = tail_out.splitlines()

        failed = [l for l in lines if "Failed password" in l or "authentication failure" in l]
        accepted = [l for l in lines if "Accepted password" in l or "session opened for user" in l]
        sudo_use = [l for l in lines if "sudo:" in l]

        if failed:
            msg = f"Recent failed login attempts: {len(failed)} (last 300 lines)"
            level = "warning" if len(failed) < 10 else "alert"
            results.append({"level": level, "message": msg})

        if accepted:
            msg = f"Recent successful logins: {len(accepted)} (last 300 lines)"
            results.append({"level": "info", "message": msg})

        if sudo_use:
            msg = f"Recent sudo commands: {len(sudo_use)} (last 300 lines)"
            results.append({"level": "info", "message": msg})

    except Exception as e:
        results.append({"level": "info", "message": f"Error reading auth logs: {e}"})

    return results


def collect_recent_logins(limit: int = 5) -> List[Dict]:
    """
    Use 'last' to show recent logins.
    """
    out = run_cmd(["last", "-n", str(limit)])
    if not out:
        return []
    lines = out.splitlines()
    clean_lines = [l for l in lines if l.strip() and "wtmp begins" not in l]
    results = [{"level": "info", "message": l} for l in clean_lines[:limit]]
    return results


# -----------------------------
# Master collector
# -----------------------------

def filter_by_level(entries: List[Dict], min_level: str) -> List[Dict]:
    threshold = LEVELS.get(min_level, 1)
    filtered = []
    for e in entries:
        if LEVELS.get(e["level"], 1) >= threshold:
            filtered.append(e)
    return filtered


def print_section(title: str):
    print()
    print(color_text(f"== {title} ==", "section"))


def clear_screen():
    if sys.stdout.isatty():
        os.system("clear")


def main():
    parser = argparse.ArgumentParser(description="Linux Master Monitor (performance + security dashboard)")
    parser.add_argument("--interval", type=int, default=5, help="Refresh interval in seconds (default: 5)")
    parser.add_argument("--min-level", choices=["info", "warning", "alert"], default="info",
                        help="Minimum severity level to display (default: info)")
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit instead of looping")
    args = parser.parse_args()

    interval = args.interval
    min_level = args.min_level

    # Simple requirement checks (these are standard on most distros)
    for cmd in ["ps", "ss", "tail", "last"]:
        if shutil.which(cmd) is None:
            print(f"[!] Required command '{cmd}' not found in PATH. Please install it via your package manager.")
            sys.exit(1)

    try:
        while True:
            clear_screen()
            print(color_text("Linux Master Monitor", "bold"))
            print(f"Time: {human_time()} | Min level: {min_level} | Interval: {interval}s")
            print("-" * 70)

            # PERFORMANCE
            perf_entries = filter_by_level(collect_performance(), min_level)
            print_section("Performance")
            if not perf_entries:
                print("  (no entries at this level)")
            for e in perf_entries:
                print("  " + color_text(f"[{e['level'].upper()}] ", e["level"]) + e["message"])

            # TOP PROCESSES
            proc_entries = filter_by_level(collect_top_processes(limit=5), min_level)
            print_section("Top CPU Processes")
            if not proc_entries:
                print("  (no entries at this level)")
            for e in proc_entries:
                print("  " + color_text(f"[{e['level'].upper()}] ", e["level"]) + e["message"])

            # NETWORK
            net_entries = filter_by_level(collect_network(), min_level)
            print_section("Network Summary")
            if not net_entries:
                print("  (no entries at this level)")
            for e in net_entries:
                print("  " + color_text(f"[{e['level'].upper()}] ", e["level"]) + e["message"])

            # AUTH / SECURITY
            auth_entries = filter_by_level(collect_auth_events(), min_level)
            print_section("Auth & Security Events")
            if not auth_entries:
                print("  (no entries at this level)")
            for e in auth_entries:
                print("  " + color_text(f"[{e['level'].upper()}] ", e["level"]) + e["message"])

            # RECENT LOGINS (always info-level, so only show if min_level == info)
            if LEVELS[min_level] <= LEVELS["info"]:
                recent_logins = collect_recent_logins(limit=5)
                print_section("Recent Logins (last 5)")
                if not recent_logins:
                    print("  (no data)")
                for e in recent_logins:
                    print("  " + e["message"])

            print()
            print("(Press Ctrl+C to exit)")

            if args.once:
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[+] Exiting monitor.")


if __name__ == "__main__":
    main()

