from __future__ import annotations

import os
from glob import glob
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

# Importar SOMENTE itens transversais do paths central
from app.config.paths import BASE_PATH, DATA_DIR, Marketplace, Regiao
from .validators import validate_regras_ml  # valida o contrato do YAML


# ---------------------------
# PATHS do domínio precificação
# ---------------------------

def produtos_pp_path() -> Path:
    """
    Caminho 'preferido' (apenas para mensagens).
    A leitura real usa produtos_pp_candidates().
    """
    return DATA_DIR / "produtos" / "pp" / "produtos_pp.json"


def _unique_append(cands: list[Path], p: Path) -> None:
    if p not in cands:
        cands.append(p)


def produtos_pp_candidates() -> list[Path]:
    """
    Possíveis locais dos PP de produtos (ordem de preferência).
    Suporta nome global, regionais, variantes em 'marketplaces/meli',
    fallback glob e override via variável de ambiente.
    """
    cands: list[Path] = []

    # 0) Override por variável de ambiente deste domínio
    env_path = os.getenv("PRODUTOS_PP_PATH")
    if env_path:
        _unique_append(cands, Path(env_path))

    # 1) Padrões em data/produtos/pp
    base = DATA_DIR / "produtos" / "pp"
    _unique_append(cands, base / "produtos_pp.json")
    _unique_append(cands, base / "produtos.json")  # seu arquivo atual

    # 2) Regionais comuns
    for suf in ("sp", "mg", "es", "rj", "pr", "rs", "sc"):
        _unique_append(cands, base / f"produtos_{suf}_pp.json")

    # 3) Variantes por marketplace (alguns projetos guardam por canal)
    ml_base = DATA_DIR / "marketplaces" / "meli" / "produtos" / "pp"
    _unique_append(cands, ml_base / "produtos_pp.json")
    for suf in ("sp", "mg", "es", "rj", "pr", "rs", "sc"):
        _unique_append(cands, ml_base / f"produtos_{suf}_pp.json")
        _unique_append(cands, ml_base / f"produtos_{suf}_meli_pp.json")

    # 4) Outros nomes típicos
    _unique_append(cands, base / "produtos_meli_pp.json")
    _unique_append(cands, base / "pp_produtos.json")

    # 5) Fallback glob amplo dentro de DATA_DIR
    try:
        for pat in (
            str(DATA_DIR / "produtos" / "pp" / "produtos*_pp.json"),
            str(DATA_DIR / "produtos" / "pp" / "produtos.json"),
            str(DATA_DIR / "marketplaces" / "meli" / "produtos" / "pp" / "produtos*_pp.json"),
            str(DATA_DIR / "**" / "produtos*_pp.json"),
        ):
            for g in glob(pat, recursive=True):
                _unique_append(cands, Path(g))
    except Exception:
        pass

    return cands


def anuncios_pp_path_meli(regiao: Optional[Regiao] = None) -> Path:
    """
    PP de anúncios do Mercado Livre (apenas para mensagens).
    A leitura real tentará candidatos em anuncios_pp_candidates_meli().
    """
    base = DATA_DIR / "marketplaces" / Marketplace.MELI.value / "anuncios"
    if regiao is not None:
        return base / "pp" / f"anuncios_{regiao.value.lower()}_pp.json"
    return base / "pp" / "anuncios_pp.json"


def anuncios_pp_candidates_meli(regiao: Optional[Regiao] = None) -> list[Path]:
    """
    Retorna, em ordem de preferência, possíveis locais do PP de anúncios do ML.
    Suporta nomeação regional por sufixo: anuncios_{regiao}_pp.json.
    """
    base = DATA_DIR / "marketplaces" / Marketplace.MELI.value / "anuncios"
    candidates: list[Path] = []

    def _reg_suf(r: Regiao) -> str:
        return r.value.lower()

    if regiao is not None:
        suf = _reg_suf(regiao)
        # Preferência: arquivo com sufixo regional na pasta pp
        candidates.append(base / "pp" / f"anuncios_{suf}_pp.json")
        # Outras convenções que podem existir no projeto
        candidates.append(base / regiao.value / "pp" / "anuncios_pp.json")
        candidates.append(base / regiao.value / "anuncios_pp.json")
        # Genéricos
        candidates.append(base / "pp" / "anuncios_pp.json")
        candidates.append(base / "anuncios_pp.json")
    else:
        # Quando não há região, tentamos regionais e também genéricos
        for suf in ("sp", "mg"):
            candidates.append(base / "pp" / f"anuncios_{suf}_pp.json")
        candidates.append(base / "pp" / "anuncios_pp.json")
        candidates.append(base / "anuncios_pp.json")
    return candidates


