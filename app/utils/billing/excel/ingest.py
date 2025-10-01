# app/utils/billing/excel/ingest.py
from __future__ import annotations

import io
import re
import zipfile
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

import pandas as pd

# Buckets (classificação de conceitos)
from .conceitos import (
    bucket_conceito_mp,
    bucket_conceito_ml,
    bucket_conceito_full,
    bucket_conceito_pagamento_detalhe,
)

import warnings
warnings.filterwarnings("ignore", message="Workbook contains no default style", category=UserWarning)


# ============================================================
# 1) Utilitários de normalização de texto, cabeçalho e valores
# ============================================================

def _strip_accents(s: str) -> str:
    if s is None:
        return ""
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(ch))

def _norm_text(s: str) -> str:
    """lower, strip, sem acentos, colapsa espaços e remove pontuação à direita."""
    t = _strip_accents(str(s)).lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = t.rstrip(":;.,")
    return t

def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    new_cols = [_norm_text(c) for c in df.columns]
    out = df.copy()
    out.columns = new_cols
    return out

# padrões numéricos
_DEC_PT = re.compile(r"^\d{1,3}(\.\d{3})*,\d{1,2}$")   # 1.234,56
_DEC_COMMA = re.compile(r"^\d+,\d{1,2}$")              # 12,34
_DEC_DOT = re.compile(r"^\d+\.\d{1,2}$")               # 12.34
_INT = re.compile(r"^\d+$")

def _coerce_amount(series: pd.Series) -> pd.Series:
    """Converte strings monetárias pt-BR/en-US para float. Parênteses = negativo."""
    def conv(x):
        if isinstance(x, (int, float, Decimal)):
            return float(x)
        if pd.isna(x):
            return None

        s = str(x).strip()
        neg = False
        if s.startswith("(") and s.endswith(")"):
            neg = True
            s = s[1:-1]

        # remove símbolo e NBSP; preserva pontos internos
        s = s.replace("R$", "").replace("\u00A0", " ").strip()
        s_no_sp = s.replace(" ", "")

        if _DEC_PT.match(s_no_sp):          # 1.234,56
            s_norm = s_no_sp.replace(".", "").replace(",", ".")
        elif _DEC_COMMA.match(s_no_sp):     # 12,34
            s_norm = s_no_sp.replace(",", ".")
        elif _DEC_DOT.match(s_no_sp):       # 12.34
            s_norm = s_no_sp
        elif _INT.match(s_no_sp):           # 1234
            s_norm = s_no_sp
        else:
            # fallback: troca vírgula por ponto e mantém pontos decimais legítimos
            s_norm = s_no_sp.replace(",", ".")

        try:
            v = float(s_norm)
            return -v if neg else v
        except Exception:
            return None
    return series.apply(conv)

