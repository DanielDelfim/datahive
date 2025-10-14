# scripts/vendas/amazon/obter_pedidos_current.py
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone

from app.config.paths import Regiao
from app.utils.vendas.amazon.service import obter_pedidos_por_periodo, destino_pp_current
from app.utils.core.result_sink.stdout_sink import StdoutSink
from app.utils.core.result_sink.json_file_sink import JsonFileSink

def _iso_or_day_start(s: str) -> str:
    return s if "T" in s else f"{s}T00:00:00Z"

def _periodo(dias: int) -> tuple[str, str]:
    agora = datetime.now(timezone.utc)
    fim_dt = agora - timedelta(minutes=5)  # margem de segurança >2min
    ini_dt = fim_dt - timedelta(days=dias)
    return (
        ini_dt.strftime("%Y-%m-%dT00:00:00Z"),
        fim_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regiao", default="sp", choices=[r.value for r in Regiao])
    ap.add_argument("--inicio", help="YYYY-MM-DD[Thh:mm:ssZ]")
    ap.add_argument("--fim", help="YYYY-MM-DD[Thh:mm:ssZ]")
    ap.add_argument("--dias", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    regiao = Regiao(args.regiao)

    if args.inicio and args.fim:
        inicio, fim = _iso_or_day_start(args.inicio), _iso_or_day_start(args.fim)
    else:
        inicio, fim = _periodo(args.dias)

    # clamp do fim para agora-5min
    fim_max = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if fim > fim_max:
        fim = fim_max

    out = obter_pedidos_por_periodo(inicio, fim, regiao)

    if args.dry_run:
        StdoutSink().write(out)
    else:
        dest = destino_pp_current(regiao)
        JsonFileSink(dest).write(out)
        StdoutSink().write({"_meta": out["_meta"]})

if __name__ == "__main__":
    main()