def regras_yaml_path_meli() -> Path:
    """
    Caminho do YAML de regras para o canal Mercado Livre.
    Mantido dentro do próprio módulo para versionamento e ajuste rápido.
    """
    return BASE_PATH / "app" / "utils" / "precificacao" / "regras" / "mercado_livre.yaml"


# ---------------------------
# Carregamento/normalização de regras
# ---------------------------

def _load_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_regras_ml() -> Dict[str, Any]:
    """
    Carrega as regras fixas de Mercado Livre (FULL e fora do FULL),
    valida contrato e NORMALIZA para o service/metricas.
    Percentuais devem vir em FRAÇÃO (0.10 = 10%).
    """
    data = _load_yaml(regras_yaml_path_meli())
    # Validação de contrato (falha cedo com mensagens claras)
    validate_regras_ml(data)

    default = data.get("default", {}) or {}
    full = data.get("full", {}) or {}
    nao_full = data.get("nao_full", {}) or {}
    comissao = data.get("comissao", {}) or {}

    # Repassa estruturas utilizadas no cálculo (listas/objetos inteiros do YAML)
    return {
        "canal": "meli",
        "default": {
            "imposto_pct": float(default.get("imposto_pct", 0.0)),
            "marketing_pct": float(default.get("marketing_pct", 0.0)),
            # Pass-through (mantemos como está no YAML; metrics.parse_frac aceita vírgula)
            "mcp_min": default.get("mcp_min"),
            "mcp_max": default.get("mcp_max"),
            "frete_pct_sobre_custo": default.get("frete_pct_sobre_custo"),
        },
        "full": {
            "frete_pct": float(full.get("frete_pct", 0.0)) if "frete_pct" in full else 0.0,
            "take_rate_pct": float(full.get("take_rate_pct", 0.0)) if "take_rate_pct" in full else 0.0,
            "custo_fixo_por_unidade_brl": full.get("custo_fixo_por_unidade_brl", []),
            # Pass-through de metas e frete % sobre custo (se houver override no perfil)
            "mcp_min": full.get("mcp_min"),
            "mcp_max": full.get("mcp_max"),
            "frete_pct_sobre_custo": full.get("frete_pct_sobre_custo"),
        },
        "nao_full": {
            "frete_pct": float(nao_full.get("frete_pct", 0.0)) if "frete_pct" in nao_full else 0.0,
            "take_rate_pct": float(nao_full.get("take_rate_pct", 0.0)) if "take_rate_pct" in nao_full else 0.0,
            "custo_fixo_por_unidade_brl": nao_full.get("custo_fixo_por_unidade_brl", []),
            "frete_gratis_40538": nao_full.get("frete_gratis_40538", {}),
            # Pass-through de metas e frete % sobre custo (se houver override no perfil)
            "mcp_min": nao_full.get("mcp_min"),
            "mcp_max": nao_full.get("mcp_max"),
            "frete_pct_sobre_custo": nao_full.get("frete_pct_sobre_custo"),
        },
        "comissao": {
            "classico_pct": float(comissao.get("classico_pct", 0.0)),
        },
    }


# --- NOVO: path/loader de overrides do ML ---
def overrides_yaml_path_meli() -> Path:
    """
    Local do arquivo de overrides do canal ML dentro do domínio de precificação.
    """
    return BASE_PATH / "app" / "utils" / "precificacao" / "regras" / "overrides.yaml"

def get_overrides_ml() -> Dict[str, Any]:
    """
    Carrega overrides opcionais (cenários e regras por item) para o canal ML.
    Estrutura esperada:
      canal: meli
      cenarios: { <nome>: { ..._override: ... } }
      por_item: { <mlb|sku|gtin>: { campanha_id, vigencia:{from,to}, ..._override } }
    """
    p = overrides_yaml_path_meli()
    if not p.exists():
        return {"canal": "meli", "cenarios": {}, "por_item": {}}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # contrato mínimo
    data.setdefault("canal", "meli")
    data.setdefault("cenarios", {})
    data.setdefault("por_item", {})
    return data