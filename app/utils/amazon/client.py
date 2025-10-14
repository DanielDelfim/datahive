#C:\Apps\Datahive\app\utils\amazon\client.py
import time
import json
import logging
import requests
from typing import Any, Dict, Optional

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"  # LWA
DEFAULT_TIMEOUT = 30

class AmazonSpApiClient:
    """
    Cliente mínimo SP-API (sem IAM/SigV4). Usa LWA access token no header:
    x-amz-access-token: <ACCESS_TOKEN>
    """
    def __init__(self, base_url: str, client_id: str, client_secret: str,
                 refresh_token: str, user_agent: str):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.user_agent = user_agent
        self._access_token: Optional[str] = None
        self._access_token_exp: float = 0.0

    def _ensure_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._access_token_exp - 60:
            return self._access_token

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        r = requests.post(LWA_TOKEN_URL, data=data, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        payload = r.json()
        self._access_token = payload["access_token"]
        self._access_token_exp = now + int(payload.get("expires_in", 3600))
        return self._access_token

    def _headers(self, token: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h = {
            "x-amz-access-token": token,
            "user-agent": self.user_agent,
            "accept": "application/json",
        }
        if extra:
            h.update(extra)
        return h

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        token = self._ensure_token()
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            r = requests.get(url, headers=self._headers(token), params=params, timeout=DEFAULT_TIMEOUT)
        except Exception as e:
            logging.exception("SP-API GET %s exception: %s", url, e)
            raise
        if r.status_code >= 400:
            # log completo e claro
            body_preview = r.text[:1000].replace("\n", " ")
            logging.error("SP-API GET failed: %s | %s | %s", url, r.status_code, body_preview)
        r.raise_for_status()
        return r.json()

    # Opcional: obter RDT para endpoints com PII (ex.: endereço comprador)
    def get_rdt(self, restricted_resources: list[dict]) -> str:
        """
        restricted_resources: [{"method":"GET","path":"/orders/v0/orders/{orderId}/address","dataElements":["buyerInfo"]}]
        """
        token = self._ensure_token()
        body = {"restrictedResources": restricted_resources}
        url = f"{self.base_url}/tokens/2021-03-01/restrictedDataToken"
        r = requests.post(url, headers=self._headers(token, {"content-type": "application/json"}),
                          data=json.dumps(body), timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()["restrictedDataToken"]
    
    # dentro da classe AmazonSpApiClient
    def post(self, path: str, json: dict) -> dict:
        """
        POST para SP-API com o mesmo padrão do get():
        - obtém LWA access token via _ensure_token()
        - monta headers (inclui content-type json)
        - executa POST e faz o mesmo tratamento de erro/log do get()
        """
        import requests
        import logging

        token = self._ensure_token()
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            r = requests.post(
                url,
                headers=self._headers(token, {"content-type": "application/json"}),
                json=json,
                timeout=DEFAULT_TIMEOUT,
            )
        except Exception as e:
            logging.exception("SP-API POST %s exception: %s", url, e)
            raise

        if r.status_code >= 400:
            body_preview = r.text[:1000].replace("\n", " ")
            logging.error("SP-API POST failed: %s | %s | %s", url, r.status_code, body_preview)
        r.raise_for_status()
        return r.json() if r.content else {}



