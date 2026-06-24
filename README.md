# ZTB Monitor

A modular Python CLI for monitoring **Zscaler Zero Trust Branch (ZTB)** gateways and network devices. It queries the ZTB REST API to collect gateway status, device metrics, device details, and device events, and presents them in one of four output modes suited to different workflows.

---

## Output modes

| Mode | Flag | Best for |
|---|---|---|
| **CLI table** | `-o cli` | Interactive inspection in a terminal |
| **JSON** | `-o json` | Piping to `jq`, scripts, or log ingestion |
| **Webhook** | `-o webhook` | Cron jobs that alert only when something is wrong |
| **Prometheus** | `-o prometheus` | Long-running exporter scraped by Prometheus / Grafana |

---

## Requirements

- Python 3.9+
- [uv](https://github.com/astral-sh/uv)

```bash
uv venv
uv pip install -r requirements.txt
```

---

## Authentication

The script uses a two-step authentication flow:

1. On first run (or when the session token has expired), the script calls `POST /api/v3/api-key-auth/login` with your static `ZTB_API_KEY` and receives a short-lived JWT **delegate token**.
2. The delegate token is written automatically to your `.env` file as `ZTB_BEARER_TOKEN` and used in the `authorization` header of every subsequent API call.
3. Before each run the token's `exp` claim is checked. If it is missing, expired, or within 60 seconds of expiry, a fresh login is performed and the new token is persisted.

You only ever need to set `ZTB_API_KEY`. `ZTB_BEARER_TOKEN` is managed by the script.

---

## Configuration

Create a `.env` file from the provided template and set your API key:

```bash
cp .env.example .env
# edit .env — set ZTB_API_KEY
```

| Variable | CLI flag | Required | Default | Description |
|---|---|---|---|---|
| `ZTB_API_KEY` | `--api-key` | **Yes** | — | Static API key used to obtain a session token at login |
| `ZTB_BEARER_TOKEN` | — | Auto-managed | — | JWT delegate token; written by the script after login |
| `ZTB_BASE_URL` | `--base-url` | No | `https://sbcorp-api.goairgap.com` | API base URL |
| `ZTB_TIMEOUT` | — | No | `30` | HTTP request timeout (seconds) |
| `ZTB_WEBHOOK_URL` | `--webhook-url` | For webhook mode | — | Destination URL for alerts |
| `ZTB_WEBHOOK_TYPE` | `--webhook-type` | No | `generic` | Payload format: `generic`, `slack`, `teams` |
| `ZTB_PROMETHEUS_PORT` | `--prometheus-port` | No | `9090` | Port for the Prometheus `/metrics` endpoint |
| `ZTB_SCRAPE_INTERVAL` | `--interval` | No | `60` | Seconds between metric collections in exporter mode |
| `ZTB_GATEWAY_ID` | `--gateway-id` | No | — | Gateway ID for resource utilisation metrics |

---

## CLI workflow guide

A typical monitoring session starts broad and narrows down. The examples below assume you have already set up `.env` with your `ZTB_API_KEY`.

### 1. Get the big picture

Start with a high-level overview of all devices and gateways:

```bash
# All active devices
uv run main.py devices

# All gateways (both isolation and access types)
uv run main.py gateways
```

### 2. Filter and search

If the device or gateway list is large, narrow it down:

```bash
# Search by hostname, IP, or MAC
uv run main.py devices --search "branch-router"

# Filter by site
uv run main.py devices --site-id abc123

# Filter by tags
uv run main.py devices --tags "core,router"

# Search gateways by name or IP
uv run main.py gateways --search "bedburg"

# Show only isolation gateways
uv run main.py gateways --type isolation
```

### 3. Drill into a specific device or gateway

Once you have identified a device or gateway of interest, inspect it in detail using its ID (visible in the list output):

```bash
# Device details + last 2 hours of metrics
uv run main.py devices --id <device_id> --minutes 120

# Gateway details: system resources, containers, hourly averages,
# peak/low values, WAN monitor stats, and network interfaces
uv run main.py gateways --id <gateway_id>
```

### 4. Check events and security alerts

Review recent activity and look for compromised devices:

```bash
# Audit log / DHCP events
uv run main.py events --limit 50

# Security alerts (compromised / blacklisted devices)
uv run main.py alerts
```

### 5. Quick operational health check

Verify that DNS and DHCP are working on a gateway:

```bash
# Run the health checks (prompts to select a device for DHCP)
uv run main.py health --gateway-id <gateway_id>

# Specify a device for the DHCP check directly
uv run main.py health --gateway-id <gateway_id> --device-id <device_id>
```

### 6. Infrastructure metrics

Get a one-shot snapshot of BGP peers, GRE tunnels, VRRP status, and gateway resource utilisation:

```bash
# Infrastructure overview
uv run main.py metrics

# Include gateway resource stats for a specific gateway
uv run main.py metrics --gateway-id <gateway_id>
```

### 7. Set up ongoing monitoring

For continuous or scheduled monitoring, use webhook alerts (cron) or the Prometheus exporter:

```bash
# Cron: alert on offline devices every 5 minutes
*/5 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook devices

# Cron: alert on unhealthy gateways every 5 minutes
*/5 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook gateways

# Cron: alert on compromised devices every 15 minutes
*/15 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook alerts

# Cron: health check (DNS, DHCP) every 10 minutes
*/10 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook health --gateway-id <gateway_id>

# Prometheus exporter for device + BGP + gateway metrics (long-running)
uv run main.py -o prometheus metrics --gateway-id <gateway_id> --prometheus-port 9090

# Prometheus exporter for gateway health + WAN quality (long-running)
uv run main.py -o prometheus gateways --prometheus-port 9091
```

### Quick-reference cheat sheet

| Goal | Command |
|---|---|
| List all devices | `devices` |
| Find a device | `devices --search "hostname"` |
| Inspect one device | `devices --id <id> --minutes 120` |
| List all gateways | `gateways` |
| Inspect one gateway | `gateways --id <id>` |
| Recent events | `events --limit 50` |
| Security alerts | `alerts` |
| Infrastructure snapshot | `metrics` |
| DNS/DHCP health check | `health --gateway-id <id>` |
| JSON output (any command) | `-o json <command>` |
| Webhook alert (any command) | `-o webhook <command>` |

---

## Commands

### Global flags

These flags apply to all commands and must appear **before** the command name:

```bash
uv run main.py [--output/-o cli|json|webhook|prometheus] \
               [--api-key TOKEN] \
               [--base-url URL] \
               [--webhook-url URL] \
               [--webhook-type generic|slack|teams] \
               COMMAND [OPTIONS]
```

---

### `devices` — List or inspect devices

Fetches all active ZTB network devices, or drills into a single device for details and rolling metrics.

```bash
# List all active devices (CLI table)
uv run main.py devices

# Filter by search term, site, or tag
uv run main.py devices --search "branch-router" --site-id abc123 --tags "core,router"

# Paginate results
uv run main.py devices --limit 50 --page 2

# Inspect a single device (details + last 2 hours of metrics)
uv run main.py devices --id <device_id> --minutes 120

# Output as JSON
uv run main.py -o json devices --search "firewall"

# Send a webhook alert for any offline device (designed for cron)
uv run main.py -o webhook devices
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--search` | — | Search across device name, IP, MAC |
| `--site-id` | — | Filter by site ID |
| `--tags` | — | Comma-separated tag filter |
| `--limit` | `100` | Results per page |
| `--page` | `1` | Page number |
| `--id` | — | Single device ID — returns details + metrics |
| `--minutes` | `60` | Metric time window when using `--id` |

**CLI table columns:** ID, Hostname, IP Address, MAC, Status, Type, Location, Quarantined

**Webhook behaviour:** Fires only if one or more devices have a status outside `active / online / connected`. Silent on a clean run.

---

### `events` — Audit log / DHCP events

Fetches the DHCP event and device audit log.

```bash
# Show recent events
uv run main.py events

# Filter to a specific site, last 200 entries
uv run main.py events --site-id abc123 --limit 200

# Output as JSON
uv run main.py -o json events
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--search` | — | Search term |
| `--site-id` | — | Filter by site ID |
| `--limit` | `100` | Max results |
| `--page` | `1` | Page number |

**CLI table columns:** Timestamp, Device, IP, MAC, Event, Site

---

### `alerts` — Security alerts (compromised devices)

Fetches the compromised / blacklisted device alert list. In webhook mode, fires only when there are open alerts.

```bash
# Show all open security alerts
uv run main.py alerts

# Show only blacklisted devices
uv run main.py alerts --tab blacklist

# Send a webhook alert if any compromised devices are found (for cron)
uv run main.py -o webhook alerts

# Filter to a specific site
uv run main.py alerts --site-id abc123 --limit 50
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--tab` | `all` | Alert category: `all`, `blacklist`, or other UI tabs |
| `--site-id` | — | Filter by site ID |
| `--limit` | `100` | Max results |

**CLI table columns:** Device, Device IP, Attack Type, Target IP, Status, Site, First Seen, Count

**Webhook behaviour:** Fires only when `rows` is non-empty. Carries device name, IP, attack type, and site in the payload.

---

### `gateways` — List or inspect gateways

Fetches ZTB gateway appliances across all branch sites. By default both gateway types (isolation and access) are returned. Supports all four output modes including a dedicated Prometheus exporter that collects gateway health, CPU/memory/disk, and WAN link quality.

```bash
# List all gateways (both types)
uv run main.py gateways

# Filter by type
uv run main.py gateways --type isolation

# Search by name or IP
uv run main.py gateways --search "branch-01"

# Inspect a single gateway (details + resource stats + interfaces)
uv run main.py gateways --id <gateway_id>

# Output as JSON
uv run main.py -o json gateways

# Send a webhook alert if any gateways are unhealthy (for cron)
uv run main.py -o webhook gateways

# Start Prometheus exporter for gateway metrics (blocks)
uv run main.py -o prometheus gateways --prometheus-port 9091 --interval 30
```

**Options:**

| Flag | Env var | Default | Description |
|---|---|---|---|
| `--type` | — | both | Gateway type: `isolation` or `access` |
| `--search` | — | — | Search term |
| `--limit` | — | `100` | Results per page |
| `--page` | — | `1` | Page number |
| `--id` | — | — | Single gateway ID — returns details, resource stats, and interfaces |
| `--prometheus-port` | `ZTB_PROMETHEUS_PORT` | `9090` | HTTP port for `/metrics` endpoint |
| `--interval` | `ZTB_SCRAPE_INTERVAL` | `60` | Collection interval in seconds |

**CLI table columns:** Gateway ID, Name, IP Address, Public IP, State, Health, Version, VRRP, Last Poll, Cluster/Site

**Detail view (`--id`):** Key-value panel (IPs, state, health, versions, VRRP, NAT/WireGuard flags), gateway resource utilisation (CPU/memory), and network interfaces table (name, type, IP, MAC, admin/oper state, speed, MTU, duplex — plus RX/TX bytes, packets, dropped, and errors when `if_stats` are available).

**Webhook behaviour:** Fires only if one or more gateways have an `operational_state` outside `active / online / up / running / connected` or a `health_color` of `red`. Silent on a clean run.

**Prometheus mode:** Exposes `ztb_gateway_up`, `ztb_gateway_disk_percent`, and per-interface WAN latency/jitter/loss gauges. Also includes CPU/memory via the existing resource-status endpoint.

---

### `metrics` — Infrastructure metrics / Prometheus exporter

One-shot infrastructure snapshot (BGP, GRE tunnels, VRRP, site info, gateway resources), or a blocking Prometheus exporter for continuous collection.

```bash
# One-shot CLI snapshot
uv run main.py metrics

# Include gateway resource stats
uv run main.py metrics --gateway-id <gateway_id>

# JSON snapshot (pipe-friendly)
uv run main.py -o json metrics --gateway-id <gateway_id>

# Start Prometheus exporter (blocks until Ctrl+C)
uv run main.py -o prometheus metrics

# Prometheus exporter with gateway metrics, custom port and interval
uv run main.py -o prometheus metrics \
  --gateway-id <gateway_id> \
  --prometheus-port 9091 \
  --interval 30
```

**Options:**

| Flag | Env var | Default | Description |
|---|---|---|---|
| `--gateway-id` | `ZTB_GATEWAY_ID` | — | Gateway ID for CPU/memory stats |
| `--prometheus-port` | `ZTB_PROMETHEUS_PORT` | `9090` | HTTP port for `/metrics` endpoint |
| `--interval` | `ZTB_SCRAPE_INTERVAL` | `60` | Collection interval in seconds |

**One-shot CLI tables:** BGP peer status, gateway resources, GRE tunnels, site info (JSON panel)

---

### `health` — DNS and DHCP health checks

Runs two operational checks against a gateway to verify that core network services are functioning:

1. **DNS** — Checks that the `dnsproxy` container is present and running in the gateway's resource stats.
2. **DHCP** — Searches the audit log (`/api/v2/devices/auditlog`) for a device's DHCP events. In CLI mode, an interactive picker lists active devices to choose from. Use `--device-id` to skip the picker, or omit it in JSON/webhook mode to auto-select the first active device. The check PASSes only when the most recent lease is **less than 5 minutes old**; an older lease FAILs as stale.

```bash
# Run the health checks (interactive device picker for DHCP)
uv run main.py health --gateway-id <gateway_id>

# Specify a device for the DHCP check (skips picker)
uv run main.py health --gateway-id <gateway_id> --device-id <device_id>

# JSON output (auto-selects first device for DHCP)
uv run main.py -o json health --gateway-id <gateway_id>

# Webhook alert if any check fails (for cron)
uv run main.py -o webhook health --gateway-id <gateway_id>
```

**Options:**

| Flag | Env var | Default | Description |
|---|---|---|---|
| `--gateway-id` | `ZTB_GATEWAY_ID` | — | **Required.** Gateway to check |
| `--device-id` | — | — | Device ID for DHCP check (interactive picker if omitted in CLI mode; auto-selects first device in JSON/webhook mode) |

**CLI output:** Summary table with check name, PASS/FAIL status, and details, plus an overall pass count.

**JSON output (`-o json`):** A structured report object with `gateway_id`, `timestamp`, `overall_status`, `passed`/`total` counts, and a `checks` array. Each check has `name`, `status`, and `details`; the DHCP check additionally carries machine-readable fields (`device`, `device_id`, `last_lease`, `lease_age_seconds`, `threshold_seconds`).

```json
{
  "gateway_id": "3db629bf-364e-451f-af24-53d88ce9dd5e",
  "timestamp": "2026-06-24T13:28:16Z",
  "overall_status": "FAIL",
  "passed": 1,
  "total": 2,
  "checks": [
    {
      "name": "DNS (dnsproxy container)",
      "status": "PASS",
      "details": "CPU: 0.5%, Memory: 45MB"
    },
    {
      "name": "DHCP (lease history)",
      "status": "FAIL",
      "details": "ip-10-0-1-254 — last lease 2026-06-24T09:12:03Z is 845s old (> 300s threshold)",
      "device": "ip-10-0-1-254",
      "device_id": "d1629d96-366a-485f-a814-7209762b7223",
      "last_lease": "2026-06-24T09:12:03Z",
      "lease_age_seconds": 845,
      "threshold_seconds": 300
    }
  ]
}
```

**Webhook behaviour:** Fires only if one or more checks fail. Silent when all checks pass.

---

## Webhook alerts

Webhook mode is designed for **cron jobs** — the script exits silently if there is nothing to report, and POSTs an alert only when an issue is detected.

### Supported formats

**`generic`** — Plain JSON envelope, compatible with n8n, Zapier, custom receivers:
```json
{
  "source": "ztb-monitor",
  "severity": "critical",
  "title": "ZTB Security Alert: 2 Compromised Device(s) Detected",
  "message": "• device-a (10.0.0.1) — ARP Spoofing @ Branch-1\n• ...",
  "timestamp": "2026-03-19T08:00:00+00:00",
  "data": [...]
}
```

**`slack`** — [Slack Incoming Webhook](https://api.slack.com/messaging/webhooks) attachment format with colour-coded severity.

**`teams`** — Microsoft Teams MessageCard format.

### Alert types

| Trigger | Severity | Command |
|---|---|---|
| Devices offline | `warning` | `devices -o webhook` |
| Gateways unhealthy / down | `critical` | `gateways -o webhook` |
| Compromised / blacklisted devices | `critical` | `alerts -o webhook` |
| Health check failures (DNS/DHCP) | `critical` | `health -o webhook --gateway-id <id>` |
| BGP peers down | `critical` | *(raised inside Prometheus collect loop)* |

### Cron examples

```cron
# Check for offline devices every 5 minutes
*/5 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook devices

# Check for unhealthy gateways every 5 minutes
*/5 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook gateways

# Check for security alerts every 15 minutes
*/15 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook alerts

# Health check (DNS, DHCP) every 10 minutes
*/10 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook health --gateway-id <gateway_id>

# Use a .env file for credentials
*/5 * * * * cd /path/to/ZTB-monitor && uv run main.py -o webhook alerts
```

---

## Prometheus / Grafana integration

Run the exporter as a long-lived process (systemd service, Docker container, etc.):

```bash
uv run main.py -o prometheus metrics --gateway-id <id> --prometheus-port 9090
```

The exporter exposes `http://<host>:9090/metrics` for Prometheus to scrape.

### Metrics reference

| Metric | Type | Labels | Description |
|---|---|---|---|
| `ztb_devices_total` | Gauge | — | Total active devices |
| `ztb_devices_quarantined_total` | Gauge | — | Currently quarantined devices |
| `ztb_devices_offline_total` | Gauge | — | Devices not in active/online state |
| `ztb_compromised_devices_total` | Gauge | — | Open compromised-device alerts |
| `ztb_bgp_peer_up` | Gauge | `peer_ip`, `cluster` | `1` = established, `0` = down |
| `ztb_gateway_cpu_percent` | Gauge | `gateway_id` | Gateway CPU utilisation (%) |
| `ztb_gateway_memory_percent` | Gauge | `gateway_id` | Gateway memory utilisation (%) |
| `ztb_gateway_up` | Gauge | `gateway_id`, `gateway_name`, `cluster` | `1` = healthy, `0` = unhealthy |
| `ztb_gateway_disk_percent` | Gauge | `gateway_id` | Gateway disk utilisation (%) |
| `ztb_gateway_wan_latency_ms` | Gauge | `gateway_id`, `interface` | WAN interface latency (ms) |
| `ztb_gateway_wan_jitter_ms` | Gauge | `gateway_id`, `interface` | WAN interface jitter (ms) |
| `ztb_gateway_wan_loss_percent` | Gauge | `gateway_id`, `interface` | WAN interface packet loss (%) |
| `ztb_scrape_errors_total` | Gauge | — | Consecutive scrape error count |

### Prometheus `scrape_config`

```yaml
scrape_configs:
  - job_name: ztb_monitor
    static_configs:
      - targets: ["localhost:9090"]
    scrape_interval: 60s
```

### Suggested Grafana panels

- **Stat panel** — `ztb_devices_total`, `ztb_devices_quarantined_total`, `ztb_compromised_devices_total`
- **Time series** — `ztb_gateway_cpu_percent`, `ztb_gateway_memory_percent`, `ztb_gateway_disk_percent`
- **Time series** — `ztb_gateway_wan_latency_ms`, `ztb_gateway_wan_jitter_ms`, `ztb_gateway_wan_loss_percent` grouped by `interface`
- **State timeline** — `ztb_bgp_peer_up` grouped by `peer_ip`, `ztb_gateway_up` grouped by `gateway_name`
- **Alert rule** — fire when `ztb_compromised_devices_total > 0`, `ztb_bgp_peer_up == 0`, or `ztb_gateway_up == 0`

---

## Project structure

```
ZTB-monitor/
├── main.py                     CLI entry point (Click)
├── requirements.txt
├── .env.example
└── ztb_monitor/
    ├── config.py               Config dataclass (env vars / .env)
    ├── auth.py                 Login flow, JWT expiry check, .env token persistence
    ├── client.py               HTTP client with ZTBApiError
    ├── api/
    │   ├── devices.py          Device list, details, metrics endpoints
    │   ├── events.py           Audit logs + compromised device alerts
    │   ├── gateways.py         Gateway list, details, interfaces endpoints
    │   └── metrics.py          BGP, GRE tunnels, VRRP, gateway resources, dashboard
    └── output/
        ├── cli.py              Rich table renderers
        ├── webhook.py          Slack / Teams / generic alert builders
        └── prometheus.py       Gauge definitions + blocking exporter loop
```
