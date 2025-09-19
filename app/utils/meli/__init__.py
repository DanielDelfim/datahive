# app/utils/meli/api.py
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from app.config.paths import ML_API_BASE  # base: https://api.mercadolibre.com
from app.utils.core.io import ler_json, salvar_json


@dataclass
class _Tokens:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: Optional[int] = None  # epoch seconds


class MeliAuthError(RuntimeError):
    pass


class MeliClient:
    """
    Cliente simples para a API do Mercado Livre com:
      - construção via from_tokens_json(...)
      - GET com retry em 401 usando refresh token
      - refresh() pelo endpoint /oauth/token
      - get_last_order(seller_id)

    Requisitos do JSON de tokens:
    {
      "access_token": "...",
      "refresh_token": "...",
      "token_type": "bearer",
      "expires_at": 1736559999  # opcional (epoch). Se ausente, será recalculado no refresh.
    }
    """

    def __init__(
        self,
        *,
        base_url: str,
        client_id: str,
        client_secret: str,
        tokens_path: Path,
        tokens: _Tokens,
        timeout_sec: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.tokens_path = Path(tokens_path)
        self.tokens = tokens
        self.timeout_sec = timeout_sec
        self.http = session or requests.Session()

    # ---------- factories ----------

    @classmethod
    def from_tokens_json(
        cls,
        tokens_path: Path | str,
        *,
        client_id: str,
        client_secret: str,
        base_url: str = ML_API_BASE,
        timeout_sec: int = 30,
    ) -> "MeliClient":
        """Carrega tokens de um arquivo JSON e devolve o cliente configurado."""
        p = Path(tokens_path)
        data = ler_json(p)
        try:
            tokens = _Tokens(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                token_type=data.get("token_type", "bearer"),
                expires_at=data.get("expires_at"),
            )
        except KeyError as e:
            raise MeliAuthError(f"Campo obrigatório ausente no tokens JSON: {e}") from e

        return cls(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            tokens_path=p,
            tokens=tokens,
            timeout_sec=timeout_sec,
        )

    # ---------- low-level helpers ----------

    def _auth_header(self) -> Dict[str, str]:
        return {"Authorization": f"{self.tokens.token_type.capitalize()} {self.tokens.access_token}"}

    def _save_tokens(self, payload: Dict[str, Any]) -> None:
        # Concilia o formato de resposta do ML (expires_in) com nosso arquivo (expires_at)
        expires_at = payload.get("expires_at")
        if not expires_at and (ei := payload.get("expires_in")):
            expires_at = int(time.time()) + int(ei)
        merged = {
            "access_token": payload.get("access_token", self.tokens.access_token),
            "refresh_token": payload.get("refresh_token", self.tokens.refresh_token),
            "token_type": payload.get("token_type", "bearer"),
            "expires_at": expires_at or self.tokens.expires_at,
        }
        salvar_json(self.tokens_path, merged)
        self.tokens = _Tokens(
            access_token=merged["access_token"],
            refresh_token=merged["refresh_token"],
            token_type=merged.get("token_type", "bearer"),
            expires_at=merged.get("expires_at"),
        )

    # ---------- HTTP com retry em 401 ----------

    def _get(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Faz GET com Authorization. Em 401, tenta um refresh() e repete 1 vez.
        Lança requests.HTTPError em status != 2xx após tentativa de refresh.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        r = self.http.get(url, params=params, headers=self._auth_header(), timeout=self.timeout_sec)

        if r.status_code == 401:
            # tenta refresh e repete uma vez
            self.refresh()
            r = self.http.get(url, params=params, headers=self._auth_header(), timeout=self.timeout_sec)

        r.raise_for_status()
        return r.json()

    # ---------- OAuth ----------

    def refresh(self) -> None:
        """
        Atualiza o access_token via /oauth/token (grant_type=refresh_token).
        Salva o novo token no tokens_path.
        """
        url = f"{self.base_url}/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.tokens.refresh_token,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        r = self.http.post(url, data=data, headers=headers, timeout=self.timeout_sec)

        if r.status_code != 200:
            # tenta extrair mensagem útil
            try:
                err = r.json()
            except Exception:
                err = r.text
            raise MeliAuthError(f"Falha no refresh token ({r.status_code}): {err}")

        payload = r.json()
        self._save_tokens(payload)

    # ---------- Endpoints de domínio ----------

    def get_last_order(self, seller_id: str) -> Dict[str, Any]:
        """
        Retorna a última venda do seller (ordenado desc pela data).
        Usa /orders/search com limit=1.
        """
        params = {"seller": seller_id, "sort": "date_desc", "limit": 1}
        return self._get("/orders/search", params=params)
