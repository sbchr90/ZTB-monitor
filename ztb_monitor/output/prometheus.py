"""Prometheus metrics exporter.

Starts an HTTP server on ZTB_PROMETHEUS_PORT (default 9090) that Prometheus
can scrape. A background collection loop refreshes metrics every
ZTB_SCRAPE_INTERVAL seconds (default 60).
"""

import time
import threading
from typing import Callable, Optional

from prometheus_client import (
    CollectorRegistry,
    Gauge,
    start_http_server,
)

# Dedicated registry so we don't collide with the default one
REGISTRY = CollectorRegistry(auto_describe=True)

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

devices_total = Gauge(
    "ztb_devices_total", "Total number of active devices", registry=REGISTRY
)
devices_quarantined = Gauge(
    "ztb_devices_quarantined_total", "Devices currently quarantined", registry=REGISTRY
)
devices_offline = Gauge(
    "ztb_devices_offline_total", "Devices not in active/online state", registry=REGISTRY
)
compromised_total = Gauge(
    "ztb_compromised_devices_total", "Open compromised-device alerts", registry=REGISTRY
)
bgp_peer_up = Gauge(
    "ztb_bgp_peer_up",
    "BGP peer reachability (1=established, 0=down)",
    ["peer_ip", "cluster"],
    registry=REGISTRY,
)
gateway_cpu_percent = Gauge(
    "ztb_gateway_cpu_percent",
    "Gateway CPU utilisation (%)",
    ["gateway_id"],
    registry=REGISTRY,
)
gateway_memory_percent = Gauge(
    "ztb_gateway_memory_percent",
    "Gateway memory utilisation (%)",
    ["gateway_id"],
    registry=REGISTRY,
)
gateway_up = Gauge(
    "ztb_gateway_up",
    "Gateway reachability (1=healthy, 0=unhealthy)",
    ["gateway_id", "gateway_name", "cluster"],
    registry=REGISTRY,
)
gateway_disk_percent = Gauge(
    "ztb_gateway_disk_percent",
    "Gateway disk utilisation (%)",
    ["gateway_id"],
    registry=REGISTRY,
)
gateway_wan_latency_ms = Gauge(
    "ztb_gateway_wan_latency_ms",
    "Gateway WAN latency (ms)",
    ["gateway_id", "interface"],
    registry=REGISTRY,
)
gateway_wan_jitter_ms = Gauge(
    "ztb_gateway_wan_jitter_ms",
    "Gateway WAN jitter (ms)",
    ["gateway_id", "interface"],
    registry=REGISTRY,
)
gateway_wan_loss_percent = Gauge(
    "ztb_gateway_wan_loss_percent",
    "Gateway WAN packet loss (%)",
    ["gateway_id", "interface"],
    registry=REGISTRY,
)
scrape_errors_total = Gauge(
    "ztb_scrape_errors_total", "Consecutive scrape errors", registry=REGISTRY
)


# ---------------------------------------------------------------------------
# Update helpers (called by the collection loop)
# ---------------------------------------------------------------------------

_ACTIVE_STATUSES = {"active", "online", "connected"}


def update_device_metrics(devices_data: dict, compromised_data: dict) -> None:
    result = devices_data.get("result", {})
    rows = result.get("rows", []) if isinstance(result, dict) else []

    devices_total.set(len(rows))
    devices_quarantined.set(sum(1 for d in rows if d.get("is_quarantined")))
    devices_offline.set(
        sum(1 for d in rows if str(d.get("status", "")).lower() not in _ACTIVE_STATUSES)
    )

    comp_result = compromised_data.get("result", {})
    comp_rows = comp_result.get("rows", []) if isinstance(comp_result, dict) else []
    compromised_total.set(len(comp_rows))


def update_bgp_metrics(bgp_data: dict) -> None:
    result = bgp_data.get("result", {})
    peers = result if isinstance(result, list) else result.get("peers", [])
    for peer in (peers if isinstance(peers, list) else []):
        peer_ip = peer.get("peer_ip", peer.get("neighbor", "unknown"))
        cluster = str(peer.get("cluster_id", peer.get("site", "default")))
        up = 1 if str(peer.get("status", "")).lower() == "established" else 0
        bgp_peer_up.labels(peer_ip=peer_ip, cluster=cluster).set(up)


