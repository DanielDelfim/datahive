from __future__ import annotations
from typing import Optional
import pandas as pd
from datetime import datetime, date
from decimal import Decimal

NUMERIC_COLS = [
    "valor_tarifa","custo_por_categoria","custo_fixo","subtotal_sem_desconto",
    "desconto_comercial","desconto_por_campanha","quantidade_vendida",
    "preco_unitario","valor_transacao","valor_acrescimo_preco","preco_produto_com_acrescimo",
    "envio_por_conta_do_cliente"
]
BOOL_COLS = ["tarifa_estornada"]
DATE_COLS = ["data_tarifa","data_venda"]

def _to_bool(x):
    if pd.isna(x):
        return None
    s = str(x).strip().lower()
    if s in {"true","t","1","sim","yes"}:
        return True
    if s in {"false","f","0","não","nao","no"}:
        return False
    return None

def _to_float(x):
    if pd.isna(x):
        return None
    if isinstance(x, str):
        s_raw = x.strip()
        s = s_raw.lower()
        # tratar flags/booleanos comuns -> número (compatível com schema float)
        if s in {"true","t","sim","yes","y","1"}:
            return 1.0
        if s in {"false","f","nao","não","no","n","0"}:
            return 0.0
        # tratar números com formatação regional
        s_num = s_raw.replace(".", "").replace(",", ".")
        try:
            return float(s_num)
        except Exception:
            return None
        
    try:
        return float(x)
    except Exception:
        return None

def _to_date(x):
    if pd.isna(x):
        return None
    return pd.to_datetime(x, dayfirst=True, errors="coerce")

def enrich_and_clean(df: pd.DataFrame, competencia: Optional[str]) -> pd.DataFrame:
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = df[c].apply(_to_float)
    for c in BOOL_COLS:
        if c in df.columns:
            df[c] = df[c].apply(_to_bool)
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = df[c].apply(_to_date).dt.date

    comp = competencia
    if not comp and "data_tarifa" in df.columns and df["data_tarifa"].notna().any():
        dt = pd.to_datetime(df["data_tarifa"], errors="coerce")
        if dt.notna().any():
            comp = f"{int(dt.dt.year.mode().iloc[0]):04d}-{int(dt.dt.month.mode().iloc[0]):02d}"
    if not comp:
        comp = datetime.today().strftime("%Y-%m")

    df["competencia"] = comp
    return df
# ... resto do arquivo inalterado ...
# ... imports do arquivo ...

def _serialize_json_safe(v):
    """Converte valores não-serializáveis (numpy/pandas/datas/Decimal) para formatos JSON-safe."""
    # Imports locais para checagem de tipos sem hard fail
    try:
        import numpy as np
        import pandas as pd
    except Exception:
        np = None
        pd = None

    # None permanece None
    if v is None:
        return None

    # Datas/timestamps → ISO
    if isinstance(v, (date, datetime)):
        return v.isoformat()

    if pd is not None and isinstance(v, getattr(pd, "Timestamp", ())):
        # Normaliza pandas.Timestamp
        try:
            # se tiver parte de data apenas, mantém como data
            return v.to_pydatetime().isoformat()
        except Exception:
            try:
                return v.isoformat()
            except Exception:
                return None

    # numpy.datetime64 → ISO (via pandas)
    if np is not None and isinstance(v, getattr(np, "datetime64", ())):
        if pd is not None:
            ts = pd.to_datetime(v, errors="coerce")
            return None if pd.isna(ts) else ts.to_pydatetime().isoformat()

    # NaN/NaT: garantir None
    if pd is not None and getattr(pd, "isna", None) is not None:
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass

    # Decimal → float (ou str, se preferir exatidão textual)
    if isinstance(v, Decimal):
        try:
            return float(v)
        except Exception:
            return str(v)

    # numpy.generic (int64, float64, bool_) → python nativo
    if np is not None and isinstance(v, getattr(np, "generic", ())):
        try:
            return _serialize_json_safe(v.item())
        except Exception:
            # fallback: str para não quebrar
            return str(v)

    # Tipos básicos já são JSON-safe (str, int, float, bool, dict, list)
    return v

def to_json_records(df: pd.DataFrame) -> list[dict]:
    # Troca NaN/NaT por None
    recs = df.where(pd.notnull(df), None).to_dict(orient="records")
    # Serialização final
    for r in recs:
        for k, v in list(r.items()):
            r[k] = _serialize_json_safe(v)
    return recs
