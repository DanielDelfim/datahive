# app/utils/tax_documents/mappers/evento_generico.py
from __future__ import annotations
from xml.etree import ElementTree as ET
from typing import Optional, Dict

def parse_evento(xml_bytes: bytes) -> Optional[Dict]:
    """
    Parse genérico de procEventoNFe.
    Retorna dict com {tpEvento, chNFe, cStat, dhEvento, nProt, xJust} ou None.
    """
    root = ET.fromstring(xml_bytes)
    if not (root.tag.endswith("procEventoNFe") or root.find(".//{*}evento") is not None):
        return None

    tp  = (root.findtext(".//{*}tpEvento") or "").strip()
    ch  = (root.findtext(".//{*}chNFe") or "").strip()
    cs  = (root.findtext(".//{*}retEvento/{*}infEvento/{*}cStat") or "").strip()
    dh  = (root.findtext(".//{*}dhEvento") or "").strip()
    pr  = (root.findtext(".//{*}retEvento/{*}infEvento/{*}nProt") or "").strip()
    jt  = (root.findtext(".//{*}detEvento/{*}xJust") or "").strip()

    return {"tpEvento": tp, "chNFe": ch, "cStat": cs, "dhEvento": dh, "nProt": pr, "xJust": jt}
