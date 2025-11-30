Here you go — a repo-ready `README.md` for your Home-SOC project 👇

---

# Home-SOC – Local Security & Performance Monitor

Home-SOC is a **lightweight personal SOC (Security Operations Center)** for your Linux machine.

It gives you:

* A **terminal dashboard** for real-time monitoring
* A **web dashboard** with charts (CPU, memory, connections, security score)
* **JSON logs** for long-term trending
* **Critical alerts** persisted to a file
* An overall **Security Score (0–100)** per snapshot

Everything runs **locally**, with no data leaving your machine.

---

## Features

* **Security Score (0–100)** — at-a-glance health/risk indicator
* **Terminal dashboard** (`home_soc.py`)

  * CPU load / memory usage
  * Top CPU processes
  * Network summary
  * Auth & security events (failed logins, sudo, etc.)
* **Web dashboard** (`home_soc_web.py`)

  * Charts for:

    * Security score over time
    * CPU load
    * Memory usage
    * Network connections
* **Logging**

  * `monitor_metrics.jsonl` – all snapshots (for graphs/trends)
  * `monitor_alerts.jsonl` – critical alerts only (for investigations)
* Hooks for **Telegram / email alerts** (disabled by default)
* Very **low resource usage** (runs every N seconds; uses standard tools)

---

## Requirements

* Linux (tested on Mint / Ubuntu / Parrot)
* Python 3
* Standard CLI tools:

  * `ps`
  * `ss`
  * `tail`
  * `last`
* For the web UI:

  * `Flask`

Install Flask:

```bash
pip install flask
```

---

## Files

* `home_soc.py` – main monitor (terminal dashboard + logging + alerts + security score)
* `home_soc_web.py` – web dashboard (Chart.js + Flask)
* `monitor_metrics.jsonl` – auto-generated metrics log
* `monitor_alerts.jsonl` – auto-generated critical alerts log

---

## Getting Started

### 1. Make scripts executable

```bash
chmod +x home_soc.py home_soc_web.py
```

---

### 2. Run the monitor (terminal dashboard)

```bash
./home_soc.py
```

Default behavior:

* Refresh every **10 seconds**
* Shows **info + warnings + alerts**
* Logs every snapshot into `monitor_metrics.jsonl`
* Persists critical alerts in `monitor_alerts.jsonl`

You’ll see:

* Performance section (load, memory + little bar graphs)
* Top CPU processes
* Network summary
* Auth & security events
* Recent logins
* Security Score at the top

---

### 3. Filter by severity

Show only warnings & alerts:

```bash
./home_soc.py --min-level warning
```

Show only critical alerts:

```bash
./home_soc.py --min-level alert
```

Run once and exit (for cron / scripting):

```bash
./home_soc.py --once
```

Change refresh interval:

```bash
./home_soc.py --interval 30
```

---

### 4. Run the web dashboard

In another terminal:

```bash
python3 home_soc_web.py
```

Then open:

```text
http://localhost:8080/
```

You’ll see:

* Latest **Security Score**
* 2×2 grid of charts:

  * Security Score over time
  * CPU Load
  * Memory Usage (%)
  * Network Connections

The web UI reads `monitor_metrics.jsonl`, so make sure `home_soc.py` is running.

---

## What Is the Security Score?

The **Security Score (0–100)** is a **composite indicator** that summarizes the overall health and risk level of your machine **at that moment**.

* Starts at **100**
* Subtracts points based on anomalies:

  * High CPU load
  * High memory usage
  * Too many established network connections
  * Recent failed login attempts
  * High-CPU processes

Rough interpretation:

* **90–100** → Normal, low risk
* **70–89** → Minor anomalies (load/activity, but likely benign)
* **50–69** → Something off (investigate CPU, network, logins)
* **0–49** → Serious issues (possible compromise / runaway system)

You can change the scoring logic inside `home_soc.py` (function `compute_security_score`).

---

## Logs

### `monitor_metrics.jsonl`

Each line is one JSON object:

```json
{
  "timestamp": "2025-11-30 11:25:10",
  "security_score": 92,
  "entries": [
    {"level": "info", "metric": "cpu_load", "value": 0.42, "message": "..."},
    {"level": "info", "metric": "memory_used_pct", "value": 23.4, "message": "..."},
    {"level": "warning", "metric": "failed_logins", "value": 3, "message": "..."}
  ]
}
```

This is what the web UI uses to draw charts.

---

### `monitor_alerts.jsonl`

Only **alert-level** events are saved here:

```json
{
  "timestamp": "2025-11-30 11:23:45",
  "alerts": [
    "Recent failed login attempts: 23 (last 300 lines)",
    "Established TCP/UDP connections: 245"
  ]
}
```

Use it to review serious incidents over time.

---

## Optional: Telegram & Email Alerts

In `home_soc.py` you’ll see:

```python
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

EMAIL_ENABLED = False
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 587
SMTP_USERNAME = "user@example.com"
SMTP_PASSWORD = "password"
EMAIL_FROM = "home-soc@example.com"
EMAIL_TO = "you@example.com"
```

To enable:

1. Set `TELEGRAM_ENABLED = True` and fill in `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
2. Or set `EMAIL_ENABLED = True` and configure your SMTP details

The script will:

* Append alerts to `monitor_alerts.jsonl`
* Send a Telegram / email notification **only when a new critical summary appears** (no spam)

---

## Customization

You can easily tweak:

* Thresholds for **CPU / memory / network / failed logins**
* How much each issue subtracts from the **security score**
* What counts as a **warning** vs **alert**
* Refresh interval (`--interval` flag)
* Number of points shown in the web charts (`load_metrics(limit=50)` in `home_soc_web.py`)

---

## Mental Model

Think of Home-SOC as:

* A **mini SIEM** for a single machine
* A **Defender-style security center**, but fully under your control
* A **training ground** to understand logs, metrics, and security signals

Use it to:

* Catch suspicious processes and logins
* See which apps spike CPU / RAM
* Track how secure & “quiet” your system is over time
* Learn to think like a SOC analyst on your own box
