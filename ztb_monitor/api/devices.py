from ..client import ZTBClient


def get_devices(
    client: ZTBClient,
    search: str = "",
    site_id: str = "",
    limit: int = 5,
    page: int = 1,
    tags: str = "",
) -> dict:
    """List active devices (v2 endpoint, lightweight).

    The v2 API's server-side ``search`` param acknowledges matches (via
    ``count``) but returns empty ``rows``, so filtering is done client-side.
    Pagination uses small page sizes because the endpoint returns fewer
    rows as ``limit`` increases (drops to zero above ~8).
    """
    _PAGE_SIZE = 5

    if search:
        all_rows = _fetch_all_devices(client, site_id=site_id, tags=tags, page_size=_PAGE_SIZE)
        term = search.lower()
        filtered = [
            d for d in all_rows
            if term in d.get("hostname", "").lower()
            or term in d.get("device_name", "").lower()
            or term in d.get("ip_address", "").lower()
            or term in d.get("mac", "").lower()
            or term in d.get("mac_address", "").lower()
        ]
        return {"result": {"count": len(filtered), "rows": filtered}}

    params: dict = {"limit": limit, "page": page}
    if site_id:
        params["siteId"] = site_id
    if tags:
        params["tags"] = tags
    return client.get("/api/v2/devices/active", params=params)


def _fetch_all_devices(
    client: ZTBClient,
    site_id: str = "",
    tags: str = "",
    page_size: int = 5,
) -> list:
    """Paginate through all active devices with a small page size."""
    all_rows: list = []
    page = 1
    while True:
        params: dict = {"limit": page_size, "page": page}
        if site_id:
            params["siteId"] = site_id
        if tags:
            params["tags"] = tags
        data = client.get("/api/v2/devices/active", params=params)
        result = data.get("result", {})
        rows = result.get("rows", []) if isinstance(result, dict) else []
        if not rows:
            break
        all_rows.extend(rows)
        total = result.get("count", 0) if isinstance(result, dict) else 0
        if len(all_rows) >= total:
            break
        page += 1
    return all_rows


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
