#C:\Apps\Datahive\scripts\amazon\sellers\obter_marketplaces_current.py
import argparse
import json
import time

from app.utils.amazon.client import AmazonSpApiClient
from app.utils.amazon import config
from app.config.paths import (
    DATA_DIR, Marketplace, Regiao, Camada,
    ensure_dir, atomic_write_json
)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regiao", default="sp", choices=[r.value for r in Regiao])
    ap.add_argument("--stage", default="dev")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    regiao = Regiao(args.regiao)

    cli = AmazonSpApiClient(
        base_url=config.API_BASE_URL,
        client_id=config.LWA_CLIENT_ID,
        client_secret=config.LWA_CLIENT_SECRET,
        refresh_token=config.LWA_REFRESH_TOKEN_BR,
        user_agent=config.USER_AGENT,
    )

    # Sellers API: marketplaces em que a conta participa
    resp = cli.get("/sellers/v1/marketplaceParticipations")
    rows = resp.get("payload") or resp.get("marketplaceParticipations") or []

    out = {
        "_meta": {
            "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "stage": args.stage,
            "marketplace": Marketplace.AMAZON.value,
            "regiao": regiao.value,
            "camada": Camada.PP.value,
            "schema_version": "1.0.0",
            "script_name": "obter_marketplaces_current",
            "script_version": "1.0.0",
            "source_paths": [],
            "row_count": len(rows),
        },
        "rows": rows,
    }

    # pp/current/<regiao>/sellers_current_<regiao>.json
    dest_dir = ensure_dir(
        DATA_DIR / "marketplaces" / Marketplace.AMAZON.value / "sellers" / Camada.PP.value / "current" / regiao.value
    )
    dest = dest_dir / f"sellers_current_{regiao.value}.json"

    if args.dry_run:
        print(json.dumps(out, ensure_ascii=False)[:1500])
    else:
        atomic_write_json(dest, out, do_backup=True)
        print(f"[OK] Gravado: {dest}")

if __name__ == "__main__":
    main()
