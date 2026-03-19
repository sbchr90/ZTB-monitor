from ..client import ZTBClient


def get_gateway_status(client: ZTBClient, gateway_id: str) -> dict:
    """Get CPU / memory / connection stats for a specific gateway."""
    return client.get("/api/v3/debug-manager/resource-status", params={"gateway_id": gateway_id})


def get_bgp_status(client: ZTBClient) -> dict:
    """Get overall BGP peer status across all clusters."""
    return client.get("/api/v3/Bgp/bgpstatus")


def get_bgp_status_by_cluster(client: ZTBClient, cluster_id: str) -> dict:
    """Get BGP status for a specific cluster."""
    return client.get(f"/api/v3/Bgp/bgpstatus/{cluster_id}")


def get_gre_tunnels(client: ZTBClient) -> dict:
    """List all GRE tunnels and their status."""
    return client.get("/api/v3/gre/all-tunnels")


def get_vrrp_status(client: ZTBClient) -> dict:
    """Get VRRP (high-availability) status."""
    return client.get("/api/v3/vrrp/vrrpstatus")


def get_site_info(client: ZTBClient) -> dict:
    """Get aggregated site / branch summary information."""
    return client.get("/api/v2/dashboard/site-info")


def get_mssp_cards(client: ZTBClient, time_range: str = "-7d", top: int = 10) -> dict:
    """Get MSSP dashboard card metrics (top sites, top devices, etc.)."""
    return client.get("/api/v2/dashboard/mssp/cards", params={"time_range": time_range, "top": top})


def get_device_posture_profiles(client: ZTBClient) -> dict:
    """Get device posture compliance profiles."""
    return client.get("/api/v3/deviceposture/profiles")
