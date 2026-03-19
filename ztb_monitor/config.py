import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    base_url: str = field(default_factory=lambda: os.environ.get("ZTB_BASE_URL", "https://sbcorp-api.goairgap.com"))
    # Static API key used to obtain a delegate bearer token via the login endpoint
    api_key: str = field(default_factory=lambda: os.environ.get("ZTB_API_KEY", ""))
    # JWT delegate token returned by the login endpoint; persisted to .env
    bearer_token: str = field(default_factory=lambda: os.environ.get("ZTB_BEARER_TOKEN", ""))
    webhook_url: str = field(default_factory=lambda: os.environ.get("ZTB_WEBHOOK_URL", ""))
    webhook_type: str = field(default_factory=lambda: os.environ.get("ZTB_WEBHOOK_TYPE", "generic"))
    prometheus_port: int = field(default_factory=lambda: int(os.environ.get("ZTB_PROMETHEUS_PORT", "9090")))
    scrape_interval: int = field(default_factory=lambda: int(os.environ.get("ZTB_SCRAPE_INTERVAL", "60")))
    timeout: int = field(default_factory=lambda: int(os.environ.get("ZTB_TIMEOUT", "30")))

    def validate(self):
        if not self.api_key:
            raise ValueError("ZTB_API_KEY is required (set via env var or --api-key flag)")
        if not self.base_url:
            raise ValueError("ZTB_BASE_URL is required")
