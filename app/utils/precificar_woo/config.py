# app/utils/precificar_woo/config.py
from dataclasses import dataclass
from pathlib import Path
from app.config.paths import Paths  # fonte única

@dataclass(frozen=True)
class WooPaths:
    regras_dir: Path
    regras_yaml: Path
    overrides_yaml: Path
    out_current: Path

def get_paths(regiao="br"):
    base = Paths.data_root() / "precificacao" / "precificar_woo"
    regras_dir = Path(__file__).parent / "regras"

    # aceita enum (com .value) ou string
    reg_code = getattr(regiao, "value", str(regiao)).lower()
    if not reg_code:
        reg_code = "br"

    return WooPaths(
        regras_dir=regras_dir,
        regras_yaml=regras_dir / "site_woocommerce.yaml",
        overrides_yaml=regras_dir / "overrides.yaml",
        out_current=base / "pp" / "current" / reg_code / f"site_precificacao_current_{reg_code}.json",
    )
