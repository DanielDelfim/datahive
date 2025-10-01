from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict, Any
import requests

from typing import List

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

class MeliClient:
    def __init__(self, access_token: str, refresh_token: Optional[str] = None,
                 client_id: Optional[str] = None, client_secret: Optional[str] = None,
                 api_base: str = "https://api.mercadolibre.com"):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_base = api_base.rstrip("/")

    @classmethod
    def from_tokens_json(cls, path: Path, client_id: Optional[str], client_secret: Optional[str],
                         api_base: str = "https://api.mercadolibre.com") -> "MeliClient":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            client_id=client_id,
            client_secret=client_secret,
            api_base=api_base,
        )

    def _auth(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def refresh(self) -> bool:
        if not (self.refresh_token and self.client_id and self.client_secret):
            return False
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        r = requests.post(TOKEN_URL, data=payload, timeout=20)
        if r.status_code != 200:
            return False
        data = r.json()
        self.access_token = data.get("access_token", self.access_token)
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        return True

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> requests.Response:
        url = f"{self.api_base}/{path.lstrip('/')}"
        r = requests.get(url, headers=self._auth(), params=params or {}, timeout=30)
        if r.status_code == 401 and self.refresh():
            r = requests.get(url, headers=self._auth(), params=params or {}, timeout=30)
        return r

    # util opcional para debug: quem é o user do token?
    def get_me(self) -> Dict[str, Any]:
        r = self._get("/users/me")
        r.raise_for_status()
        return r.json()

    def get_last_order(self, seller_id: str) -> Dict[str, Any]:
        params = {"seller": seller_id, "sort": "date_desc", "limit": 1}
        r = self._get("/orders/search", params=params)
        r.raise_for_status()
        return r.json()

    def search_orders_range(
        self,
        seller_id: str,
        date_from_iso: str,
        date_to_iso: str,
        limit: int = 50,
        max_pages: int = 1000,
    ) -> Dict[str, Any]:
        """
        Busca pedidos na faixa [date_from_iso, date_to_iso], paginando por offset/limit.
        date_* devem estar em ISO8601 com offset (ex.: '2025-07-01T00:00:00-03:00').
        Retorna {"results": [...], "paging": {"total": N}}.
        """
        path = "/orders/search"
        params = {
            "seller": seller_id,
            "order.date_created.from": date_from_iso,
            "order.date_created.to": date_to_iso,
            "sort": "date_asc",  # asc para acumular sem duplicar
            "limit": limit,
            "offset": 0,
        }

        all_results: List[Dict[str, Any]] = []
        page = 0
        while True:
            r = self._get(path, params)
            r.raise_for_status()
            data = r.json()
            results = data.get("results") or []
            all_results.extend(results)

            paging = data.get("paging") or {}
            total = int(paging.get("total") or 0)
            got = len(results)
            if got == 0:
                break

            params["offset"] = int(params["offset"]) + limit
            page += 1
            if page >= max_pages:
                break
            if total and len(all_results) >= total:
                break

        return {"results": all_results, "paging": {"total": len(all_results)}}
    
    # dentro de MeliClient
    def get_item(self, mlb: str) -> dict:
        r = self._get(f"/items/{mlb}")
        r.raise_for_status()
        return r.json()

    def get_item_description(self, mlb: str) -> dict:
        r = self._get(f"/items/{mlb}/description")
        r.raise_for_status()
        return r.json()
    
    def search_seller_items(self, seller_id: str, limit: int = 100, max_pages: int = 1000) -> List[str]:
        """
        Retorna todos os MLBs do seller usando /users/{seller_id}/items/search (scan).
        """
        path = f"/users/{seller_id}/items/search"
        params = {"search_type": "scan", "limit": limit, "offset": 0}
        ids: List[str] = []
        page = 0
        while True:
            r = self._get(path, params)
            r.raise_for_status()
            data = r.json() or {}
            results = data.get("results") or []
            if not results:
                break
            ids.extend(results)
            params["offset"] = int(params["offset"]) + limit
            page += 1
            if page >= max_pages:
                break
            paging = data.get("paging") or {}
            total = int(paging.get("total") or 0)
            if total and len(ids) >= total:
                break
        return ids

    def get_items_bulk(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Busca detalhes dos itens em lotes via /items?ids=...
        """
        out: List[Dict[str, Any]] = []
        step = 20
        for i in range(0, len(ids), step):
            chunk = ids[i:i+step]
            if not chunk:
                continue
            r = self._get("/items", params={"ids": ",".join(chunk)})
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                for it in data:
                    body = it.get("body") if isinstance(it, dict) else None
                    if body:
                        out.append(body)
            elif isinstance(data, dict) and data.get("body"):
                out.append(data["body"])
        return out