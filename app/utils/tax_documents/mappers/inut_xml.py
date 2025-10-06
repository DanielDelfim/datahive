from __future__ import annotations
from xml.etree import ElementTree as ET
from typing import Optional, Dict

def parse_inutilizacao(xml_bytes: bytes) -> Optional[Dict]:
    root = ET.fromstring(xml_bytes)
    if not (root.tag.endswith("procInutNFe") or root.find(".//{*}inutNFe") is not None):
        return None
    inf = root.find(".//{*}retInutNFe/{*}infInut")
    if inf is None:
        return None
    return {
        "cStat": (inf.findtext(".//{*}cStat") or "").strip(),
        "CNPJ": (inf.findtext(".//{*}CNPJ") or "").strip(),
        "ano":  (inf.findtext(".//{*}ano") or "").strip(),
        "mod":  (inf.findtext(".//{*}mod") or "").strip(),
        "serie":(inf.findtext(".//{*}serie") or "").strip(),
        "nNFIni": (inf.findtext(".//{*}nNFIni") or "").strip(),
        "nNFFin": (inf.findtext(".//{*}nNFFin") or "").strip(),
    }
