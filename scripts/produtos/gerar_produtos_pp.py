# scripts/produtos/gerar_produtos_pp.py
"""
Lê o Excel de cadastro de produtos e gera produtos_pp.json normalizado.
ÚNICO AUTOR do JSON de produtos (pp).
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd

# Transversal (Enums)
from app.config.paths import Camada

# Result sink (fábrica) e paths do módulo
from app.utils.core.result_sink.service import resolve_sink_from_flags
from app.utils.produtos.config import (
    cadastro_produtos_excel, produtos_json, produtos_dir, COLUMNS_EXCEL,
    UNIDADES_MEDIDA, ORIGEM_MERCADORIA, REGIME_FISCAL, REQUIRED_MIN
)

from app.utils.core.produtos.units import (
    to_bool, to_int, to_float, calc_volume_m3,
    sanitize_gtin, sanitize_cnpj
)
from app.utils.core.produtos.validate import validate_required, coerce_in_set
# Paths do módulo + parâmetros:

def _load_excel(path: Path) -> pd.DataFrame:
    # dtype=str não garante ausência de NaN; manteremos _s() para sanitizar
    df = pd.read_excel(path, dtype=str, keep_default_na=True, na_filter=True)
    # normaliza colunas
    df.columns = [c.strip() for c in df.columns]
    missing_cols = [c for c in COLUMNS_EXCEL if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Colunas ausentes no Excel: {missing_cols}")
    return df[COLUMNS_EXCEL].copy()

def _s(v: object) -> str | None:
    """String segura: None/NaN -> None; trim; vazio -> None."""
    if v is None:
        return None
    try:
        # pandas NaN
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, str):
        s = v.strip()
        return s or None
    s = str(v).strip()
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

    # Textos
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

    # Volume (m3) — recalcula se possível; senão usa o informado
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

    # Medidas da caixa (cm) e pesos da caixa (g)
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

    # Validação mínima
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

def main():
    excel_path = cadastro_produtos_excel()
    out_path = produtos_json(Camada.PP)

    df = _load_excel(excel_path)
    registros = {}
    skipped_no_sku = 0
    skipped_required = 0

    for _, r in df.iterrows():
        row = r.to_dict()
        raw_sku = _s(row.get("sku"))
        if not raw_sku:
            skipped_no_sku += 1
            continue
        try:
            norm = _normalize_row(row)
        except ValueError as exc:
            if "campos obrigatórios ausentes" in str(exc).lower():
                skipped_required += 1
                continue
            raise
        sku = norm["sku"]
        if not sku:
            skipped_no_sku += 1
            continue
        if sku in registros:
            raise ValueError(f"SKU duplicado no Excel: {sku}")
        registros[sku] = norm

    payload = {
        "count": len(registros),
        "source": str(excel_path),
        "items": registros,
    }

    # ==== Escrita via RESULT SINK (JsonFileSink) ====
    sink = resolve_sink_from_flags(
        to_file=True,
        output_dir=produtos_dir(Camada.PP),
        prefix="produtos",
        keep=3,
        filename="produtos.json",
    )
    
    sink.emit(payload)

    print(f"[OK] Produtos PP → {out_path}")
    if skipped_no_sku:
        print(f"[WARN] Linhas ignoradas por falta de SKU: {skipped_no_sku}")
    if skipped_required:
        print(f"[WARN] Linhas ignoradas por falta de campos obrigatórios (ex.: preco_compra): {skipped_required}")

if __name__ == "__main__":
    main()
