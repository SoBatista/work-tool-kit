#!/usr/bin/env python3
from flask import Flask, jsonify, render_template_string
import json

LOG_FILE = "monitor_metrics.jsonl"

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Home-SOC Dashboard</title>
    <style>
        body {
            background-color: #0e0e0e;
            color: #e6e6e6;
            font-family: Arial, sans-serif;
            margin: 20px;
        }

        h1 {
            color: #6ec6ff;
            margin-bottom: 10px;
        }

        h2 {
            margin-bottom: 30px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr)); /* always 2 columns */
            gap: 20px;
        }

        .card {
            background: #1c1c1c;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.4);
            height: 350px; /* fixes height for charts */
        }

        .section-title {
            font-size: 18px;
            color: #7cb8ff;
            margin-bottom: 12px;
        }

        @media (max-width: 900px) {
            .grid {
                grid-template-columns: 1fr; /* 1 column on small screens */
            }
        }
    </style>

    <!-- Load Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>

<h1>Home-SOC Web Dashboard</h1>
<h2>Latest Security Score: <span id="score">--</span>/100</h2>

<div class="grid">

    <div class="card">
        <div class="section-title">Security Score Over Time</div>
        <canvas id="scoreChart"></canvas>
    </div>

    <div class="card">
        <div class="section-title">CPU Load</div>
        <canvas id="cpuChart"></canvas>
    </div>

    <div class="card">
        <div class="section-title">Memory Usage (%)</div>
        <canvas id="memChart"></canvas>
    </div>

    <div class="card">
        <div class="section-title">Network Connections</div>
        <canvas id="networkChart"></canvas>
    </div>

</div>

<script>
async function fetchData() {
    const res = await fetch("/api/metrics");
    return await res.json();
}

let scoreChart, cpuChart, memChart, netChart;

function buildChart(id, label, data, color) {
    const ctx = document.getElementById(id).getContext("2d");

    return new Chart(ctx, {
        type: "line",
        data: {
            labels: data.timestamps,
            datasets: [{
                label: label,
                data: data.values,
                borderColor: color,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: "#fff" } }
            },
            scales: {
                x: {
                    ticks: {
                        color: "#ccc",
                        maxTicksLimit: 6,   // fewer labels
                        maxRotation: 30,
                        minRotation: 0
                    }
                },
                y: {
                    ticks: { color: "#ccc" }
                }
            }
        }
    });
}

async function refresh() {
    const data = await fetchData();

    if (data.length === 0) return;

    // Extract metrics
    const timestamps = data.map(d => d.timestamp);
    const scores = data.map(d => d.security_score);

    const cpu = data.map(d => d.cpu_load);
    const mem = data.map(d => d.mem_used);
    const net = data.map(d => d.connections);

    // Update latest score
    document.getElementById("score").innerText = scores[scores.length - 1];

    const formatted = (values) => ({
        timestamps,
        values,
    });

    // Destroy old charts if they exist
    if (scoreChart) scoreChart.destroy();
    if (cpuChart) cpuChart.destroy();
    if (memChart) memChart.destroy();
    if (netChart) netChart.destroy();

    // Rebuild charts
    scoreChart = buildChart("scoreChart", "Security Score", formatted(scores), "#6ec6ff");
    cpuChart = buildChart("cpuChart", "CPU Load", formatted(cpu), "#ffa07a");
    memChart = buildChart("memChart", "Memory Usage (%)", formatted(mem), "#90ee90");
    netChart = buildChart("networkChart", "Connections", formatted(net), "#ffeb3b");
}

setInterval(refresh, 5000);
refresh();
</script>

</body>
</html>
"""

def load_metrics(limit=50):
    data = []
    try:
        with open(LOG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                # extract metrics
                cpu = 0
                mem = 0
                conns = 0
                for e in obj.get("entries", []):
                    if e.get("metric") == "cpu_load":
                        cpu = e.get("value", 0)
                    if e.get("metric") == "memory_used_pct":
                        mem = e.get("value", 0)
                    if e.get("metric") == "established_connections":
                        conns = e.get("value", 0)

                data.append({
                    "timestamp": obj.get("timestamp"),
                    "security_score": obj.get("security_score", 0),
                    "cpu_load": cpu,
                    "mem_used": mem,
                    "connections": conns,
                })

    except FileNotFoundError:
        pass

    return data[-limit:]


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/metrics")
def api_metrics():
    return jsonify(load_metrics())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

