#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import datetime
import json
import shutil
import argparse
import smtplib
from email.mime.text import MIMEText
from typing import List, Dict, Any

# ============================
# CONFIG
# ============================

CHECK_INTERVAL_SECONDS_DEFAULT = 10  # higher interval = lower resource usage

LOG_FILE = "monitor_metrics.jsonl"       # all snapshots
ALERTS_FILE = "monitor_alerts.jsonl"     # only alerts (warning/alert, esp. alert)

AUTH_LOG_PATHS = [
    "/var/log/auth.log",  # Debian/Ubuntu/Mint
    "/var/log/secure",    # RHEL/CentOS
]

# Severity levels
LEVELS = {"info": 1, "warning": 2, "alert": 3}

# Colors (for terminal output)
COLORS = {
    "reset": "\033[0m",
    "info": "\033[36m",      # cyan
    "warning": "\033[33m",   # yellow
    "alert": "\033[31m",     # red
    "section": "\033[35m",   # magenta
    "bold": "\033[1m",
}

# Ignore performance impact from our own process unless truly insane
SELF_CPU_IGNORE_THRESHOLD = 90.0  # only alert if our own script > 90% CPU

# Optional: Telegram alerts
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = ""   # "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = ""     # e.g. "123456789"

# Optional: Email alerts
EMAIL_ENABLED = False
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 587
SMTP_USERNAME = "user@example.com"
SMTP_PASSWORD = "password"
EMAIL_FROM = "home-soc@example.com"
EMAIL_TO = "you@example.com"

# ============================
# HELPER FUNCTIONS
# ============================

def run_cmd(cmd: List[str]) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return ""


def human_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_auth_log_path() -> str:
    for p in AUTH_LOG_PATHS:
        if os.path.exists(p):
            return p
    return ""


def color_text(text: str, level: str) -> str:
    return COLORS.get(level, "") + text + COLORS["reset"]


def clear_screen():
    if sys.stdout.isatty():
        os.system("clear")


def write_jsonl(path: str, obj: Dict[str, Any]):
    try:
        with open(path, "a") as f:
            f.write(json.dumps(obj) + "\n")
    except Exception:
        # fail silently, we don't want the monitor to crash because of logging
        pass


# ============================
# PERFORMANCE
# ============================

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
    results = []
    load1, load5, load15 = get_loadavg()
    mem_used_pct, mem_total_mb, mem_used_mb = get_mem_usage()

    try:
        cpu_cores = os.cpu_count() or 1
    except Exception:
        cpu_cores = 1

    # CPU load
    msg = f"Load avg (1/5/15): {load1:.2f}, {load5:.2f}, {load15:.2f} | Cores: {cpu_cores}"
    if load1 > cpu_cores * 1.5:
        level = "alert"
    elif load1 > cpu_cores:
        level = "warning"
    else:
        level = "info"
    results.append({"level": level, "message": msg, "metric": "cpu_load", "value": load1})

    # Memory usage
    msg = f"Memory: {mem_used_mb:.0f}/{mem_total_mb:.0f} MB used ({mem_used_pct:.1f}%)"
    if mem_used_pct > 90:
        level = "alert"
    elif mem_used_pct > 80:
        level = "warning"
    else:
        level = "info"
    results.append({
        "level": level,
        "message": msg,
        "metric": "memory_used_pct",
        "value": mem_used_pct
    })

    return results


# ============================
# TOP PROCESSES
# ============================

def collect_top_processes(limit: int = 5) -> List[Dict]:
    """
    Use ps to get top CPU-using processes.
    Skip our own PID unless CPU is extreme.
    """
    results = []
    ps_out = run_cmd(["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"])
    if not ps_out:
        return results

    lines = ps_out.splitlines()
    procs = lines[1:limit+1]  # skip header

    self_pid = os.getpid()

    for line in procs:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid_str, comm, cpu_str, mem_str = parts
        try:
            pid = int(pid_str)
        except ValueError:
            pid = -1

        try:
            cpu = float(cpu_str)
        except ValueError:
            cpu = 0.0

        # Ignore our own script unless it's really crazy
        if pid == self_pid and cpu < SELF_CPU_IGNORE_THRESHOLD:
            continue

        if cpu > 80:
            level = "alert"
        elif cpu > 40:
            level = "warning"
        else:
            level = "info"

        msg = f"PID {pid:>6} | {comm:<20} | CPU: {cpu_str:>5}% | MEM: {mem_str:>5}%"
        results.append({
            "level": level,
            "message": msg,
            "metric": "process_cpu",
            "value": cpu,
            "pid": pid,
            "command": comm
        })

    return results


# ============================
# NETWORK
# ============================

