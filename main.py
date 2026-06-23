#!/usr/bin/env python3
"""ZTB Monitor — CLI entry point.

Usage examples:
  uv run main.py devices
  uv run main.py devices --id <device_id>
  uv run main.py events
  uv run main.py alerts
  uv run main.py metrics
  uv run main.py metrics --output prometheus --gateway-id <id>

Output modes  (-o / --output):
  cli         Pretty tables via Rich  (default for interactive use)
  json        Raw JSON to stdout      (pipe-friendly)
  webhook     POST alerts to a webhook URL (designed for cron jobs)
  prometheus  Start a Prometheus /metrics HTTP server (blocks)
"""

import json
import sys
from pathlib import Path

import click
import requests

from ztb_monitor.api import devices as devices_api
from ztb_monitor.api import events as events_api
from ztb_monitor.api import gateways as gateways_api
from ztb_monitor.api import metrics as metrics_api
from ztb_monitor.auth import ensure_token
from ztb_monitor.client import ZTBClient, ZTBApiError
from ztb_monitor.config import Config
from ztb_monitor.output import cli as cli_out
from ztb_monitor.output import webhook as webhook_out
from ztb_monitor.output import prometheus as prom_out

ENV_FILE = Path(__file__).parent / ".env"

OUTPUT_CHOICES = click.Choice(["cli", "json", "webhook", "prometheus"])
_ACTIVE_STATUSES = {"active", "online", "connected"}
_HEALTHY_GW_STATES = {"active", "online", "up", "running", "connected"}


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group()
@click.option(
    "--output", "-o",
    type=OUTPUT_CHOICES,
    default="cli",
    show_default=True,
    help="Output mode.",
)
@click.option("--api-key", envvar="ZTB_API_KEY", help="Bearer token (or set ZTB_API_KEY).")
@click.option(
    "--base-url",
    envvar="ZTB_BASE_URL",
    default="https://sbcorp-api.goairgap.com",
    show_default=True,
    help="API base URL.",
)
@click.option("--webhook-url", envvar="ZTB_WEBHOOK_URL", default="", help="Webhook destination URL.")
@click.option(
    "--webhook-type",
    envvar="ZTB_WEBHOOK_TYPE",
    default="generic",
    show_default=True,
    type=click.Choice(["generic", "slack", "teams"]),
    help="Webhook payload format.",
)
@click.pass_context
def cli(ctx, output, api_key, base_url, webhook_url, webhook_type):
    ctx.ensure_object(dict)
    config = Config(
        base_url=base_url,
        api_key=api_key or "",
        webhook_url=webhook_url,
        webhook_type=webhook_type,
    )
    try:
        config.validate()
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    try:
        token = ensure_token(
            base_url=config.base_url,
            api_key=config.api_key,
            bearer_token=config.bearer_token,
            env_path=ENV_FILE,
            timeout=config.timeout,
        )
    except Exception as exc:
        click.echo(f"Authentication error: {exc}", err=True)
        sys.exit(1)

    config.bearer_token = token
    client = ZTBClient(config)
    client._set_bearer(token)

    ctx.obj["config"] = config
    ctx.obj["output"] = output
    ctx.obj["client"] = client


