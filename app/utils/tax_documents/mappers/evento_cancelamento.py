from __future__ import annotations
from xml.etree import ElementTree as ET

def parse_evento_cancelamento(xml_bytes: bytes):
    """
    Retorna dict com {chNFe, cancelada: bool, dhEvento, nProt, xJust}
    ou None se não for evento de cancelamento.
    """
    root = ET.fromstring(xml_bytes)
    if not (root.tag.endswith("procEventoNFe") or root.find(".//{*}evento") is not None):
        return None

    tpEvento = (root.findtext(".//{*}tpEvento") or "").strip()
    if tpEvento != "110111":  # cancelamento
        return None

    chNFe = (root.findtext(".//{*}chNFe") or "").strip()
    cStat = (root.findtext(".//{*}retEvento/{*}infEvento/{*}cStat") or "").strip()
    cancelada = cStat in {"135", "155"}  # evento registrado
    dhEvento = (root.findtext(".//{*}dhEvento") or "").strip()
    nProt    = (root.findtext(".//{*}retEvento/{*}infEvento/{*}nProt") or "").strip()
    xJust    = (root.findtext(".//{*}detEvento/{*}xJust") or "").strip()

    return {"chNFe": chNFe, "cancelada": cancelada, "dhEvento": dhEvento, "nProt": nProt, "xJust": xJust}