def update_gateway_metrics(gateway_data: dict, gateway_id: str) -> None:
    result = gateway_data.get("result", gateway_data)
    if not isinstance(result, dict):
        return
    cpu = result.get("cpu_percent", result.get("cpu_usage"))
    mem = result.get("memory_percent", result.get("memory_usage"))
    if cpu is not None:
        gateway_cpu_percent.labels(gateway_id=gateway_id).set(float(cpu))
    if mem is not None:
        gateway_memory_percent.labels(gateway_id=gateway_id).set(float(mem))


_HEALTHY_STATES = {"active", "online", "up", "running", "connected"}


def update_all_gateway_metrics(gateways_data: dict, resource_fn: Optional[Callable] = None) -> None:
    rows = gateways_data.get("rows", [])
    for cluster_row in rows:
        cluster_info = cluster_row.get("cluster_info", cluster_row.get("GatewayCluster", cluster_row))
        cluster_name = cluster_info.get("cluster_name", cluster_info.get("name", ""))
        gateways = cluster_row.get("gateways", cluster_info.get("gateways", []))
        if not gateways:
            gateways = [cluster_info]
        for gw in gateways:
            gw_id = str(gw.get("gateway_id", gw.get("id", "")))
            gw_name = gw.get("gateway_name", gw.get("display_name", gw.get("name", "")))
            state = str(gw.get("operational_state", gw.get("state", ""))).lower()
            health = str(gw.get("health_color", "")).lower()
            up = 1 if (state in _HEALTHY_STATES and health != "red") else 0
            gateway_up.labels(gateway_id=gw_id, gateway_name=gw_name, cluster=cluster_name).set(up)

            if resource_fn and gw_id:
                try:
                    res = resource_fn(gw_id)
                    update_gateway_metrics(res, gw_id)
                    result = res.get("result", res) if isinstance(res, dict) else {}
                    disk = result.get("disk_percent", result.get("disk_usage"))
                    if disk is not None:
                        gateway_disk_percent.labels(gateway_id=gw_id).set(float(disk))
                    # WAN metrics per interface
                    wan_interfaces = result.get("wan_interfaces", [])
                    if isinstance(wan_interfaces, list):
                        for iface in wan_interfaces:
                            iface_name = iface.get("name", iface.get("interface", ""))
                            latency = iface.get("latency")
                            jitter = iface.get("jitter")
                            loss = iface.get("packet_loss", iface.get("loss"))
                            if latency is not None:
                                gateway_wan_latency_ms.labels(gateway_id=gw_id, interface=iface_name).set(float(latency))
                            if jitter is not None:
                                gateway_wan_jitter_ms.labels(gateway_id=gw_id, interface=iface_name).set(float(jitter))
                            if loss is not None:
                                gateway_wan_loss_percent.labels(gateway_id=gw_id, interface=iface_name).set(float(loss))
                except Exception:
                    pass  # One broken gateway shouldn't break the loop


# ---------------------------------------------------------------------------
# Exporter entry point
# ---------------------------------------------------------------------------

def start_exporter(port: int, collect_fn: Callable, interval: int = 60) -> None:
    """Start the Prometheus HTTP server and block, collecting metrics on interval."""
    start_http_server(port, registry=REGISTRY)
    print(f"[ztb-monitor] Prometheus exporter listening on :{port}/metrics")
    print(f"[ztb-monitor] Scrape interval: {interval}s  (Ctrl+C to stop)")

    consecutive_errors = 0
    while True:
        try:
            collect_fn()
            consecutive_errors = 0
            scrape_errors_total.set(0)
        except Exception as exc:
            consecutive_errors += 1
            scrape_errors_total.set(consecutive_errors)
            print(f"[ztb-monitor] Scrape error ({consecutive_errors}): {exc}")
        time.sleep(interval)
