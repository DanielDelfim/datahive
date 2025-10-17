import json
import hashlib
import time
from app.config.paths import Stage, Marketplace, Regiao, Camada
from app.utils.core.result_sink.service import JsonFileSink
from app.utils.core.result_sink.multi_sink import MultiSink
from app.utils.core.result_sink.stdout_sink import StdoutSink
from app.utils.precificar_woo.config import get_paths
from app.utils.precificar_woo.service import construir_dataset

SCRIPT_NAME = "scripts/precificar_woo/gerar_pp_current.py"
SCRIPT_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

def _hash(payload) -> str:
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(s).hexdigest()

def main(stage: Stage = Stage.dev, regiao: Regiao = Regiao.br, dry_run: bool = False):
    paths = get_paths(regiao)
    doc = construir_dataset()
    payload = {"itens": doc["itens"]}
    meta = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage": stage.value, "marketplace": Marketplace.site.value,
        "regiao": regiao.value, "camada": Camada.pp.value,
        "schema_version": SCHEMA_VERSION,
        "script_name": SCRIPT_NAME, "script_version": SCRIPT_VERSION,
        "source_paths": [str(paths.regras_yaml), str(paths.overrides_yaml)],
        "row_count": len(payload["itens"]), "hash": _hash(payload),
        "ttl_hint": "current",
    }
    out = {"_meta": meta, **payload}
    sink = StdoutSink() if dry_run else MultiSink([JsonFileSink(paths.out_current)])
    sink.write(out)

if __name__ == "__main__":
    main()
