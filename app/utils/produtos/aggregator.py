# C:\Apps\Datahive\app\utils\produtos\aggregator.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Tuple

from app.utils.produtos.mappers.dimensions import attach_dims_blocks
import pandas as pd
from app.utils.produtos.metrics import normalizar_multiplo

from app.utils.core.produtos.units import (
    to_bool, to_int, to_float, calc_volume_m3,
    sanitize_gtin, sanitize_cnpj
)
from app.utils.core.produtos.validate import validate_required, coerce_in_set
from app.utils.produtos.config import (
    COLUMNS_EXCEL, UNIDADES_MEDIDA, ORIGEM_MERCADORIA,
    REGIME_FISCAL, REQUIRED_MIN
)

def _safe_get(d: Dict[str, Any] | None, *path):
    x = d or {}
    for p in path:
        x = x.get(p) if isinstance(x, dict) else None
    return x

def normalizar_para_envio(prod: Dict[str, Any]) -> Dict[str, Any]:
    """
    Padroniza um produto para a aba **Envios** SEM fallback:
      - CAIXA: caixa_cm.{largura, profundidade, altura} (cm)
      - CAIXA: pesos_caixa_g.bruto (g)  [convertido de kg -> g]
      - multiplo_compra normalizado (>=1) ou None
      - ean/gtin/titulo/preco_compra canônicos
    Também retorna os campos do PRODUTO (dimensoes_cm/pesos_g) apenas para referência.
   """

    dims = attach_dims_blocks(prod)

    return {
        "titulo": prod.get("titulo") or prod.get("title") or "",
        "gtin": prod.get("gtin") or prod.get("ean") or "",
        "ean": prod.get("ean") or prod.get("gtin") or "",
        "multiplo_compra": normalizar_multiplo(
            prod.get("multiplo_compra") or prod.get("multiplo_de_compra") or prod.get("multiplo")
        ),
        "preco_compra": prod.get("preco_compra") if isinstance(prod.get("preco_compra"), (int, float)) else prod.get("custo"),
        # bloco CAIXA (sem fallback):
        "caixa_cm": {
            "largura": dims["caixa_largura"],
            "profundidade": dims["caixa_profundidade"],
            "altura": dims["caixa_altura"],
        },
        "pesos_caixa_g": {
            # mapper retorna kg; se quiser em g, multiplique por 1000 caso não seja None
            "bruto": None if dims["peso_caixa"] is None else round(dims["peso_caixa"] * 1000, 3),
        },
        # (opcional) manter também os campos de PRODUTO, se forem úteis em outras abas:
        "dimensoes_cm": {
            "largura": dims["produto_largura"],
            "profundidade": dims["produto_profundidade"],
            "altura": dims["produto_altura"],
        },
        "pesos_g": {
            "bruto": None if dims["produto_peso"] is None else round(dims["produto_peso"] * 1000, 3),
        },
    }

def _s(df_value) -> str | None:
    if df_value is None:
        return None
    try:
        if pd.isna(df_value):
            return None
    except Exception:
        pass
    s = str(df_value).strip()
    return s or None