def collect_network() -> List[Dict]:
    results = []

    listen_out = run_cmd(["ss", "-tuln"])
    if listen_out:
        lines = listen_out.splitlines()[1:]
        count_listen = len(lines)
        msg = f"Listening sockets: {count_listen}"
        results.append({
            "level": "info",
            "message": msg,
            "metric": "listening_sockets",
            "value": count_listen
        })

    est_out = run_cmd(["ss", "-tun"])
    if est_out:
        lines = [l for l in est_out.splitlines()[1:] if "ESTAB" in l]
        count_estab = len(lines)
        msg = f"Established TCP/UDP connections: {count_estab}"
        if count_estab > 200:
            level = "alert"
        elif count_estab > 50:
            level = "warning"
        else:
            level = "info"
        results.append({
            "level": level,
            "message": msg,
            "metric": "established_connections",
            "value": count_estab
        })

    return results


# ============================
# AUTH / SECURITY
# ============================

def collect_auth_events() -> List[Dict]:
    results = []
    path = get_auth_log_path()
    if not path:
        return [{"level": "info", "message": "No auth.log/secure file found.", "metric": "auth_log"}]

    try:
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
            results.append({
                "level": level,
                "message": msg,
                "metric": "failed_logins",
                "value": len(failed)
            })

        if accepted:
            msg = f"Recent successful logins: {len(accepted)} (last 300 lines)"
            results.append({
                "level": "info",
                "message": msg,
                "metric": "successful_logins",
                "value": len(accepted)
            })

        if sudo_use:
            msg = f"Recent sudo commands: {len(sudo_use)} (last 300 lines)"
            results.append({
                "level": "info",
                "message": msg,
                "metric": "sudo_commands",
                "value": len(sudo_use)
            })

    except Exception as e:
        results.append({"level": "info", "message": f"Error reading auth logs: {e}", "metric": "auth_error"})

    return results


def collect_recent_logins(limit: int = 5) -> List[Dict]:
    out = run_cmd(["last", "-n", str(limit)])
    if not out:
        return []
    lines = out.splitlines()
    clean_lines = [l for l in lines if l.strip() and "wtmp begins" not in l]
    return [{"level": "info", "message": l, "metric": "recent_login"} for l in clean_lines[:limit]]


# ============================
# SECURITY SCORE
# ============================

def compute_security_score(all_entries: List[Dict]) -> int:
    """
    Very rough heuristic security score from 0-100.
    Start at 100, subtract based on alerts.
    """
    score = 100

    # helper index:
    metrics = {}
    for e in all_entries:
        m = e.get("metric")
        if m is not None:
            metrics.setdefault(m, []).append(e)

    # CPU load
    if "cpu_load" in metrics:
        load_val = metrics["cpu_load"][0].get("value", 0)
        try:
            cores = os.cpu_count() or 1
        except Exception:
            cores = 1
        if load_val > cores * 1.5:
            score -= 20
        elif load_val > cores:
            score -= 10

    # Memory
    if "memory_used_pct" in metrics:
        mem_pct = metrics["memory_used_pct"][0].get("value", 0)
        if mem_pct > 90:
            score -= 20
        elif mem_pct > 80:
            score -= 10

    # Failed logins
    if "failed_logins" in metrics:
        fails = metrics["failed_logins"][0].get("value", 0)
        if fails > 20:
            score -= 25
        elif fails > 5:
            score -= 10
        elif fails > 0:
            score -= 5

    # Network
    if "established_connections" in metrics:
        conns = metrics["established_connections"][0].get("value", 0)
        if conns > 200:
            score -= 20
        elif conns > 50:
            score -= 10

    # Top processes (high CPU)
    if "process_cpu" in metrics:
        high_procs = [e for e in metrics["process_cpu"] if e.get("value", 0) > 80]
        if high_procs:
            score -= 10

    score = max(0, min(100, score))
    return score


# ============================
# ALERTING (Telegram / Email)
# ============================

_last_alert_fingerprint = None  # to avoid spamming same alert

def send_telegram_alert(text: str):
    if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import urllib.parse
        import urllib.request

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }).encode()
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def send_email_alert(subject: str, body: str):
    if not EMAIL_ENABLED:
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=5) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        pass


def handle_critical_alerts(entries: List[Dict]):
    """
    Persist alerts to ALERTS_FILE, and send Telegram/email on new ones.
    """
    global _last_alert_fingerprint
    timestamp = human_time()

    critical_entries = [e for e in entries if e["level"] == "alert"]

    if not critical_entries:
        return

    # Build a compact summary
    summary = {
        "timestamp": timestamp,
        "alerts": [e["message"] for e in critical_entries],
    }

    # Persist to JSONL
    write_jsonl(ALERTS_FILE, summary)

    # Fingerprint to avoid spamming same alert over and over
    fingerprint = json.dumps(summary, sort_keys=True)
    if fingerprint == _last_alert_fingerprint:
        return

    _last_alert_fingerprint = fingerprint

    text = "*Home-SOC Critical Alerts:*\n" + "\n".join(f"- {m}" for m in summary["alerts"])
    send_telegram_alert(text)
    send_email_alert(subject="Home-SOC Critical Alerts", body=text)


# ============================
# DISPLAY & FILTERING
# ============================

