from __future__ import annotations

from typing import Any, Dict, Iterable


class RegraInvalida(ValueError):
    """Erro de validação de regras de precificação."""


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float))


def _req_keys(obj: Dict[str, Any], keys: Iterable[str], raiz: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise RegraInvalida(f"[{raiz}] faltando chaves obrigatórias: {', '.join(missing)}")


def _pct_in_range(v: Any, raiz: str, campo: str) -> None:
    if not _is_number(v):
        raise RegraInvalida(f"[{raiz}] '{campo}' deve ser numérico em fração (ex.: 0.14)")
    v = float(v)
    if v < 0.0 or v > 1.0:
        raise RegraInvalida(
            f"[{raiz}] '{campo}' fora de [0,1]. Use fração (ex.: 0.14 para 14%). Valor recebido: {v}"
        )


def _nonneg_number(v: Any, raiz: str, campo: str) -> None:
    if not _is_number(v):
        raise RegraInvalida(f"[{raiz}] '{campo}' deve ser numérico (>= 0)")
    if float(v) < 0.0:
        raise RegraInvalida(f"[{raiz}] '{campo}' não pode ser negativo. Valor recebido: {v}")


def _validate_faixas_valor(items: Any, raiz: str, chave_lista: str, allow_percent: bool = False) -> None:
    if not isinstance(items, list):
        raise RegraInvalida(f"[{raiz}] '{chave_lista}' deve ser lista")

    seen_otherwise = False
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise RegraInvalida(f"[{raiz}] item #{i} de '{chave_lista}' deve ser objeto")

        if item.get("otherwise"):
            # Faixa de fallback
            if seen_otherwise:
                raise RegraInvalida(f"[{raiz}] múltiplos 'otherwise' em '{chave_lista}'")
            seen_otherwise = True
            if "valor" not in item:
                raise RegraInvalida(f"[{raiz}] item 'otherwise' em '{chave_lista}' requer 'valor'")
            _nonneg_number(item["valor"], raiz, f"{chave_lista}[{i}].valor")
            continue

        if "max_preco" in item:
            _nonneg_number(item["max_preco"], raiz, f"{chave_lista}[{i}].max_preco")
        elif "max_kg" in item:
            _nonneg_number(item["max_kg"], raiz, f"{chave_lista}[{i}].max_kg")
        else:
            raise RegraInvalida(
                f"[{raiz}] item #{i} em '{chave_lista}' requer 'max_preco' ou 'max_kg' (ou 'otherwise')"
            )

        if allow_percent and "valor_pct_do_preco" in item:
            _pct_in_range(item["valor_pct_do_preco"], raiz, f"{chave_lista}[{i}].valor_pct_do_preco")
        elif "valor" in item:
            _nonneg_number(item["valor"], raiz, f"{chave_lista}[{i}].valor")
        else:
            ok = "valor_pct_do_preco" if allow_percent else "valor"
            raise RegraInvalida(f"[{raiz}] item #{i} em '{chave_lista}' requer '{ok}'")


def validate_regras_ml(data: Dict[str, Any]) -> None:
    """
    Valida a estrutura e os intervalos do YAML de Mercado Livre.
    Levanta RegraInvalida (ValueError) em caso de problemas.
    """
    if not isinstance(data, dict):
        raise RegraInvalida("Documento de regras deve ser um objeto (dict)")

    # Top-level
    _req_keys(data, ["canal", "default", "comissao", "full", "nao_full"], "regras_ml")

    # default
    default = data["default"]
    if not isinstance(default, dict):
        raise RegraInvalida("[default] deve ser objeto")
    _req_keys(default, ["imposto_pct", "marketing_pct"], "default")
    _pct_in_range(default["imposto_pct"], "default", "imposto_pct")
    _pct_in_range(default["marketing_pct"], "default", "marketing_pct")

    # comissao
    comissao = data["comissao"]
    if not isinstance(comissao, dict):
        raise RegraInvalida("[comissao] deve ser objeto")
    _req_keys(comissao, ["classico_pct"], "comissao")
    _pct_in_range(comissao["classico_pct"], "comissao", "classico_pct")

    # full
    full = data["full"]
    if not isinstance(full, dict):
        raise RegraInvalida("[full] deve ser objeto")
    if "custo_fixo_por_unidade_brl" not in full:
        raise RegraInvalida("[full] requer 'custo_fixo_por_unidade_brl'")
    _validate_faixas_valor(full["custo_fixo_por_unidade_brl"], "full", "custo_fixo_por_unidade_brl")

    # nao_full
    nf = data["nao_full"]
    if not isinstance(nf, dict):
        raise RegraInvalida("[nao_full] deve ser objeto")

    # custo fixo por unidade (padrão de não-Full)
    if "custo_fixo_por_unidade_brl" in nf:
        _validate_faixas_valor(
            nf["custo_fixo_por_unidade_brl"],
            "nao_full",
            "custo_fixo_por_unidade_brl",
            allow_percent=True,
        )

    # frete_gratis_40538 (opcional, mas se existir, checar contrato)
    if "frete_gratis_40538" in nf:
        fg = nf["frete_gratis_40538"]
        if not isinstance(fg, dict):
            raise RegraInvalida("[nao_full.frete_gratis_40538] deve ser objeto")
        _req_keys(fg, ["threshold_preco_brl", "tabelas_por_preco"], "nao_full.frete_gratis_40538")
        _nonneg_number(fg["threshold_preco_brl"], "nao_full.frete_gratis_40538", "threshold_preco_brl")

        tpp = fg["tabelas_por_preco"]
        if not isinstance(tpp, dict):
            raise RegraInvalida("[nao_full.frete_gratis_40538.tabelas_por_preco] deve ser objeto")

        # Cada banda de preço tem faixas por peso
        for banda, faixas in tpp.items():
            if not isinstance(banda, str):
                raise RegraInvalida("[nao_full.frete_gratis_40538.tabelas_por_preco] chave de banda deve ser string")
            _validate_faixas_valor(
                faixas,
                f"nao_full.frete_gratis_40538['{banda}']",
                "faixas_peso",
                allow_percent=False,
            )
