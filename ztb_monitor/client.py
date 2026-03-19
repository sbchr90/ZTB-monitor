import requests
from typing import Any, Dict, Optional

from .config import Config


class ZTBApiError(Exception):
    def __init__(self, message: str, status_code: int = 0, error_code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class ZTBClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        # bearer_token is set after ensure_token() resolves it in main.py
        if config.bearer_token:
            self._set_bearer(config.bearer_token)

    def _set_bearer(self, token: str) -> None:
        """Update the authorization header on the shared session."""
        self.session.headers["authorization"] = f"Bearer {token}"

    def _handle_response(self, resp: requests.Response) -> Any:
        resp.raise_for_status()
        data = resp.json()
        # ZTB API wraps errors in the response body even on 200
        if isinstance(data, dict) and data.get("errorCode") and data.get("errorCode") != 0:
            raise ZTBApiError(
                data.get("message", "API error"),
                status_code=data.get("statusCode", resp.status_code),
                error_code=str(data.get("errorCode", "")),
            )
        return data

    def get(self, path: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.config.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.config.timeout)
        return self._handle_response(resp)

    def post(self, path: str, data: Optional[Dict] = None) -> Any:
        url = f"{self.config.base_url}{path}"
        resp = self.session.post(url, json=data, timeout=self.config.timeout)
        return self._handle_response(resp)
