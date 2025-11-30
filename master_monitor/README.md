Absolutely — here is a clean, professional, repo-ready **Markdown wiki page** you can drop directly into a `README.md` or `WIKI.md`.

---

# Master Monitor — Linux Performance & Security Dashboard

**Master Monitor** is an all-in-one script that gives you a real-time dashboard of:

* System performance
* Top CPU-hungry processes
* Network connections
* Authentication & security events
* Recent logins
* ⚠️ Alerts & warnings (configurable)

It’s designed for **Linux desktop users** who want full visibility into their system without needing to install heavyweight tools like Grafana, Wazuh, or Splunk.

---

# Features

### ✅ Performance Monitoring

* CPU load (1/5/15 min averages)
* Memory usage
* Alerts when load or memory exceed safe thresholds

### ✅ Process Monitoring

* Top CPU-consuming processes
* Alerts for processes exceeding 40% / 80% CPU
* Useful for detecting runaway or malicious programs

### ✅ Network Monitoring

* Listening ports (via `ss`)
* Established TCP/UDP connections
* Warnings on suspiciously high connection counts

### ✅ Authentication & Security

* Failed login attempts
* Successful logins
* Sudo command usage
* Works with `/var/log/auth.log` or `/var/log/secure`

### ✅ Recent Login History

* Last login sessions via `last`

### ✅ Severity Filtering

Choose what you want to see:

* `info`
* `warning`
* `alert`

Example:

```bash
./master_monitor.py --min-level alert
```

Only shows **critical issues**.

---

# Installation

1. Clone your repository:

```bash
git clone <your-repo-url>
cd <repo>
```

2. Make the script executable:

```bash
chmod +x master_monitor.py
```

That’s it — no extra dependencies required.

All commands used (`ps`, `ss`, `tail`, `last`) are standard on Linux Mint/Ubuntu/Debian.

---

# Usage

### Basic: run the live dashboard

```bash
./master_monitor.py
```

Refreshes every 5 seconds.

---

### Show only warnings and alerts

```bash
./master_monitor.py --min-level warning
```

This filters out noise and focuses on:

* High CPU usage
* High memory usage
* Failed logins
* Suspicious network activity

---

### Alerts only (critical mode)

```bash
./master_monitor.py --min-level alert
```

Useful while working:

* If nothing prints, everything's OK
* If anything prints, investigate immediately

---

### One-time snapshot (no live dashboard)

```bash
./master_monitor.py --once
```

This prints a “status report” and exits.

Perfect for automation.

---

### Change refresh interval

```bash
./master_monitor.py --interval 10
```

Updates every 10 seconds.

---

# Example Output

```
Linux Master Monitor
Time: 2025-11-30 10:42:18 | Min level: info | Interval: 5s
--------------------------------------------------------------------

== Performance ==
[INFO] Load avg (1/5/15): 0.24, 0.18, 0.11 | Cores: 8
[INFO] Memory: 2150/16000 MB used (13.4%)

== Top CPU Processes ==
[INFO] PID   1032 | firefox-esr          | CPU:  11.2% | MEM:   4.3%
[WARNING] PID  2375 | node                | CPU:  47.4% | MEM:   2.8%

== Network Summary ==
[INFO] Listening sockets: 12
[WARNING] Established TCP/UDP connections: 58

== Auth & Security Events ==
[WARNING] Recent failed login attempts: 4 (last 300 lines)
[INFO] Recent sudo commands: 3 (last 300 lines)

== Recent Logins (last 5) ==
mregra   pts/0        192.168.1.44   Mon Nov 30 10:22   still logged in
```

---

# Customization

To adjust thresholds (e.g., CPU warning levels), modify:

```python
if cpu > 80:
    level = "alert"
elif cpu > 40:
    level = "warning"
```

Memory thresholds:

```python
if mem_used_pct > 90:
    level = "alert"
elif mem_used_pct > 80:
    level = "warning"
```

Network thresholds:

```python
if count_estab > 200:
    level = "alert"
elif count_estab > 50:
    level = "warning"
```

---

# Security Notes

Master Monitor can help detect:

* Unexpected SSH logins
* Bruteforce attempts
* Malware establishing network connections
* Crypto miners using high CPU
* Runaway browser tabs
* Services listening on unexpected ports
* Suspicious processes with high resource usage

But it **does not replace** full IDS tools like:

* Zeek
* Suricata
* OSSEC/Wazuh

Think of it as your **local detective**, not your entire security team.

---

# Recommended Add-Ons (Optional)

If you want to extend this:

* `fail2ban` → blocks repeated SSH logins
* `ufw` → simple firewall
* `rkhunter` → rootkit scanning
* `auditd` → deeper kernel-level auditing
* `nethogs` → per-process bandwidth usage
* `atop` → historical performance logs

I can help you integrate any of these next.

---

# Final Notes

This script is intentionally:

* **Lightweight**
* **No external dependencies**
* **Fast**
* **Local-only**
* **Full control by the user**

Perfect for developers, hackers, or privacy-focused users who want to understand their Linux system at a deeper level.
