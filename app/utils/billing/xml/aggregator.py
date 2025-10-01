from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Dict, Any, Iterable, List, Set

from .parser_xml import parse_xml_nfe, parse_xml_nfse

def _dedup(notas: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for n in notas:
        k = n.get("id_unico") or hashlib.sha1(str(n).encode()).hexdigest()
        if k in seen:
            continue
        seen.add(k)
        out.append(n)
    return out

def carregar_zip_dir(*, dir_raw: Path, regiao: str, market: str, incluir_modelos: Set[str] | None = None) -> List[Dict[str, Any]]:
    """
    Lê todos os .zip em dir_raw, percorre XMLs e aplica parser.
    """
    if incluir_modelos is None:
        incluir_modelos = {"NFe", "NFSe"}

    notas: List[Dict[str, Any]] = []
    for zip_path in sorted(dir_raw.glob("*.zip")):
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".xml"):
                    continue
                data = zf.read(name)
                # simples heurística: NF-e costuma ter <NFe ...>
                if b"<NFe" in data[:2000] and "NFe" in incluir_modelos:
                    n = parse_xml_nfe(data, regiao=regiao, market=market, origem_arquivo=f"{zip_path.name}::{name}")
                elif "NFSe" in incluir_modelos:
                    n = parse_xml_nfse(data, regiao=regiao, market=market, origem_arquivo=f"{zip_path.name}::{name}")
                else:
                    continue
                notas.append(n)
    return _dedup(notas)
