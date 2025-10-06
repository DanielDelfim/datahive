# C:\Apps\Datahive\app\dashboard\precificacao\context.py
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd

from app.utils.precificacao.config import (
    get_anuncios_path,
    get_precificacao_dataset_path,
)
from app.utils.precificacao.service import carregar_regras_ml

_PRECO_COMPRA_PATH = Path("data/precificacao/common/pp/preco_compra_produtos.json")

def _read_json(path: Path):
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _as_df(obj) -> pd.DataFrame:
    """Converte json-like em DataFrame sem usar truthiness de DF."""
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, dict) and isinstance(obj.get("itens"), list):
        return pd.DataFrame(obj["itens"])
    if isinstance(obj, list):
        return pd.DataFrame(obj)
    # se vier dict sem "itens" (raro), tenta colunas
    if isinstance(obj, dict):
        return pd.DataFrame([obj])
    return pd.DataFrame()

def _load_dataset(regiao: str):
    # sempre usa o dataset principal (o metrics pode ser apenas um resumo)
    return _read_json(get_precificacao_dataset_path(regiao))

def load_context(*, regiao: str = "sp") -> dict:
    anuncios_raw = _read_json(get_anuncios_path(regiao)) or []
    produtos_raw = _read_json(_PRECO_COMPRA_PATH) or []

    env = _load_dataset(regiao)
    other = "mg" if regiao.lower() == "sp" else "sp"
    env_other = _load_dataset(other)

    anuncios_df = pd.DataFrame(anuncios_raw)
    dataset_df = _as_df(env)
    df_other = _as_df(env_other)

    if not dataset_df.empty and "regiao" not in dataset_df.columns:
        dataset_df = dataset_df.copy()
        dataset_df["regiao"] = regiao.lower()
    if not df_other.empty and "regiao" not in df_other.columns:
        df_other = df_other.copy()
        df_other["regiao"] = other

    if dataset_df.empty and df_other.empty:
        dataset_df_all = pd.DataFrame()
    elif dataset_df.empty:
        dataset_df_all = df_other.copy()
    elif df_other.empty:
        dataset_df_all = dataset_df.copy()
    else:
        dataset_df_all = pd.concat([dataset_df, df_other], ignore_index=True)

    regras = carregar_regras_ml() or {}
    produtos_df = pd.DataFrame(produtos_raw)

    return {
        "regiao": regiao,
        "anuncios_df": anuncios_df,
        "dataset_df": dataset_df,
        "dataset_df_all": dataset_df_all,
        "regras": regras,
        "produtos_df": produtos_df,
    }