def filter_by_level(entries: List[Dict], min_level: str) -> List[Dict]:
    threshold = LEVELS.get(min_level, 1)
    return [e for e in entries if LEVELS.get(e["level"], 1) >= threshold]


def print_section(title: str):
    print()
    print(color_text(f"== {title} ==", "section"))


def draw_bar(label: str, value: float, max_value: float, width: int = 30, level: str = "info"):
    if max_value <= 0:
        frac = 0
    else:
        frac = max(0.0, min(1.0, value / max_value))
    filled = int(frac * width)
    bar = "#" * filled + "-" * (width - filled)
    print(f"  {label:<12} [{color_text(bar, level)}] {value:.1f}/{max_value:.1f}")


# ============================
# MAIN LOOP
# ============================

def main():
    parser = argparse.ArgumentParser(description="Home-SOC: Linux performance + security monitor")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL_SECONDS_DEFAULT,
                        help=f"Refresh interval in seconds (default: {CHECK_INTERVAL_SECONDS_DEFAULT})")
    parser.add_argument("--min-level", choices=["info", "warning", "alert"], default="info",
                        help="Minimum severity level to display (default: info)")
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit instead of looping")
    args = parser.parse_args()

    interval = args.interval
    min_level = args.min_level

    # Requirements check (all standard tools)
    for cmd in ["ps", "ss", "tail", "last"]:
        if shutil.which(cmd) is None:
            print(f"[!] Required command '{cmd}' not found in PATH. Please install it via your package manager.")
            sys.exit(1)

    try:
        while True:
            clear_screen()
            now = human_time()

            # Collect everything
            perf_entries = collect_performance()
            proc_entries = collect_top_processes(limit=5)
            net_entries = collect_network()
            auth_entries = collect_auth_events()
            recent_login_entries = collect_recent_logins(limit=5)

            all_entries = perf_entries + proc_entries + net_entries + auth_entries

            # Compute security score
            security_score = compute_security_score(all_entries)

            # Persist snapshot (for web UI + trends)
            snapshot = {
                "timestamp": now,
                "security_score": security_score,
                "entries": all_entries,
            }
            write_jsonl(LOG_FILE, snapshot)

            # Handle critical alerts
            handle_critical_alerts(all_entries)

            # HEADER
            print(color_text("Home-SOC Monitor", "bold"))
            print(f"Time: {now} | Min level: {min_level} | Interval: {interval}s | Security Score: {security_score}/100")
            print("-" * 80)

            # PERFORMANCE (with simple colored bars)
            filtered_perf = filter_by_level(perf_entries, min_level)
            print_section("Performance")

            # CPU bar & mem bar using perf entries
            load1 = next((e["value"] for e in perf_entries if e.get("metric") == "cpu_load"), 0.0)
            mem_pct = next((e["value"] for e in perf_entries if e.get("metric") == "memory_used_pct"), 0.0)

            # CPU bar
            cpu_level = "info"
            try:
                cores = os.cpu_count() or 1
            except Exception:
                cores = 1
            if load1 > cores * 1.5:
                cpu_level = "alert"
            elif load1 > cores:
                cpu_level = "warning"
            draw_bar("CPU load", load1, max(cores * 2, 1), level=cpu_level)

            # MEM bar
            mem_level = "info"
            if mem_pct > 90:
                mem_level = "alert"
            elif mem_pct > 80:
                mem_level = "warning"
            draw_bar("Memory %", mem_pct, 100.0, level=mem_level)

            for e in filtered_perf:
                print("  " + color_text(f"[{e['level'].upper()}] ", e["level"]) + e["message"])

            # TOP PROCESSES
            filtered_procs = filter_by_level(proc_entries, min_level)
            print_section("Top CPU Processes")
            if not filtered_procs:
                print("  (no entries at this level)")
            else:
                for e in filtered_procs:
                    print("  " + color_text(f"[{e['level'].upper()}] ", e["level"]) + e["message"])

            # NETWORK
            filtered_net = filter_by_level(net_entries, min_level)
            print_section("Network Summary")
            if not filtered_net:
                print("  (no entries at this level)")
            else:
                for e in filtered_net:
                    print("  " + color_text(f"[{e['level'].upper()}] ", e["level"]) + e["message"])

            # AUTH / SECURITY
            filtered_auth = filter_by_level(auth_entries, min_level)
            print_section("Auth & Security Events")
            if not filtered_auth:
                print("  (no entries at this level)")
            else:
                for e in filtered_auth:
                    print("  " + color_text(f"[{e['level'].upper()}] ", e["level"]) + e["message"])

            # RECENT LOGINS (only when info is allowed)
            if LEVELS[min_level] <= LEVELS["info"]:
                print_section("Recent Logins (last 5)")
                if not recent_login_entries:
                    print("  (no data)")
                else:
                    for e in recent_login_entries:
                        print("  " + e["message"])

            print()
            print("(Press Ctrl+C to exit)")

            if args.once:
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[+] Exiting Home-SOC Monitor.")


if __name__ == "__main__":
    main()

