from __future__ import annotations
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Dict
import unicodedata

from app.config.paths import BASE_PATH, Marketplace, Regiao, Camada

# === Diretórios-base do domínio Meli (custos variáveis) ===
DOMAIN_DIR = BASE_PATH / "data" / "costs" / "variable" / "meli"

def domain_dir() -> Path:
    return DOMAIN_DIR

def excel_dir(ano: int, mes: int, regiao: Regiao) -> Path:
    """Diretório onde ficam os Excel de entrada do mês/região."""
    return DOMAIN_DIR / f"{ano:04d}" / f"{mes:02d}" / regiao.value / "excel"

def raw_dir(ano: int, mes: int, regiao: Regiao) -> Path:
    """Diretório 'raw' (se existir para dumps auxiliares)."""
    return DOMAIN_DIR / f"{ano:04d}" / f"{mes:02d}" / regiao.value / "raw"

def pp_dir(ano: int, mes: int, regiao: Regiao, camada: Camada = Camada.PP) -> Path:
    """Diretório 'pp' de saída normalizada (pós-processado)."""
    return DOMAIN_DIR / f"{ano:04d}" / f"{mes:02d}" / regiao.value / camada.value

def ensure_dirs(ano: int, mes: int, regiao: Regiao) -> None:
    """Garante existência dos diretórios comuns (excel/pp)."""
    excel_dir(ano, mes, regiao).mkdir(parents=True, exist_ok=True)
    pp_dir(ano, mes, regiao).mkdir(parents=True, exist_ok=True)