# ---------------------------------------------------------------------------
# devices
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--search", default="", help="Search term.")
@click.option("--site-id", default="", help="Filter by site ID.")
@click.option("--tags", default="", help="Filter by tags (comma-separated).")
@click.option("--limit", default=5, show_default=True, help="Max results per page (v2 API quirk: values >5 may return fewer results).")
@click.option("--page", default=1, show_default=True, help="Page number.")
@click.option("--id", "device_id", default="", help="Fetch details + metrics for a single device.")
@click.option("--minutes", default=60, show_default=True, help="Metric window (minutes) when using --id.")
@click.pass_context
def devices(ctx, search, site_id, tags, limit, page, device_id, minutes):
    """List active devices or inspect a single device."""
    client: ZTBClient = ctx.obj["client"]
    output: str = ctx.obj["output"]
    config: Config = ctx.obj["config"]

    try:
        if device_id:
            details = devices_api.get_device_details(client, device_id)
            metrics = devices_api.get_device_metrics(client, device_id, minutes)
            if output == "json":
                click.echo(json.dumps({"details": details, "metrics": metrics}, indent=2, default=str))
            else:
                cli_out.display_device_details(details, metrics)
            return

        data = devices_api.get_devices(client, search=search, site_id=site_id, tags=tags, limit=limit, page=page)

        if output == "json":
            click.echo(json.dumps(data, indent=2, default=str))

        elif output == "webhook":
            if not config.webhook_url:
                click.echo("Error: --webhook-url / ZTB_WEBHOOK_URL is required for webhook output.", err=True)
                sys.exit(1)
            result = data.get("result", {})
            rows = result.get("rows", []) if isinstance(result, dict) else []
            offline = [d for d in rows if str(d.get("status", "")).lower() not in _ACTIVE_STATUSES]
            if offline:
                webhook_out.alert_offline_devices(config.webhook_url, config.webhook_type, offline)
                click.echo(f"Alert sent: {len(offline)} offline device(s).")
            else:
                click.echo("All devices online — no alert sent.")

        else:  # cli
            cli_out.display_devices(data)

    except ZTBApiError as exc:
        click.echo(f"API error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--search", default="", help="Search term.")