def _normalize_row(row: dict) -> dict:
    # Identificadores
    sku = _s(row.get("sku")) or ""
    gtin = sanitize_gtin(row.get("gtin"))
    bling_id = _s(row.get("bling_id"))
    titulo = _s(row.get("titulo")) or ""

    # Flags e inteiros
    e_kit = to_bool(row.get("e_kit"))
    unidades_kit = to_int(row.get("Unidades_no_kit"))
    ativo = to_bool(row.get("ativo"))

    # Textos/domínios
    marca = _s(row.get("marca"))
    ncm = _s(row.get("ncm"))
    cest = _s(row.get("cest"))
    origem_mercadoria = coerce_in_set(_s(row.get("origem_mercadoria")) or "", ORIGEM_MERCADORIA)
    unidade_medida = coerce_in_set((_s(row.get("unidade_medida")) or "").upper(), UNIDADES_MEDIDA)

    # Pesos (g)
    peso_liq_g = to_float(row.get("peso_liq_g"))
    peso_bruto_g = to_float(row.get("peso_bruto_g"))

    # Dimensões (cm)
    altura_cm = to_float(row.get("altura_cm"))
    largura_cm = to_float(row.get("largura_cm"))
    profundidade_cm = to_float(row.get("profundidade_cm"))

    # Volume (m3) — recalcula quando possível
    vol_calc = calc_volume_m3(altura_cm, largura_cm, profundidade_cm)
    volume_m3 = vol_calc if vol_calc is not None else to_float(row.get("volume_m3"))

    # Compra / fornecedor
    preco_compra = to_float(row.get("preco_compra"))
    fornecedor_nome = _s(row.get("fornecedor_nome"))
    fornecedor_cnpj = sanitize_cnpj(row.get("fornecedor_cnpj"))
    fornecedor_codigo = _s(row.get("fornecedor_codigo"))
    lead_time_dias = to_int(row.get("lead_time_dias"))
    dum_14 = to_bool(row.get("dum_14"))
    multiplo_compra = to_int(row.get("multiplo_compra"))

    # Medidas e pesos da caixa
    peso_bruto_caixa = to_float(row.get("peso_bruto_caixa"))
    peso_liq_caixa = to_float(row.get("peso_liq_caixa"))
    largura_caixa = to_float(row.get("largura_caixa"))
    altura_caixa = to_float(row.get("altura_caixa"))
    profundidade_caixa = to_float(row.get("profundidade_caixa"))

    # Fiscais
    regime_fiscal = coerce_in_set(_s(row.get("regime_fiscal")) or "", REGIME_FISCAL)
    csosn_default = _s(row.get("csosn_default"))

    # Atributos
    atrib_conteudo_liquido = _s(row.get("atrib_conteudo_liquido"))
    atrib_tipo_embalagem = _s(row.get("atrib_tipo_embalagem"))
    atrib_validade_meses = to_int(row.get("atrib_validade_meses"))

    categoria_interna = _s(row.get("categoria_interna"))
    observacoes = _s(row.get("observacoes"))

    missing = validate_required(REQUIRED_MIN, {
        "sku": sku, "titulo": titulo, "preco_compra": preco_compra
    })
    if missing:
        raise ValueError(f"[SKU {sku or 'N/A'}] Campos obrigatórios ausentes: {missing}")

    return {
        "sku": sku,
        "gtin": gtin,
        "bling_id": bling_id,
        "titulo": titulo,
        "e_kit": e_kit,
        "unidades_no_kit": unidades_kit,
        "marca": marca,
        "ncm": ncm,
        "cest": cest,
        "origem_mercadoria": origem_mercadoria,
        "unidade_medida": unidade_medida,
        "pesos_g": {"liq": peso_liq_g, "bruto": peso_bruto_g},
        "dimensoes_cm": {"altura": altura_cm, "largura": largura_cm, "profundidade": profundidade_cm},
        "volume_m3": volume_m3,
        "preco_compra": preco_compra,
        "fornecedor": {
            "nome": fornecedor_nome,
            "cnpj": fornecedor_cnpj,
            "codigo": fornecedor_codigo
        },
        "lead_time_dias": lead_time_dias,
        "dum_14": dum_14,
        "multiplo_compra": multiplo_compra,
        "caixa_cm": {
            "altura": altura_caixa,
            "largura": largura_caixa,
            "profundidade": profundidade_caixa
        },
        "pesos_caixa_g": {
            "liq": peso_liq_caixa,
            "bruto": peso_bruto_caixa
        },
        "regime_fiscal": regime_fiscal,
        "csosn_default": csosn_default,
        "atributos": {
            "conteudo_liquido": atrib_conteudo_liquido,
            "tipo_embalagem": atrib_tipo_embalagem,
            "validade_meses": atrib_validade_meses
        },
        "ativo": ativo,
        "categoria_interna": categoria_interna,
        "observacoes": observacoes
    }


def carregar_excel_normalizado(excel_path: Path | str) -> Dict[str, Dict[str, Any]]:
    """
    Lê o Excel e devolve um dicionário { sku: registro_normalizado }, ignorando:
    - linhas sem SKU
    - linhas sem obrigatórios (ex.: preco_compra)
    """
    p = Path(excel_path)
    df = pd.read_excel(p, dtype=str, keep_default_na=True, na_filter=True)
    df.columns = [c.strip() for c in df.columns]
    # filtra colunas relevantes e remove linhas vazias
    df = df[[c for c in COLUMNS_EXCEL if c in df.columns]].copy()
    df = df.dropna(how="all")

    registros: Dict[str, Dict[str, Any]] = {}
    for _, r in df.iterrows():
        row = r.to_dict()
        raw_sku = _s(row.get("sku"))
        if not raw_sku:
            continue
        try:
            norm = _normalize_row(row)
        except ValueError:
            # pula linha incompleta (ex.: sem preco_compra)
            continue
        sku = norm["sku"]
        if not sku or sku in registros:
            continue
        registros[sku] = norm
    return registros

def carregar_excel_normalizado_detalhado(excel_path: Path | str) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Versão detalhada: além do dicionário {sku: registro}, devolve uma lista 'skipped'
    com as linhas ignoradas e seus respectivos motivos.
    Motivos possíveis:
      - "sem_sku"
      - "campos_obrigatorios_ausentes" (ex.: preco_compra)
      - "sku_duplicado"
    """
    p = Path(excel_path)
    df = pd.read_excel(p, dtype=str, keep_default_na=True, na_filter=True)
    df.columns = [c.strip() for c in df.columns]
    df = df[[c for c in COLUMNS_EXCEL if c in df.columns]].copy()
    df = df.dropna(how="all")

    registros: Dict[str, Dict[str, Any]] = {}
    skipped: List[Dict[str, Any]] = []

    for idx, r in df.iterrows():
        row = r.to_dict()
        raw_sku = _s(row.get("sku"))
        raw_titulo = _s(row.get("titulo"))
        if not raw_sku:
            skipped.append({
                "row_index": int(idx),
                "sku_detectado": None,
                "titulo_detectado": raw_titulo,
                "motivos": ["sem_sku"],
            })
            continue
        try:
            norm = _normalize_row(row)
        except ValueError:
            skipped.append({
                "row_index": int(idx),
                "sku_detectado": raw_sku,
                "titulo_detectado": raw_titulo,
                "motivos": ["campos_obrigatorios_ausentes"],
            })
            continue
        sku = norm["sku"]
        if not sku:
            skipped.append({
                "row_index": int(idx),
                "sku_detectado": None,
                "titulo_detectado": raw_titulo,
                "motivos": ["sem_sku"],
            })
            continue
        if sku in registros:
            skipped.append({
                "row_index": int(idx),
                "sku_detectado": sku,
                "titulo_detectado": raw_titulo,
                "motivos": ["sku_duplicado"],
            })
            continue
        registros[sku] = norm
    return registros, skipped