import json
from typing import Any, Optional

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.text import Text

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rows_from(data: dict, *keys: str) -> list:
    """Drill into nested dicts to find a list of rows."""
    result = data.get("result", data)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for k in keys:
            if k in result:
                v = result[k]
                if isinstance(v, list):
                    return v
        # Fallback: return dict values if it looks like a map of items
    return []


def _status_style(status: str) -> str:
    s = status.lower()
    if s in ("active", "online", "connected", "established", "up"):
        return "green"
    if s in ("offline", "disconnected", "down", "inactive"):
        return "red"
    return "yellow"


# ---------------------------------------------------------------------------
# Device tables
# ---------------------------------------------------------------------------

def display_devices(data: dict) -> None:
    rows = _rows_from(data, "rows", "data", "devices")

    table = Table(title="Active Devices", box=box.ROUNDED, highlight=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Hostname", style="bold")
    table.add_column("IP Address")
    table.add_column("MAC")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Location")
    table.add_column("Quarantined", justify="center")

    for d in rows:
        status = d.get("status", "")
        quarantined = d.get("is_quarantined", False)
        q_text = Text("YES", style="bold red") if quarantined else Text("NO", style="green")
        device_type = d.get("device_type") or (
            d.get("type", [""])[0] if isinstance(d.get("type"), list) else d.get("type", "")
        )
        table.add_row(
            str(d.get("id", d.get("device_id", ""))),
            d.get("hostname", d.get("device_name", "")),
            d.get("ip_address", ""),
            d.get("mac", d.get("mac_address", "")),
            Text(status, style=_status_style(status)),
            str(device_type),
            d.get("location", ""),
            q_text,
        )

    console.print(table)
    _print_pagination(data)


def display_device_details(details: dict, metrics: dict) -> None:
    result = details.get("result", details)
    if isinstance(result, dict):
        console.print(Panel(
            json.dumps(result, indent=2),
            title="Device Details",
            border_style="blue",
        ))
    if metrics:
        metrics_result = metrics.get("result", metrics)
        console.print(Panel(
            json.dumps(metrics_result, indent=2),
            title="Device Metrics",
            border_style="cyan",
        ))


# ---------------------------------------------------------------------------
# Event / audit log table
# ---------------------------------------------------------------------------

def display_events(data: dict) -> None:
    rows = _rows_from(data, "rows", "data", "logs")

    table = Table(title="Device Events / Audit Log", box=box.ROUNDED)
    table.add_column("Timestamp", style="dim", no_wrap=True)
    table.add_column("Device")
    table.add_column("IP")
    table.add_column("MAC")
    table.add_column("Event")
    table.add_column("Site")

    for e in rows:
        table.add_row(
            str(e.get("createdAt", e.get("timestamp", e.get("event_time", "")))),
            e.get("hostname", e.get("device_name", "")),
            e.get("ip_address", ""),
            e.get("mac", e.get("mac_address", "")),
            e.get("event_type", e.get("action", e.get("type", ""))),
            e.get("site_name", ""),
        )

    console.print(table)
    _print_pagination(data)


# ---------------------------------------------------------------------------
# Security alerts table
# ---------------------------------------------------------------------------

def display_compromised_devices(data: dict) -> None:
    rows = _rows_from(data, "rows", "data", "devices")

    table = Table(
        title="[bold red]Security Alerts — Compromised Devices[/bold red]",
        box=box.ROUNDED,
        border_style="red",
    )
    table.add_column("Device", style="bold")
    table.add_column("Device IP")
    table.add_column("Attack Type", style="red")
    table.add_column("Target IP")
    table.add_column("Status")
    table.add_column("Site")
    table.add_column("First Seen", style="dim")
    table.add_column("Count", justify="right")

    for d in rows:
        table.add_row(
            d.get("compromised_device_name", ""),
            d.get("compromised_device_ip", ""),
            d.get("attack_type", ""),
            d.get("target_device_ip", ""),
            d.get("status", ""),
            d.get("site_name", ""),
            str(d.get("first_occurence", "")),
            str(d.get("count", "")),
        )

    if not rows:
        console.print("[green]No compromised devices found.[/green]")
    else:
        console.print(table)
    _print_pagination(data)


# ---------------------------------------------------------------------------
# Infrastructure metrics tables
# ---------------------------------------------------------------------------

def display_bgp_status(data: dict) -> None:
    result = data.get("result", data)
    peers = result if isinstance(result, list) else result.get("peers", [])

    table = Table(title="BGP Status", box=box.ROUNDED)
    table.add_column("Peer IP")
    table.add_column("Status")
    table.add_column("Remote AS")
    table.add_column("Routes Received", justify="right")
    table.add_column("Cluster / Site", style="dim")

    for peer in (peers if isinstance(peers, list) else []):
        status = peer.get("status", "")
        table.add_row(
            peer.get("peer_ip", peer.get("neighbor", "")),
            Text(status, style=_status_style(status)),
            str(peer.get("remote_as", peer.get("as", ""))),
            str(peer.get("routes_received", peer.get("routes", ""))),
            str(peer.get("cluster_id", peer.get("site", ""))),
        )

    console.print(table)


def display_gateway_status(data: dict, gateway_id: str = "") -> None:
    result = data.get("result", data)
    title = f"Gateway Resource Status — {gateway_id}" if gateway_id else "Gateway Resource Status"

    if not isinstance(result, dict):
        return

    # --- System Stats ---
    sys_stats = result.get("system_stats", {})
    if sys_stats:
        st = Table(title="System Resources", box=box.ROUNDED)
        st.add_column("Resource", style="bold")
        st.add_column("Used", justify="right")
        st.add_column("Free", justify="right")
        st.add_column("Total", justify="right")

        cpu = sys_stats.get("cpu", {})
        mem = sys_stats.get("memory", {})
        disk = sys_stats.get("disk", {})
        swap = sys_stats.get("swap", {})

        st.add_row("CPU", f"{cpu.get('used', '')}%", f"{cpu.get('free', '')}%", "—")
        st.add_row("Memory", f"{mem.get('used', 0):.2f} GB", f"{mem.get('free', 0):.2f} GB", f"{mem.get('total', 0):.2f} GB")
        st.add_row("Disk", f"{disk.get('used', '')} GB", f"{disk.get('free', '')} GB", f"{disk.get('total', '')} GB")
        swap_used = swap.get("used", 0)
        st.add_row("Swap", f"{swap_used} GB" if swap_used else "0", "—", "—")
        console.print(st)

    # --- Uptime ---
    uptime = result.get("device_uptime", "")
    if uptime:
        console.print(f"  [bold]Uptime:[/bold] {uptime}")
        console.print()

    # --- Peak / Low ---
    peaks = result.get("peak_low_values", {})
    if peaks:
        pt = Table(title="Peak / Low (24 h)", box=box.ROUNDED)
        pt.add_column("Metric", style="bold")
        pt.add_column("Peak", justify="right")
        pt.add_column("Low", justify="right")
        pt.add_row("CPU %", str(peaks.get("cpu_used_peak", "")), str(peaks.get("cpu_used_low", "")))
        pt.add_row("Memory GB", str(peaks.get("mem_used_peak", "")), str(peaks.get("mem_used_low", "")))
        pt.add_row("Disk GB", str(peaks.get("disk_used_peak", "")), str(peaks.get("disk_used_low", "")))
        pt.add_row("Swap GB", str(peaks.get("swap_used_peak", "")), str(peaks.get("swap_used_low", "")))
        console.print(pt)

    # --- Containers ---
    containers = result.get("containers_stats", {})
    clist = containers.get("container_stats", []) if isinstance(containers, dict) else []
    if clist:
        ct = Table(title="Containers", box=box.ROUNDED)
        ct.add_column("Container", style="bold")
        ct.add_column("CPU %", justify="right")
        ct.add_column("Memory", justify="right")
        for c in clist:
            ct.add_row(c.get("cname", ""), c.get("cpu", ""), c.get("memory", ""))
        console.print(ct)

    # --- Hourly Averages ---
    avg = result.get("average_values", {})
    hourly = avg.get("hourly_stats", []) if isinstance(avg, dict) else []
    if hourly:
        at = Table(title="Hourly Averages (24 h)", box=box.ROUNDED)
        at.add_column("Hour", style="dim", no_wrap=True)
        at.add_column("CPU %", justify="right", no_wrap=True)
        at.add_column("Mem Used", justify="right", no_wrap=True)
        at.add_column("Mem Free", justify="right", no_wrap=True)
        at.add_column("Disk Used", justify="right", no_wrap=True)
        at.add_column("Disk Free", justify="right", no_wrap=True)
        for h in hourly:
            start = h.get("start_time", "")
            end = h.get("end_time", "")
            # Show "Mar 19 09:00–10:00" style
            try:
                s_time = start.split(" ")[1][:5] if " " in start else start
                e_time = end.split(" ")[1][:5] if " " in end else end
                s_date = start.split(" ")[0][5:] if " " in start else ""  # MM-DD
                window = f"{s_date} {s_time}–{e_time}"
            except (IndexError, AttributeError):
                window = f"{start}–{end}"
            at.add_row(
                window,
                str(h.get("cpu_used_avg", "")),
                str(h.get("mem_used_avg", "")),
                str(h.get("mem_free_avg", "")),
                str(h.get("disk_used_avg", "")),
                str(h.get("disk_free_avg", "")),
            )
        console.print(at)

    # --- WAN Monitor Current ---
    wanmon = result.get("wanmon_status", [])
    if wanmon and isinstance(wanmon, list):
        wt = Table(title="WAN Monitor — Current", box=box.ROUNDED)
        wt.add_column("Interface", style="bold")
        wt.add_column("Loss %", justify="right")
        wt.add_column("Jitter ms", justify="right")
        wt.add_column("Latency ms", justify="right")
        wt.add_column("Score", justify="right")
        for w in wanmon:
            wt.add_row(
                w.get("wan_intf_name", ""),
                w.get("loss", ""),
                w.get("jitter", ""),
                w.get("latency", ""),
                w.get("score", ""),
            )
        console.print(wt)

    # --- WAN Monitor Averages ---
    wanmon_avg = result.get("wanmon_avg_values", [])
    if wanmon_avg and isinstance(wanmon_avg, list):
        wa = Table(title="WAN Monitor — Hourly Averages", box=box.ROUNDED)
        wa.add_column("Hour", style="dim", no_wrap=True)
        wa.add_column("Interface", style="bold")
        wa.add_column("Loss %", justify="right", no_wrap=True)
        wa.add_column("Jitter ms", justify="right", no_wrap=True)
        wa.add_column("Latency ms", justify="right", no_wrap=True)
        wa.add_column("Score", justify="right", no_wrap=True)
        for entry in wanmon_avg:
            start = entry.get("start_time", "")
            end = entry.get("end_time", "")
            try:
                s_time = start.split(" ")[1][:5] if " " in start else start
                e_time = end.split(" ")[1][:5] if " " in end else end
                s_date = start.split(" ")[0][5:] if " " in start else ""
                window = f"{s_date} {s_time}–{e_time}"
            except (IndexError, AttributeError):
                window = f"{start}–{end}"
            for iface in entry.get("interfaces", []):
                wa.add_row(
                    window,
                    iface.get("wan_intf_name", ""),
                    iface.get("loss", ""),
                    iface.get("jitter", ""),
                    iface.get("latency", ""),
                    iface.get("score", ""),
                )
        console.print(wa)

    # --- Any remaining keys we didn't handle ---
    handled = {"system_stats", "device_uptime", "peak_low_values", "containers_stats",
               "average_values", "wanmon_status", "wanmon_avg_values", "gateway_id"}
    remaining = {k: v for k, v in result.items() if k not in handled}
    if remaining:
        ft = Table(title="Other", box=box.ROUNDED)
        ft.add_column("Metric")
        ft.add_column("Value", justify="right")
        for key, value in remaining.items():
            ft.add_row(key, str(value))
        console.print(ft)


def display_tunnels(data: dict) -> None:
    rows = _rows_from(data, "rows", "tunnels", "data")

    table = Table(title="GRE Tunnels", box=box.ROUNDED)
    table.add_column("Tunnel ID / Name")
    table.add_column("Local")
    table.add_column("Remote")
    table.add_column("Status")

    for t in (rows if rows else ([data.get("result", {})] if isinstance(data.get("result"), dict) else [])):
        status = t.get("status", t.get("state", ""))
        table.add_row(
            str(t.get("tunnel_id", t.get("name", ""))),
            t.get("local_ip", t.get("local", "")),
            t.get("remote_ip", t.get("remote", "")),
            Text(status, style=_status_style(status)),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Gateway tables
# ---------------------------------------------------------------------------

def display_gateways(data: dict) -> None:
    rows = data.get("rows", [])
    total = data.get("count", 0)

    table = Table(title="Gateways", box=box.ROUNDED, highlight=True)
    table.add_column("Gateway ID", style="dim", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("IP Address")
    table.add_column("Public IP")
    table.add_column("State")
    table.add_column("Health")
    table.add_column("Version")
    table.add_column("VRRP")
    table.add_column("Last Poll", style="dim")
    table.add_column("Cluster / Site", style="dim")

    for cluster_row in rows:
        cluster_info = cluster_row.get("cluster_info", cluster_row.get("GatewayCluster", cluster_row))
        cluster_name = cluster_info.get("cluster_name", cluster_info.get("name", ""))
        location = cluster_row.get("location_display_name", cluster_row.get("location", ""))
        site_label = f"{cluster_name} / {location}" if location and cluster_name else (cluster_name or location)
        gateways = cluster_row.get("gateways", cluster_info.get("gateways", []))
        if not gateways:
            # Flat structure — treat the row itself as a gateway
            gateways = [cluster_info]
        for gw in gateways:
            state = gw.get("operational_state", gw.get("state", ""))
            health = gw.get("health_color", "")
            health_style = {"green": "green", "red": "red", "yellow": "yellow"}.get(health.lower(), "dim")
            table.add_row(
                str(gw.get("gateway_id", gw.get("id", ""))),
                gw.get("gateway_name", gw.get("display_name", gw.get("name", ""))),
                gw.get("gateway_ip_address", gw.get("ip_address", "")),
                gw.get("public_ip", ""),
                Text(state, style=_status_style(state)),
                Text(health or "-", style=health_style),
                gw.get("running_version", gw.get("version", "")),
                gw.get("vrrp_state", ""),
                str(gw.get("last_poll_updated", gw.get("last_poll", ""))),
                site_label,
            )

    console.print(table)
    console.print(f"[dim]Total: {total} gateway(s)[/dim]")


def display_gateway_details(details: dict, resource_status: Optional[dict], interfaces: Optional[dict]) -> None:
    result = details.get("result", details)
    if isinstance(result, dict):
        kv_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        kv_table.add_column("Key", style="bold")
        kv_table.add_column("Value")

        fields = [
            ("Gateway ID", result.get("gateway_id", result.get("id", ""))),
            ("Name", result.get("name", result.get("gateway_name", ""))),
            ("IP Address", result.get("ip_address", "")),
            ("Public IP", result.get("public_ip", "")),
            ("State", result.get("operational_state", result.get("state", ""))),
            ("Health", result.get("health_color", "")),
            ("Version", result.get("version", "")),
            ("Build", result.get("build_version", "")),
            ("VRRP State", result.get("vrrp_state", "")),
            ("NAT Enabled", str(result.get("nat_enabled", ""))),
            ("WireGuard", str(result.get("wireguard_enabled", ""))),
            ("Last Poll", str(result.get("last_poll", ""))),
        ]
        for key, val in fields:
            if val:
                kv_table.add_row(key, str(val))

        console.print(Panel(kv_table, title="Gateway Details", border_style="blue"))

    if resource_status:
        gw_id = str(result.get("gateway_id", result.get("id", ""))) if isinstance(result, dict) else ""
        display_gateway_status(resource_status, gw_id)

    if interfaces:
        iface_rows = _rows_from(interfaces, "rows", "data", "interfaces")
        if iface_rows:
            itable = Table(title="Interfaces", box=box.ROUNDED)
            itable.add_column("Name")
            itable.add_column("IP")
            itable.add_column("Admin State")
            itable.add_column("Oper State")
            itable.add_column("Speed")
            itable.add_column("RX Bytes", justify="right")
            itable.add_column("TX Bytes", justify="right")

            for iface in iface_rows:
                admin = iface.get("admin_state", "")
                oper = iface.get("operational_state", iface.get("oper_state", ""))
                stats = iface.get("if_stats", {}) or {}
                itable.add_row(
                    iface.get("name", iface.get("interface_name", "")),
                    iface.get("ip_address", iface.get("ip", "")),
                    Text(admin, style=_status_style(admin)),
                    Text(oper, style=_status_style(oper)),
                    str(iface.get("speed", "")),
                    str(stats.get("rx_bytes", "")),
                    str(stats.get("tx_bytes", "")),
                )

            console.print(itable)


# ---------------------------------------------------------------------------
# Health check table
# ---------------------------------------------------------------------------

def display_health_status(results: list) -> None:
    """Display health check results as a summary table."""
    table = Table(title="Health Check", box=box.ROUNDED, highlight=True)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    for check in results:
        status = check.get("status", "UNKNOWN")
        style = "green" if status == "PASS" else "red" if status == "FAIL" else "yellow"
        table.add_row(
            check.get("name", ""),
            Text(status, style=f"bold {style}"),
            check.get("details", ""),
        )

    console.print(table)

    passed = sum(1 for c in results if c.get("status") == "PASS")
    total = len(results)
    overall_style = "green" if passed == total else "red"
    console.print(f"[{overall_style}]{passed}/{total} checks passed[/{overall_style}]")


# ---------------------------------------------------------------------------
# Generic / JSON fallback
# ---------------------------------------------------------------------------

def display_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


# ---------------------------------------------------------------------------
# Pagination hint
# ---------------------------------------------------------------------------

def _print_pagination(data: dict) -> None:
    result = data.get("result", {})
    if not isinstance(result, dict):
        return
    total = result.get("total", result.get("count"))
    page = result.get("page", result.get("currentPage"))
    limit = result.get("limit", result.get("pageSize"))
    if total is not None:
        console.print(
            f"[dim]Showing {limit or '?'} of {total} total  |  page {page or 1}[/dim]"
        )
