from ..client import ZTBClient


def get_gateways(
    client: ZTBClient,
    gateway_type: str = "",
    search: str = "",
    limit: int = 100,
    page: int = 1,
) -> dict:
    """List gateways. When gateway_type is empty, fetch both types and merge.

    The CLI uses 1-based pages; the v3 Gateway API is 0-based, so we
    convert here.
    """
    api_page = max(page - 1, 0)
    if not gateway_type:
        iso = _fetch_gateways(client, "isolation", search, limit, api_page)
        acc = _fetch_gateways(client, "access", search, limit, api_page)
        iso_rows = iso.get("rows", [])
        acc_rows = acc.get("rows", [])
        return {
            "rows": iso_rows + acc_rows,
            "count": iso.get("count", 0) + acc.get("count", 0),
        }
    return _fetch_gateways(client, gateway_type, search, limit, api_page)


def _fetch_gateways(
    client: ZTBClient,
    gateway_type: str,
    search: str,
    limit: int,
    page: int,
) -> dict:
    params: dict = {"gateway_type": gateway_type, "limit": limit, "page": page}
    if search:
        params["search"] = search
    return client.get("/api/v3/Gateway/", params=params)


def get_gateway_details(client: ZTBClient, gateway_id: str) -> dict:
    """Get detailed info for a single gateway."""
    return client.get(f"/api/v3/Gateway/id/{gateway_id}")


def get_gateway_interfaces(
    client: ZTBClient,
    gateway_id: str = "",
    limit: int = 100,
    page: int = 1,
) -> dict:
    """Get network interfaces for a gateway."""
    params: dict = {"limit": limit, "page": page}
    if gateway_id:
        params["gatewayId"] = gateway_id
    return client.get("/api/v2/Gateway/interfaces", params=params)