# === Arquivos PP de saída (nomes canônicos) ===
def pp_outfile_faturamento_meli(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "faturamento_meli_pp.json"

def pp_outfile_faturamento_mercadopago(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "faturamento_mercadopago_pp.json"

def pp_outfile_pagamentos_estornos(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "pagamentos_estornos_pp.json"

def pp_outfile_detalhe_pagamentos(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "detalhe_pagamentos_mes_pp.json"

def pp_outfile_tarifas_full_armazenamento(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "tarifas_full_armazenamento_pp.json"

def pp_outfile_tarifas_full_retirada_estoque(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "tarifas_full_retirada_estoque_pp.json"

def pp_outfile_tarifas_full_servico_coleta(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "tarifas_full_servico_coleta_pp.json"

def pp_outfile_tarifas_full_armazenamento_prolongado(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "tarifas_full_armazenamento_prolongado_pp.json"

def pp_outfile_fatura_resumo(ano: int, mes: int, regiao: Regiao) -> Path:
    return pp_dir(ano, mes, regiao) / "fatura_resumo_pp.json"

def pp_outfile(nome: str, ano: int, mes: int, regiao: Regiao) -> Path:
    """Helper genérico para novos arquivos PP."""
    safe = nome.strip().replace(" ", "_").lower()
    if not safe.endswith(".json"):
        safe += ".json"
    return pp_dir(ano, mes, regiao) / safe

# === Candidatos de ARQUIVOS Excel por fonte (para variações de nome) ===
FATURAMENTO_MELI_XLSX_CANDIDATES: List[str] = [
    # Padrões comuns
    "Relatorio_Faturamento_MercadoLivre_{mesnome}{ano}.xlsx",
    "Relatorio_Faturamento_Mercado_Livre_{mesnome}{ano}.xlsx",
    # Fallbacks genéricos
    "Faturamento_Meli_{ano}_{mes:02d}.xlsx",
    "Faturamento_Mercado_Livre_{ano}_{mes:02d}.xlsx",
]

PAGAMENTOS_FATURAS_XLSX_CANDIDATES: List[str] = [
    "Relatorio_Pagamento_Faturas_{mesnome}{ano}.xlsx",
    "Relatorio_Pagamento_de_Faturas_{mesnome}{ano}.xlsx",
    "Pagamentos_Faturas_{ano}_{mes:02d}.xlsx",
]

TARIFAS_FULL_ARMAZENAMENTO_XLSX_CANDIDATES: List[str] = [
    "Relatorio_Tarifas_Full_{mesnome}{ano}.xlsx",
    "Tarifas_Full_{ano}_{mes:02d}.xlsx",
]

# Se sua fonte separa por aba/tipo em arquivos distintos, crie listas específicas:
TARIFAS_FULL_RETIRADA_ESTOQUE_XLSX_CANDIDATES = TARIFAS_FULL_ARMAZENAMENTO_XLSX_CANDIDATES
TARIFAS_FULL_SERVICO_COLETA_XLSX_CANDIDATES   = TARIFAS_FULL_ARMAZENAMENTO_XLSX_CANDIDATES
TARIFAS_FULL_ARMAZENAMENTO_PROLONGADO_XLSX_CANDIDATES = TARIFAS_FULL_ARMAZENAMENTO_XLSX_CANDIDATES

# === Resolução robusta de arquivos ===
MESES_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
}

def _render_candidates(cands: Iterable[str], ano: int, mes: int) -> List[str]:
    mesnome = MESES_PT.get(mes, f"{mes:02d}")
    out: List[str] = []
    for c in cands:
        try:
            out.append(c.format(ano=ano, mes=mes, mesnome=mesnome))
        except Exception:
            out.append(c)
    return out

def find_excel_by_candidates(base_dir: Path, candidates: Iterable[str]) -> Optional[Path]:
    """Retorna o primeiro arquivo existente no diretório que bata com a lista de candidatos."""
    for name in candidates:
        p = base_dir / name
        if p.exists():
            return p
    # tentativa adicional por 'startswith' (casos com sufixo de exportação)
    existing = list(base_dir.glob("*.xlsx"))
    cnorm = [name.lower() for name in candidates]
    for f in existing:
        fn = f.name.lower()
        if any(fn.startswith(prefix.replace("{mesnome}", "").replace("{ano}", "")) for prefix in cnorm):
            return f
    return None

# === Resolução de ABAS (sheet names) com normalização ===
def _norm(s: str) -> str:
    s = "" if s is None else str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.strip().lower().split())

# Candidatos de nome de ABA para Tarifas FULL
SHEET_CANDS_TARIFAS_FULL_RETIRADA: List[str] = [
    "Custo por retirada de estoque",
    "Custos por retirada de estoque",
    "Custo retirada estoque",
]
SHEET_CANDS_TARIFAS_FULL_ARMAZEN: List[str] = [
    "Custo por armazenamento",
    "Custos por armazenamento",
    "Armazenamento",
]
SHEET_CANDS_TARIFAS_FULL_COLETA: List[str] = [
    "Servico de coleta",
    "Serviço de coleta",
    "Coleta",
]
SHEET_CANDS_TARIFAS_FULL_ARMAZEN_PROL: List[str] = [
    "Armazenamento prolongado",
    "Custo por armazenamento prolongado",
]

def resolve_sheet_name(available: Iterable[str], preferred: Iterable[str], *, keywords: Tuple[str, ...] = ()) -> Optional[str]:
    """
    Tenta resolver o nome da aba:
      1) match exato após normalização com 'preferred';
      2) por palavras-chave (todas devem estar contidas) se fornecidas;
      3) None se não achar (o chamador decide tratar como DF vazio).
    """
    av_norm: Dict[str, str] = {s: _norm(s) for s in available}
    pref_norm = [_norm(p) for p in preferred]
    # 1) match exato normalizado
    for s, ns in av_norm.items():
        if ns in pref_norm:
            return s
    # 2) keywords
    if keywords:
        for s, ns in av_norm.items():
            if all(k in ns for k in keywords):
                return s
    return None

# === Resumo da Fatura: buckets oficiais e mapeamento (para agregação) ===
REQUIRED_BUCKETS: List[str] = [
    "outras_tarifas",
    "tarifas_venda",
    "tarifas_envios_ml",
    "tarifas_publicidade",
    "tarifas_envios_full",
    "taxas_parcelamento",
    "minha_pagina",
    "servicos_mercado_pago",
    "cancelamentos",
]

BUCKET_MAP: Dict[str, str] = {
# Use chaves NORMALIZADAS (mesma função _norm) para a origem (detalhe) -> bucket
    # gerais
    "outras tarifas": "outras_tarifas",
    # venda (comissão + gestão)
    "tarifa de venda": "tarifas_venda",
    "tarifas de venda": "tarifas_venda",
    "custo de gestao da venda": "tarifas_venda",
    "custo de gestao da venda full": "tarifas_venda",
    # envios ML (extra/intermunicipal)
    "tarifa de envios no mercado livre": "tarifas_envios_ml",
    "tarifa de envio extra ou intermunicipal": "tarifas_envios_ml",
    # publicidade
    "tarifa de publicidade": "tarifas_publicidade",
    "tarifas de publicidade": "tarifas_publicidade",
    "campanhas de publicidade - product ads": "tarifas_publicidade",
    "campanas de publicidad - brand ads": "tarifas_publicidade",
    # full
    "tarifa de envios full": "tarifas_envios_full",
    "custo do servico de coleta full": "tarifas_envios_full",
    "custo por retirada de estoque full": "tarifas_envios_full",
    "tarifa pelo servico de armazenamento full": "tarifas_envios_full",
    "tarifa por estoque antigo no full": "tarifas_envios_full",
    # parcelamento (tratar também por prefixo no aggregator)
    "taxas de parcelamento": "taxas_parcelamento",
    "taxa de parcelamento (equivalente ao acrescimo no preco pago pelo comprador)": "taxas_parcelamento",
    # outros
    "minha pagina": "minha_pagina",
    "servicos do mercado pago": "servicos_mercado_pago",
    "cancelamentos": "cancelamentos",
}

# Se True, interrompe quando houver detalhes não mapeados; se False, apenas reporta
STRICT_BUCKETS: bool = False

# === Marketplace alvo deste módulo ===
MARKETPLACE = Marketplace.MELI
