from ..client import ZTBClient


def get_devices(
    client: ZTBClient,
    search: str = "",
    site_id: str = "",
    limit: int = 100,
    page: int = 1,
    tags: str = "",
) -> dict:
    """List active devices (v2 endpoint, lightweight)."""
    params: dict = {"limit": limit, "page": page}
    if search:
        params["search"] = search
    if site_id:
        params["siteId"] = site_id
    if tags:
        params["tags"] = tags
    return client.get("/api/v2/devices/active", params=params)


def get_devices_v3(
    client: ZTBClient,
    search: str = "",
    limit: int = 100,
    page: int = 1,
    device_type: str = "",
    category: str = "",
    full: bool = True,
) -> dict:
    """List devices using v3 endpoint with richer filtering and schema."""
    params: dict = {"limit": limit, "page": page, "full": full}
    if search:
        params["search"] = search
    if device_type:
        params["type"] = device_type
    if category:
        params["category"] = category
    return client.get("/api/v3/device", params=params)


def get_device_details(client: ZTBClient, device_id: str) -> dict:
    """Get comprehensive device details via v3 endpoint."""
    return client.get(f"/api/v3/device/details/{device_id}")


def get_device_metrics(client: ZTBClient, device_id: str, minutes: int = 60) -> dict:
    """Get device metrics over a rolling time window (minutes)."""
    return client.get(f"/api/v2/devices/active/details/{device_id}/{minutes}")


def get_dhcp_history(client: ZTBClient, device_id: str, minutes: int = 60) -> dict:
    """Get DHCP history for a device over a rolling time window.

    Returns ip_addresses with timestamps showing DHCP lease refreshes.
    """
    return client.get(f"/api/v2/devices/details/id/{device_id}/{minutes}")


def get_device_tags(client: ZTBClient) -> dict:
    """Get all available device tags."""
    return client.get("/api/v2/devices/tags")