def _parse_date(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", dayfirst=True)
    except Exception:
        return pd.to_datetime(series, errors="coerce")

# =================================================
# 2) Leitura de fontes: .xlsx e .zip com .xlsx dentro
# =================================================

def _iter_excel_sources(dir_excel: Path) -> Iterable[Tuple[str, bytes]]:
    """Itera sobre .xlsx e .zip contendo .xlsx, retornando (nome, bytes)."""
    if not dir_excel.exists():
        return
    # XLSX diretos
    for p in sorted(dir_excel.glob("*.xlsx")):
        yield (p.name, p.read_bytes())
    # ZIPs com XLSX
    for z in sorted(dir_excel.glob("*.zip")):
        with zipfile.ZipFile(z, "r") as zf:
            for name in zf.namelist():
                if name.lower().endswith(".xlsx"):
                    yield (Path(name).name, zf.read(name))

# ==========================================================
# 3) Header dinâmico por aba (detecta linha com tokens-chave)
# ==========================================================

_BASE_TOKENS = [
    "n° nf-e", "no nf-e", "nº nf-e",
    "numero da tarifa", "número da tarifa", "no da tarifa", "nº da tarifa",
    "data da tarifa", "data do movimento", "data do pagamento",
    "detalhe", "valor da tarifa", "valor do custo",
    "numero do pagamento", "número do pagamento",
    "parte do pagamento aplicado a tarifas",
]

def _looks_like_header_row(row_vals: List[str], tokens: List[str]) -> bool:
    row_norm = [_norm_text(str(v)) for v in row_vals]
    joined = " | ".join(row_norm)
    hits = sum(1 for t in tokens if t in joined)
    return hits >= 2  # pelo menos 2 tokens na linha

def _detect_header_row(xls: pd.ExcelFile, sheet: str, tokens: List[str], probe_rows: int = 50) -> Optional[int]:
    tmp = xls.parse(sheet_name=sheet, header=None, nrows=probe_rows)
    for i, row in tmp.iterrows():
        vals = [row.get(j, "") for j in range(len(row))]
        if _looks_like_header_row(vals, tokens):
            return int(i)
    return None

def _read_sheet_dynamic_header(xls: pd.ExcelFile, sheet: str, tokens: List[str]) -> pd.DataFrame:
    row = _detect_header_row(xls, sheet, tokens)
    if row is None:
        df = xls.parse(sheet_name=sheet)  # fallback
    else:
        df = xls.parse(sheet_name=sheet, header=row)
    df["__sheet__"] = sheet
    return df

def _read_workbook_filtered_sheets(file_bytes: bytes, allowed_sheets: set[str], tokens: List[str]) -> pd.DataFrame:
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    frames = []
    for sh in xls.sheet_names:
        sh_norm = _norm_text(sh)
        if sh_norm not in allowed_sheets:
            continue
        try:
            df = _read_sheet_dynamic_header(xls, sh, tokens)
            frames.append(df)
        except Exception:
            continue
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return out

# ==========================================
# 4) Abas “oficiais” por relatório (normalizadas)
# ==========================================

SHEETS_MP = {"report"}
SHEETS_ML = {"report"}
SHEETS_PAY = {"pagamentos e estornos", "detalhe do pagamentos deste mes", "detalhe do pagamentos deste mês"}
SHEETS_FULL = {
    "tarifa de armazenamento",
    "custo por servico de coleta", "custo por serviço de coleta",
    "custo de armazenamento prolonga",
}

# =====================================
# 5) Mapeamentos explícitos de colunas
# =====================================

MP_MAP = {
    "detalhe": ["detalhe"],
    "valor_tarifa": ["valor da tarifa"],
    "numero_tarifa": ["numero da tarifa", "nº da tarifa", "no da tarifa"],
    "data": ["data do movimento", "data da tarifa"],
    "estornada": ["tarifa estornada"],
}

ML_MAP = {
    "detalhe": ["detalhe"],
    # valor_tarifa: no ML usaremos apenas "valor da tarifa" (nunca "valor")
    "valor_tarifa": ["valor da tarifa"],
    "numero_tarifa": ["numero da tarifa", "nº da tarifa", "no da tarifa"],
    "data": ["data da tarifa", "data"],
    "cancelada": ["tarifa cancelada"],
    "desconto_comercial": ["desconto comercial"],
}

FULL_MAP = {
    "detalhe": ["detalhe"],
    "valor": ["valor da tarifa", "valor do custo"],
    "numero": ["numero da tarifa", "nº da tarifa", "no da tarifa", "numero do custo", "nº do custo", "no do custo"],
    "data": ["data da tarifa", "data do custo", "data"],
}

PAY_MAP = {
    "valor_mes": ["valor aplicado a este mes", "valor aplicado a este mês"],
    "valor_total": ["valor total"],
    "data": ["data do pagamento/emissao de estorno", "data do pagamento", "emissao de estorno"],
    "pagamento_id": ["numero do pagamento", "número do pagamento", "pagamento"],
    "valor_aplicado_tarifas": ["parte do pagamento aplicado a tarifas"],  # aba de detalhe do mês
}

def _find_by_keys(df: pd.DataFrame, keys: List[str]) -> Optional[str]:
    cols = list(df.columns)
    for k in keys:
        k0 = _norm_text(k)
        for c in cols:
            if k0 == c:
                return c
    # fallback contain
    for k in keys:
        k0 = _norm_text(k)
        for c in cols:
            if k0 in c:
                return c
    return None

def _dedup_by_id(df: pd.DataFrame) -> pd.DataFrame:
    if "__id__" in df.columns:
        return df.drop_duplicates(subset=["__id__"], keep="last")
    return df

# =========================================
# 6) Carregadores por relatório (retornam DF)
# =========================================

def carregar_faturamento_mp(dir_excel: Path) -> pd.DataFrame:
    frames = []
    for name, data in _iter_excel_sources(dir_excel):
        if not re.search(r"faturamento[_\s-]*mercado\s*pago", name.lower()):
            continue
        raw = _read_workbook_filtered_sheets(data, SHEETS_MP, _BASE_TOKENS)
        if raw.empty:
            continue
        df = _normalize_headers(raw)

        conc = _find_by_keys(df, MP_MAP["detalhe"])
        val  = _find_by_keys(df, MP_MAP["valor_tarifa"])
        tid  = _find_by_keys(df, MP_MAP["numero_tarifa"])
        dtc  = _find_by_keys(df, MP_MAP["data"])
        est  = _find_by_keys(df, MP_MAP.get("estornada", []))

        out = pd.DataFrame()
        out["__conceito__"] = df[conc].astype(str) if conc else ""
        out["__valor__"] = _coerce_amount(df[val]) if val else None
        out["__data__"] = _parse_date(df[dtc]) if dtc else pd.NaT
        out["__id__"] = df[tid].astype(str) if tid else df.index.astype(str)
        out["__tarifa_id__"] = out["__id__"]
        out["__src__"] = "Faturamento Mercado Pago"

        # estornada ⇒ negativo
        if est and est in df.columns:
            mask_est = df[est].astype(str).str.strip().str.lower().isin(["sim", "true", "1"])
            out.loc[mask_est, "__valor__"] = out.loc[mask_est, "__valor__"].fillna(0).astype(float) * -1.0

        out["__categoria__"] = out["__conceito__"].apply(bucket_conceito_mp)
        out = out.dropna(subset=["__valor__"])
        frames.append(out[["__id__","__data__","__conceito__","__valor__","__categoria__","__src__"]])

    return _dedup_by_id(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame(columns=["__id__","__data__","__conceito__","__valor__","__categoria__","__src__"])


def carregar_faturamento_ml(dir_excel: Path) -> pd.DataFrame:
    frames = []
    for name, data in _iter_excel_sources(dir_excel):
        if not re.search(r"faturamento[_\s-]*mercado\s*livre", name.lower()):
            continue
        raw = _read_workbook_filtered_sheets(data, SHEETS_ML, _BASE_TOKENS)
        if raw.empty:
            continue
        df = _normalize_headers(raw)

        conc = _find_by_keys(df, ML_MAP["detalhe"])
        # *** valor: usar apenas 'valor da tarifa' (nunca 'valor') ***
        val  = _find_by_keys(df, ML_MAP["valor_tarifa"])
        tid  = _find_by_keys(df, ML_MAP["numero_tarifa"])
        dtc  = _find_by_keys(df, ML_MAP["data"])
        canc = _find_by_keys(df, ML_MAP.get("cancelada", []))
        desc = _find_by_keys(df, ML_MAP.get("desconto_comercial", []))

        out = pd.DataFrame()
        out["__conceito__"] = df[conc].astype(str) if conc else ""

        # --- anti-ID: impedir que strings de ID longas virem dinheiro ---
        def _anti_id_series(raw_series: pd.Series, parsed_series: pd.Series) -> List[Optional[float]]:
            out_vals: List[Optional[float]] = []
            for rv, pv in zip(raw_series.tolist(), parsed_series.tolist()):
                s = str(rv).strip()
                if s.isdigit() and len(s) >= 8:   # id longo (ex.: 00000000000002417899)
                    out_vals.append(None)
                else:
                    out_vals.append(pv)
            return out_vals

        if val:
            parsed = _coerce_amount(df[val])
            out["__valor__"] = _anti_id_series(df[val], parsed)
        else:
            out["__valor__"] = None

        out["__data__"] = _parse_date(df[dtc]) if dtc else pd.NaT
        # id e tarifa_id
        out["__id__"] = df[tid].astype(str) if tid else df.index.astype(str)
        out["__tarifa_id__"] = out["__id__"]  # usa Número da tarifa como chave global
        out["__src__"] = "Faturamento Mercado Livre"

        # cancelada ⇒ negativo
        if canc and canc in df.columns:
            mask_canc = df[canc].astype(str).str.strip().str.lower().isin(["sim","true","1"])
            out.loc[mask_canc, "__valor__"] = out.loc[mask_canc, "__valor__"].fillna(0).astype(float) * -1.0

        # bucketização fina (conceitos ML)
        out["__categoria__"] = out["__conceito__"].apply(bucket_conceito_ml)
        out = out.dropna(subset=["__valor__"])
        frames.append(out[["__id__","__data__","__conceito__","__valor__","__categoria__","__src__"]])

        # --- Aplicamos descontos sobre essas tarifas (linhas negativas) ---
        if desc and desc in df.columns:
            df_desc = pd.DataFrame()
            df_desc["__id__"] = (df[tid].astype(str) if tid else df.index.astype(str)).astype(str) + ":DESC"
            df_desc["__data__"] = _parse_date(df[dtc]) if dtc else pd.NaT
            df_desc["__conceito__"] = "Desconto comercial (aplicado em tarifas)"
            df_desc["__valor__"] = _coerce_amount(df[desc]).fillna(0.0) * -1.0
            df_desc["__categoria__"] = "Aplicamos descontos sobre essas tarifas"
            df_desc["__src__"] = "Faturamento Mercado Livre"
            df_desc = df_desc[df_desc["__valor__"] != 0]
            if not df_desc.empty:
                frames.append(df_desc[["__id__","__data__","__conceito__","__valor__","__categoria__","__src__"]])

    return _dedup_by_id(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame(columns=["__id__","__data__","__conceito__","__valor__","__categoria__","__src__"])


def carregar_tarifas_full(dir_excel: Path) -> pd.DataFrame:
    frames = []
    for name, data in _iter_excel_sources(dir_excel):
        if "tarifas_full" not in name.lower():
            continue
        raw = _read_workbook_filtered_sheets(data, SHEETS_FULL, _BASE_TOKENS)
        if raw.empty:
            continue
        df = _normalize_headers(raw)

        conc = _find_by_keys(df, FULL_MAP["detalhe"])
        valc = _find_by_keys(df, FULL_MAP["valor"])     # "valor da tarifa" ou "valor do custo"
        tid  = _find_by_keys(df, FULL_MAP["numero"])
        dtc  = _find_by_keys(df, FULL_MAP["data"])

        out = pd.DataFrame()
        out["__conceito__"] = df[conc].astype(str) if conc else ""
        out["__valor__"] = _coerce_amount(df[valc]) if valc else None
        out["__data__"] = _parse_date(df[dtc]) if dtc else pd.NaT
        out["__id__"] = df[tid].astype(str) if tid else df.index.astype(str)
        out["__tarifa_id__"] = out["__id__"]
        out["__src__"] = "Tarifas Full"
        out["__categoria__"] = out["__conceito__"].apply(bucket_conceito_full)
        out = out.dropna(subset=["__valor__"])
        frames.append(out[["__id__","__data__","__conceito__","__valor__","__categoria__","__src__"]])

    return _dedup_by_id(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame(columns=["__id__","__data__","__conceito__","__valor__","__categoria__","__src__"])

# (moved to top with other imports)

def carregar_pagamento_faturas(dir_excel: Path) -> pd.DataFrame:
    frames = []
    for name, data in _iter_excel_sources(dir_excel):
        if "pagamento_faturas" not in name.lower():
            continue
        raw = _read_workbook_filtered_sheets(data, SHEETS_PAY, _BASE_TOKENS)
        if raw.empty:
            continue
        df = _normalize_headers(raw)

        # Detalhe do mês — parte aplicada a tarifas (mais preciso)
        v_apl = _find_by_keys(df, PAY_MAP["valor_aplicado_tarifas"])
        pid_d = _find_by_keys(df, PAY_MAP["pagamento_id"]) or "__rowid__"
        det_c = _find_by_keys(df, ["detalhe"])   # <<< pega a coluna "Detalhe" da aba

        nid = _find_by_keys(df, ["numero da tarifa","nº da tarifa","no da tarifa"])

        if v_apl and v_apl in df.columns:
            det = df.dropna(subset=[v_apl]).copy()
            if not det.empty:
                # Para reconciliação (valor aplicado a este mês)
                det["__valor_mes__"] = _coerce_amount(det[v_apl])
                det["__id__"] = det[pid_d].astype(str) if pid_d in det.columns else det.index.astype(str)
                det["__data__"] = pd.NaT
                # Para cobrança (entra no somatório por categoria)
            if det_c and det_c in det.columns:
                    det["__conceito__"] = det[det_c].astype(str)
                    det["__valor__"] = det["__valor_mes__"].astype(float).abs()
                    det["__categoria__"] = det["__conceito__"].apply(bucket_conceito_pagamento_detalhe)
                    # <<< chave global para dedup entre fontes
                    if nid and nid in det.columns:
                        det["__tarifa_id__"] = det[nid].astype(str)
                    else:
                        det["__tarifa_id__"] = det["__id__"].astype(str)

        # Aba de pagamentos agregados (valor aplicado a este mês / valor total)
        v_mes = _find_by_keys(df, PAY_MAP["valor_mes"])
        v_tot = _find_by_keys(df, PAY_MAP["valor_total"])
        dtc   = _find_by_keys(df, PAY_MAP["data"])
        pid   = _find_by_keys(df, PAY_MAP["pagamento_id"]) or "__rowid__"

        agg = pd.DataFrame()
        if v_mes and v_mes in df.columns:
            agg["__valor_mes__"] = _coerce_amount(df[v_mes])
        elif v_tot and v_tot in df.columns:
            agg["__valor_mes__"] = _coerce_amount(df[v_tot])
        if not agg.empty:
            agg["__data__"] = _parse_date(df[dtc]) if dtc else pd.NaT
            agg["__id__"] = df[pid].astype(str) if pid in df.columns else df.index.astype(str)
            frames.append(agg[["__id__","__data__","__valor_mes__"]])

    if not frames:
        return pd.DataFrame(columns=["__id__","__data__","__valor_mes__","__conceito__","__valor__","__categoria__","__src__"])
    out = pd.concat(frames, ignore_index=True)
    out["__src__"] = "Pagamento de Faturas"
    return out
