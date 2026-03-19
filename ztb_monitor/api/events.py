from ..client import ZTBClient


def get_audit_logs(
    client: ZTBClient,
    search: str = "",
    site_id: str = "",
    limit: int = 100,
    page: int = 1,
    sort: str = "createdAt",
    sortdir: str = "desc",
) -> dict:
    """Fetch DHCP event audit logs."""
    params: dict = {"limit": limit, "page": page, "sort": sort, "sortdir": sortdir}
    if search:
        params["search"] = search
    if site_id:
        params["siteId"] = site_id
    return client.get("/api/v2/devices/auditlog", params=params)


def get_compromised_devices(
    client: ZTBClient,
    tab: str = "all",
    search: str = "",
    site_id: str = "",
    limit: int = 100,
    page: int = 1,
) -> dict:
    """Fetch compromised / blacklisted device alerts.

    tab options: all, blacklist, quarantine, etc. (as exposed in the UI)
    """
    params: dict = {"limit": limit, "page": page}
    if search:
        params["search"] = search
    if site_id:
        params["siteId"] = site_id
    return client.get(f"/api/v2/compromised-device/get/{tab}", params=params)