@click.option("--site-id", default="", help="Filter by site ID.")
@click.option("--limit", default=100, show_default=True, help="Max results.")
@click.option("--page", default=1, show_default=True)
@click.pass_context
def events(ctx, search, site_id, limit, page):
    """Show DHCP / device audit log events."""
    client: ZTBClient = ctx.obj["client"]
    output: str = ctx.obj["output"]

    try:
        data = events_api.get_audit_logs(client, search=search, site_id=site_id, limit=limit, page=page)
        if output == "json":
            click.echo(json.dumps(data, indent=2, default=str))
        else:
            cli_out.display_events(data)
    except ZTBApiError as exc:
        click.echo(f"API error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# alerts
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--tab", default="all", show_default=True, help="Alert tab (all, blacklist, …).")
@click.option("--site-id", default="", help="Filter by site ID.")
@click.option("--limit", default=100, show_default=True, help="Max results.")
@click.pass_context
def alerts(ctx, tab, site_id, limit):
    """Show security alerts for compromised / blacklisted devices."""
    client: ZTBClient = ctx.obj["client"]
    output: str = ctx.obj["output"]
    config: Config = ctx.obj["config"]

    try:
        data = events_api.get_compromised_devices(client, tab=tab, site_id=site_id, limit=limit)
        result = data.get("result", {})
        rows = result.get("rows", []) if isinstance(result, dict) else []

        if output == "json":
            click.echo(json.dumps(data, indent=2, default=str))

        elif output == "webhook":
            if not config.webhook_url:
                click.echo("Error: --webhook-url / ZTB_WEBHOOK_URL is required for webhook output.", err=True)
                sys.exit(1)
            if rows:
                webhook_out.alert_compromised_devices(config.webhook_url, config.webhook_type, rows)
                click.echo(f"Alert sent: {len(rows)} compromised device(s).")
            else:
                click.echo("No compromised devices — no alert sent.")

        else:  # cli
            cli_out.display_compromised_devices(data)

    except ZTBApiError as exc:
        click.echo(f"API error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# gateways
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--type", "gateway_type", default="", type=click.Choice(["isolation", "access", ""], case_sensitive=False), help="Gateway type filter (default: both).")
@click.option("--search", default="", help="Search term.")
@click.option("--limit", default=100, show_default=True, help="Max results per page.")
@click.option("--page", default=1, show_default=True, help="Page number.")
@click.option("--id", "gateway_id", default="", help="Fetch details for a single gateway.")
@click.option(
    "--prometheus-port",
    default=9090,
    show_default=True,
    envvar="ZTB_PROMETHEUS_PORT",
    help="Port for the Prometheus exporter (prometheus output only).",
)
@click.option(
    "--interval",
    default=60,
    show_default=True,
    envvar="ZTB_SCRAPE_INTERVAL",
    help="Collection interval in seconds (prometheus output only).",
)
@click.pass_context
def gateways(ctx, gateway_type, search, limit, page, gateway_id, prometheus_port, interval):
    """List gateways or inspect a single gateway."""
    client: ZTBClient = ctx.obj["client"]
    output: str = ctx.obj["output"]
    config: Config = ctx.obj["config"]

    try:
        if gateway_id:
            details = gateways_api.get_gateway_details(client, gateway_id)
            resource_status = None
            try:
                resource_status = metrics_api.get_gateway_status(client, gateway_id)
            except Exception:
                pass
            interfaces = None
            try:
                interfaces = gateways_api.get_gateway_interfaces(client, gateway_id)
            except Exception:
                pass

            if output == "json":
                click.echo(json.dumps(
                    {"details": details, "resource_status": resource_status, "interfaces": interfaces},
                    indent=2, default=str,
                ))
            else:
                cli_out.display_gateway_details(details, resource_status, interfaces)
            return

        data = gateways_api.get_gateways(client, gateway_type=gateway_type, search=search, limit=limit, page=page)

        if output == "json":
            click.echo(json.dumps(data, indent=2, default=str))

        elif output == "webhook":
            if not config.webhook_url:
                click.echo("Error: --webhook-url / ZTB_WEBHOOK_URL is required for webhook output.", err=True)
                sys.exit(1)
            unhealthy = []
            for cluster_row in data.get("rows", []):
                cluster_info = cluster_row.get("cluster_info", cluster_row.get("GatewayCluster", cluster_row))
                gw_list = cluster_row.get("gateways", cluster_info.get("gateways", []))
                if not gw_list:
                    gw_list = [cluster_info]
                for gw in gw_list:
                    state = str(gw.get("operational_state", gw.get("state", ""))).lower()
                    health = str(gw.get("health_color", "")).lower()
                    if state not in _HEALTHY_GW_STATES or health == "red":
                        unhealthy.append(gw)
            if unhealthy:
                webhook_out.alert_gateways_down(config.webhook_url, config.webhook_type, unhealthy)
                click.echo(f"Alert sent: {len(unhealthy)} unhealthy gateway(s).")
            else:
                click.echo("All gateways healthy — no alert sent.")

        elif output == "prometheus":
            def collect():
                gw_data = gateways_api.get_gateways(client, gateway_type=gateway_type, search=search, limit=limit, page=page)
                prom_out.update_all_gateway_metrics(
                    gw_data,
                    resource_fn=lambda gw_id: metrics_api.get_gateway_status(client, gw_id),
                )
            prom_out.start_exporter(prometheus_port, collect, interval)

        else:  # cli
            cli_out.display_gateways(data)

    except ZTBApiError as exc:
        click.echo(f"API error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--gateway-id", default="", envvar="ZTB_GATEWAY_ID", help="Gateway ID for resource stats.")
@click.option(
    "--prometheus-port",
    default=9090,
    show_default=True,
    envvar="ZTB_PROMETHEUS_PORT",
    help="Port for the Prometheus exporter (prometheus output only).",
)
@click.option(
    "--interval",
    default=60,
    show_default=True,
    envvar="ZTB_SCRAPE_INTERVAL",
    help="Collection interval in seconds (prometheus output only).",
)
@click.pass_context
def metrics(ctx, gateway_id, prometheus_port, interval):
    """Show infrastructure metrics (BGP, gateway, tunnels) or start Prometheus exporter.

    \b
    For Grafana integration, run:
        uv run main.py metrics --output prometheus [--gateway-id <id>]

    Then point Prometheus at http://<host>:<port>/metrics.
    """
    client: ZTBClient = ctx.obj["client"]
    config: Config = ctx.obj["config"]
    output: str = ctx.obj["output"]

    if output == "prometheus":
        # Define what gets collected every interval
        def collect():
            dev_data = devices_api.get_devices_v3(client)
            comp_data = events_api.get_compromised_devices(client)
            prom_out.update_device_metrics(dev_data, comp_data)

            try:
                bgp_data = metrics_api.get_bgp_status(client)
                prom_out.update_bgp_metrics(bgp_data)
            except Exception as exc:
                click.echo(f"[bgp] {exc}", err=True)

            if gateway_id:
                try:
                    gw_data = metrics_api.get_gateway_status(client, gateway_id)
                    prom_out.update_gateway_metrics(gw_data, gateway_id)
                except Exception as exc:
                    click.echo(f"[gateway] {exc}", err=True)

        prom_out.start_exporter(prometheus_port, collect, interval)
        return

    # For cli / json output, do a one-shot collection
    gathered: dict = {}

    try:
        gathered["bgp"] = metrics_api.get_bgp_status(client)
    except (ZTBApiError, requests.HTTPError) as exc:
        gathered["bgp_error"] = str(exc)

    try:
        gathered["site_info"] = metrics_api.get_site_info(client)
    except (ZTBApiError, requests.HTTPError) as exc:
        gathered["site_info_error"] = str(exc)

    try:
        gathered["gre_tunnels"] = metrics_api.get_gre_tunnels(client)
    except (ZTBApiError, requests.HTTPError) as exc:
        gathered["gre_tunnels_error"] = str(exc)

    try:
        gathered["vrrp"] = metrics_api.get_vrrp_status(client)
    except (ZTBApiError, requests.HTTPError) as exc:
        gathered["vrrp_error"] = str(exc)

    if gateway_id:
        try:
            gathered["gateway"] = metrics_api.get_gateway_status(client, gateway_id)
        except (ZTBApiError, requests.HTTPError) as exc:
            gathered["gateway_error"] = str(exc)

    if output == "json":
        click.echo(json.dumps(gathered, indent=2, default=str))
    else:
        if "bgp" in gathered:
            cli_out.display_bgp_status(gathered["bgp"])
        if "gateway" in gathered:
            cli_out.display_gateway_status(gathered["gateway"], gateway_id)
        if "gre_tunnels" in gathered:
            cli_out.display_tunnels(gathered["gre_tunnels"])
        # Site info is deeply nested — fall back to JSON panel
        if "site_info" in gathered:
            cli_out.display_json(gathered["site_info"])


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--gateway-id", required=True, envvar="ZTB_GATEWAY_ID", help="Gateway ID to check.")
@click.option("--device-id", default="", help="Device ID for DHCP check (interactive picker if omitted in CLI mode).")
@click.pass_context
def health(ctx, gateway_id, device_id):
    """Run DNS and DHCP health checks for a gateway."""
    client: ZTBClient = ctx.obj["client"]
    output: str = ctx.obj["output"]
    config: Config = ctx.obj["config"]

    results = []

    # --- DNS: check dnsproxy container ---
    try:
        gw_status = metrics_api.get_gateway_status(client, gateway_id)
        result = gw_status.get("result", gw_status)
        containers = result.get("containers_stats", {}) if isinstance(result, dict) else {}
        clist = containers.get("container_stats", []) if isinstance(containers, dict) else []
        dns_container = next((c for c in clist if "dnsproxy" in c.get("cname", "").lower()), None)

        if dns_container:
            cpu = dns_container.get("cpu", "0")
            mem = dns_container.get("memory", "0")
            results.append({
                "name": "DNS (dnsproxy container)",
                "status": "PASS",
                "details": f"CPU: {cpu}, Memory: {mem}",
            })
        else:
            results.append({
                "name": "DNS (dnsproxy container)",
                "status": "FAIL",
                "details": "dnsproxy container not found in gateway resource stats",
            })
    except Exception as exc:
        results.append({
            "name": "DNS (dnsproxy container)",
            "status": "FAIL",
            "details": f"Error fetching gateway status: {exc}",
        })

    # --- DHCP: recent events for a device ---
    try:
        # Resolve the device to check
        dev_data = devices_api.get_devices(client, limit=5)
        dev_rows = dev_data.get("result", {})
        if isinstance(dev_rows, dict):
            dev_rows = dev_rows.get("rows", [])
        elif not isinstance(dev_rows, list):
            dev_rows = []

        if not dev_rows:
            results.append({
                "name": "DHCP (lease history)",
                "status": "FAIL",
                "details": "No active devices found to check DHCP lease history",
            })
        else:
            selected = None
            if device_id:
                # Match the provided ID against the fetched list for the name
                selected = next(
                    (d for d in dev_rows
                     if d.get("id", d.get("device_id", "")) == device_id),
                    None,
                )
                if not selected:
                    # ID wasn't in the first page — use it directly
                    selected = {"id": device_id, "hostname": device_id}
            elif output == "cli":
                # Interactive picker
                click.echo("\nSelect a device for the DHCP check:")
                for idx, d in enumerate(dev_rows, 1):
                    did = d.get("id", d.get("device_id", ""))
                    name = d.get("hostname", d.get("device_name", "unknown"))
                    ip = d.get("ip_address", "")
                    mac = d.get("mac", d.get("mac_address", ""))
                    click.echo(f"  [{idx}] {name}  {ip}  {mac}  ({did})")
                choice = click.prompt(
                    "Device number", type=click.IntRange(1, len(dev_rows)), default=1,
                )
                selected = dev_rows[choice - 1]
            else:
                # Non-interactive: auto-select first device
                selected = dev_rows[0]

            sel_id = selected.get("id", selected.get("device_id", ""))
            sel_name = selected.get("hostname", selected.get("device_name", sel_id))

            # Fetch DHCP history for this device
            dhcp_data = devices_api.get_dhcp_history(client, sel_id, minutes=60)
            dhcp_result = dhcp_data.get("result", dhcp_data)
            ip_addresses = dhcp_result.get("ip_addresses", []) if isinstance(dhcp_result, dict) else []

            if ip_addresses:
                latest_ts = ip_addresses[0].get("timestamp", "unknown")
                latest_ip = ip_addresses[0].get("ip_address", "")
                results.append({
                    "name": "DHCP (lease history)",
                    "status": "PASS",
                    "details": f"{sel_name} — {latest_ip}, last lease: {latest_ts}",
                })
            else:
                results.append({
                    "name": "DHCP (lease history)",
                    "status": "FAIL",
                    "details": f"No DHCP lease history for {sel_name} ({sel_id})",
                })
    except Exception as exc:
        results.append({
            "name": "DHCP (lease history)",
            "status": "FAIL",
            "details": f"Error checking DHCP lease history: {exc}",
        })

    # --- Output ---
    try:
        if output == "json":
            click.echo(json.dumps(results, indent=2, default=str))

        elif output == "webhook":
            if not config.webhook_url:
                click.echo("Error: --webhook-url / ZTB_WEBHOOK_URL is required for webhook output.", err=True)
                sys.exit(1)
            failed = [r for r in results if r.get("status") == "FAIL"]
            if failed:
                webhook_out.alert_health_check(config.webhook_url, config.webhook_type, results)
                click.echo(f"Alert sent: {len(failed)} failed check(s).")
            else:
                click.echo("All health checks passed — no alert sent.")

        else:  # cli
            cli_out.display_health_status(results)

    except ZTBApiError as exc:
        click.echo(f"API error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli(obj={})
