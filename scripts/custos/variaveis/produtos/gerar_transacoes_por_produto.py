from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.utils.costs.variable.produtos.config import transacoes_por_produto_json
from app.utils.costs.variable.produtos.service import (
    read_faturamento_pp_and_build_transacoes,
)

# Enums e utilidades transversais
from app.config.paths import Regiao, Marketplace, backup_path, atomic_write_json

# Sinks (classe pode variar entre projetos)
FileSinkClass = None
try:
    from app.utils.core.result_sink.json_file_sink import JSONFileSink as FileSinkClass  # type: ignore
except Exception:
    try:
        from app.utils.core.result_sink.json_file_sink import JsonFileSink as FileSinkClass  # type: ignore
    except Exception:
        try:
            from app.utils.core.result_sink.json_file_sink import ResultJSONFileSink as FileSinkClass  # type: ignore
        except Exception:
            FileSinkClass = None

# StdoutSink (preferencial); se não houver, um fallback leve
try:
    from app.utils.core.result_sink.stdout_sink import StdoutSink  # type: ignore
except Exception:
    class StdoutSink:
        def emit(self, result: dict, *, name: Optional[str] = None, sample: int = 3) -> None:
            if name:
                print(f"\n=== Resultado: {name} ===")
            meta = result.get("meta", {})
            recs = result.get("records", []) or []
            n = 3
            try:
                n = max(0, int(sample))
            except Exception:
                pass
            print(json.dumps({"meta": meta, "sample": recs[:n]}, ensure_ascii=False, indent=2))


# Módulo de domínio (custos → variável → produtos)


# ---------------- Helpers locais ----------------

def _project_root_from_here() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "app":
            return p.parent
    return here.parents[-1]

def _to_path(p: Union[str, Path]) -> Path:
    """
    Converte para Path e resolve placeholders ${BASE_PATH}/{BASE_PATH}
    apontando para a raiz do repo.
    """
    if isinstance(p, Path):
        return p
    s = str(p)
    if "${BASE_PATH}" in s or "{BASE_PATH}" in s:
        root = _project_root_from_here()
        s = s.replace("${BASE_PATH}", str(root)).replace("{BASE_PATH}", str(root))
    return Path(s)

def _build_meta(market: Marketplace, ano: int, mes: int, regiao: Regiao, n: int) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S"),
        "market": market.value,
        "ano": ano,
        "mes": mes,
        "regiao": regiao.value,
        "source": "faturamento_pp",
        "records_count": n,
    }

def _dedupe(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Deduplicação por chave estável.
    Ajuste a chave se houver campos que distingam linhas 'iguais' no mesmo pedido.
    """
    seen: Dict[Tuple[str, str, float, float], Dict[str, Any]] = {}
    for r in records:
        chave = (
            str(r.get("numero_venda") or "").strip(),
            str(r.get("numero_anuncio") or "").strip(),
            float(r.get("quantidade") or 0.0),
            float(r.get("valor_transacao") or 0.0),
        )
        seen[chave] = r
    return list(seen.values()), len(records) - len(seen)

def _emit_file_result(destino: Union[str, Path], result: dict) -> None:
    """
    Emite resultado para arquivo:
      - Tenta instanciar o sink de arquivo e emitir (vários contratos conhecidos)
      - Fallback: atomic_write_json(destino, do_backup=True, backup_dir=backup_path(destino))
    """
    dst = _to_path(destino)
    out_dir = dst.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Tentativa: sink com assinatura .emit(path_or_obj, ...)
    if FileSinkClass is not None:
        try:
            # a) Alguns projetos instanciam sem args e aceitam caminho direto
            sink = FileSinkClass()  # type: ignore
            if hasattr(sink, "emit"):
                try:
                    # contrato 1: emit(path, obj, do_backup=True)
                    sink.emit(dst, result, do_backup=True)  # type: ignore
                    return
                except TypeError:
                    pass
            # b) Outros recebem diretório e um "name"
            sink = FileSinkClass(out_dir)  # type: ignore
            if hasattr(sink, "emit"):
                try:
                    sink.emit(result, name=dst.stem)  # type: ignore
                    return
                except TypeError:
                    pass
            if hasattr(sink, "write"):
                try:
                    sink.write(result, name=dst.stem)  # type: ignore
                    return
                except TypeError:
                    try:
                        sink.write(meta=result.get("meta"), records=result.get("records"), name=dst.stem)  # type: ignore
                        return
                    except TypeError:
                        pass
        except Exception:
            # cai no fallback
            pass

    # 2) Fallback seguro
    try:
        atomic_write_json(str(dst), result, do_backup=True, backup_dir=str(backup_path(dst)))
    except TypeError:
        # caso a assinatura não aceite backup_dir
        atomic_write_json(str(dst), result, do_backup=True)


# ---------------- CLI ----------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Gera JSON de transações por produto a partir do faturamento PP (custos → variável → produtos)."
    )
    p.add_argument("--market", default="meli", choices=[m.value for m in Marketplace], help="Marketplace (ex.: meli)")
    p.add_argument("--ano", type=int, required=True)
    p.add_argument("--mes", type=int, required=True)
    p.add_argument("--regiao", required=True,
                   help="Região: sp, mg, ou lista separada por vírgula (ex.: sp,mg) ou 'all'.")
    p.add_argument("--debug", action="store_true", help="Exibe logs detalhados e amostra no console.")
    p.add_argument("--limit", type=int, default=0, help="Opcional: limitar quantidade de registros (debug).")
    p.add_argument(
        "--source-path",
        type=str,
        default="",
        help="Opcional: caminho explícito do faturamento PP (para troubleshooting).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    market = Marketplace(args.market)
    source_override = args.source_path
    # suporta sp,mg,sp,mg ou 'all'
    if args.regiao.lower() == "all":
        regioes = [Regiao.SP, Regiao.MG]
    else:
        regioes = [Regiao(r.strip()) for r in args.regiao.split(",")]
    for regiao in regioes:
        recs: List[Dict[str, Any]] = read_faturamento_pp_and_build_transacoes(
            market,
            args.ano,
            args.mes,
            regiao,
            debug=args.debug,
            source_path_override=source_override,
        )
        if args.limit and args.limit > 0:
            recs = recs[: args.limit]

        destino = _to_path(transacoes_por_produto_json(args.ano, args.mes, regiao))

        if args.debug:
            print(f"[DBG] market={market.value} ano={args.ano} mes={args.mes} regiao={regiao.value}")
            if source_override:
                print(f"[DBG] source override = {source_override}")
            print(f"[ECHO] destino: {destino} (exists={destino.exists()})")
            print(f"[ECHO] total registros: {len(recs)}")

        result = {
            "meta": _build_meta(market, args.ano, args.mes, regiao, len(recs)),
            "records": recs,
        }
        _emit_file_result(destino, result)
        print(f"[OK] gravado: {destino}")


    # 1) Ler PP do faturamento e transformar em transações


if __name__ == "__main__":
    main()
