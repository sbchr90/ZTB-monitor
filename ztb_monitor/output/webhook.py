"""Webhook alert sender.

Supports three payload formats:
  - generic  : plain JSON envelope (works with n8n, Zapier, custom endpoints)
  - slack     : Slack Incoming Webhook attachment format
  - teams     : Microsoft Teams MessageCard format
"""

import requests
from datetime import datetime, timezone
from typing import Any, List, Dict, Optional


# ---------------------------------------------------------------------------
# Low-level sender
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict, timeout: int = 10) -> None:
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Format builders
# ---------------------------------------------------------------------------

def _generic_payload(title: str, message: str, severity: str, data: Any = None) -> dict:
    return {
        "source": "ztb-monitor",
        "severity": severity,
        "title": title,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def _slack_payload(title: str, message: str, severity: str, fields: Optional[List[Dict]] = None) -> dict:
    color = {"critical": "#FF0000", "warning": "#FFA500", "info": "#36A2EB"}.get(severity, "#808080")
    attachment: dict = {
        "color": color,
        "title": title,
        "text": message,
        "ts": int(datetime.now(timezone.utc).timestamp()),
        "footer": "ZTB Monitor",
    }
    if fields:
        attachment["fields"] = fields
    return {"attachments": [attachment]}


def _teams_payload(title: str, message: str, severity: str, facts: Optional[List[Dict]] = None) -> dict:
    color = {"critical": "FF0000", "warning": "FFA500", "info": "36A2EB"}.get(severity, "808080")
    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": title,
        "sections": [{
            "activityTitle": title,
            "activityText": message,
            "facts": facts or [],
        }],
    }


# ---------------------------------------------------------------------------
# Public send helpers
# ---------------------------------------------------------------------------

def send_alert(
    url: str,
    webhook_type: str,
    title: str,
    message: str,
    severity: str = "warning",
    data: Any = None,
) -> None:
    """Send an alert to the configured webhook endpoint."""
    if webhook_type == "slack":
        fields = None
        if isinstance(data, list):
            fields = [
                {"title": str(d.get("name", d.get("device_name", d.get("hostname", "")))),
                 "value": str(d.get("detail", d.get("attack_type", d.get("status", "")))),
                 "short": True}
                for d in data[:10]
            ]
        payload = _slack_payload(title, message, severity, fields)
    elif webhook_type == "teams":
        facts = None
        if isinstance(data, list):
            facts = [
                {"name": str(d.get("name", d.get("device_name", d.get("hostname", "")))),
                 "value": str(d.get("detail", d.get("attack_type", d.get("status", ""))))}
                for d in data[:10]
            ]
        payload = _teams_payload(title, message, severity, facts)
    else:
        payload = _generic_payload(title, message, severity, data)

    _post(url, payload)


# ---------------------------------------------------------------------------
# Domain-specific alert builders
# ---------------------------------------------------------------------------

def alert_compromised_devices(url: str, webhook_type: str, devices: list) -> None:
    """Alert on compromised / blacklisted devices."""
    if not devices:
        return
    title = f"ZTB Security Alert: {len(devices)} Compromised Device(s) Detected"
    lines = [
        f"• {d.get('compromised_device_name', 'Unknown')} "
        f"({d.get('compromised_device_ip', '')}) — "
        f"{d.get('attack_type', 'Unknown')} @ {d.get('site_name', '')}"
        for d in devices
    ]
    # Enrich items for format helpers
    enriched = [
        {
            "name": d.get("compromised_device_name", "Unknown"),
            "detail": d.get("attack_type", ""),
        }
        for d in devices
    ]
    send_alert(url, webhook_type, title, "\n".join(lines), severity="critical", data=enriched)


def alert_offline_devices(url: str, webhook_type: str, devices: list) -> None:
    """Alert on devices that appear offline."""
    if not devices:
        return
    title = f"ZTB Alert: {len(devices)} Device(s) Offline"
    lines = [
        f"• {d.get('hostname', d.get('device_name', 'Unknown'))} ({d.get('ip_address', '')})"
        for d in devices
    ]
    enriched = [
        {
            "name": d.get("hostname", d.get("device_name", "Unknown")),
            "detail": f"Status: {d.get('status', 'offline')}",
        }
        for d in devices
    ]
    send_alert(url, webhook_type, title, "\n".join(lines), severity="warning", data=enriched)


def alert_gateways_down(url: str, webhook_type: str, gateways: list) -> None:
    """Alert when gateways are unhealthy or down."""
    if not gateways:
        return
    title = f"ZTB Gateway Alert: {len(gateways)} Gateway(s) Unhealthy"
    lines = [
        f"• {g.get('name', g.get('gateway_name', 'Unknown'))} "
        f"({g.get('ip_address', '')}) — "
        f"state: {g.get('operational_state', g.get('state', 'unknown'))}, "
        f"health: {g.get('health_color', 'unknown')}"
        for g in gateways
    ]
    enriched = [
        {
            "name": g.get("name", g.get("gateway_name", "Unknown")),
            "detail": f"State: {g.get('operational_state', g.get('state', 'unknown'))}, "
                      f"Health: {g.get('health_color', 'unknown')}",
        }
        for g in gateways
    ]
    send_alert(url, webhook_type, title, "\n".join(lines), severity="critical", data=enriched)


def alert_health_check(url: str, webhook_type: str, results: list) -> None:
    """Alert when one or more health checks fail."""
    failed = [r for r in results if r.get("status") == "FAIL"]
    if not failed:
        return
    title = f"ZTB Health Alert: {len(failed)} Check(s) Failed"
    lines = [f"• {r.get('name', 'Unknown')}: {r.get('details', '')}" for r in failed]
    enriched = [
        {"name": r.get("name", "Unknown"), "detail": r.get("details", "")}
        for r in failed
    ]
    send_alert(url, webhook_type, title, "\n".join(lines), severity="critical", data=enriched)


def alert_bgp_down(url: str, webhook_type: str, peers: list) -> None:
    """Alert when BGP peers are not established."""
    if not peers:
        return
    title = f"ZTB BGP Alert: {len(peers)} Peer(s) Down"
    lines = [
        f"• {p.get('peer_ip', p.get('neighbor', 'Unknown'))} — {p.get('status', 'down')}"
        for p in peers
    ]
    enriched = [
        {
            "name": p.get("peer_ip", p.get("neighbor", "Unknown")),
            "detail": f"Status: {p.get('status', 'down')}",
        }
        for p in peers
    ]
    send_alert(url, webhook_type, title, "\n".join(lines), severity="critical", data=enriched)
