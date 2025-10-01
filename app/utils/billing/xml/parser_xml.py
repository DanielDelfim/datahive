from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, Any
from xml.etree import ElementTree as ET

def _text(el, path, default=None):
    x = el.find(path)
    return (x.text.strip() if x is not None and x.text is not None else default)

def _parse_datetime(dtstr: str) -> datetime:
    # tenta ISO ou formato NFe (YYYY-MM-DDTHH:MM:SS-03:00)
    try:
        return datetime.fromisoformat(dtstr)
    except Exception:
        # fallback sem tz → assumir UTC
        return datetime.strptime(dtstr[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)

def _mk_mes_comp(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"

def parse_xml_nfe(xml_bytes: bytes, *, regiao: str, market: str, origem_arquivo: str) -> Dict[str, Any]:
    """
    Parser simplificado de NF-e (modelo 55).
    Extrai campos essenciais para NotaResumo; campos ausentes são preenchidos com defaults.
    """
    try:
        root = ET.fromstring(xml_bytes)
        infNFe = root.find(".//infNFe")
        ide = root.find(".//ide")
        emit = root.find(".//emit")
        dest = root.find(".//dest")
        total = root.find(".//total/ICMSTot")
        dets = root.findall(".//det")

        chave = infNFe.attrib.get("Id", "").replace("NFe", "") if infNFe is not None else None
        numero = _text(ide, "nNF", "")
        serie = _text(ide, "serie", "")
        dhEmi = _text(ide, "dhEmi", "") or _text(ide, "dEmi", "")
        dt = _parse_datetime(dhEmi) if dhEmi else datetime.now(timezone.utc)

        emit_doc = _text(emit, "CNPJ") or _text(emit, "CPF")
        dest_doc = _text(dest, "CNPJ") or _text(dest, "CPF")

        natureza = _text(ide, "natOp", "") or ""
        cfops = []
        itens = []
        for det in dets:
            prod = det.find("prod")
            det.find("imposto")
            cfop = _text(prod, "CFOP", "")
            if cfop:
                cfops.append(cfop)
            item = {
                "sku": _text(prod, "cProd", None),
                "gtin": _text(prod, "cEAN", None) or _text(prod, "cEANTrib", None),
                "descricao": _text(prod, "xProd", "") or "",
                "ncm": _text(prod, "NCM", None),
                "cfop": cfop,
                "cst_icms": None,
                "cst_pis": None,
                "cst_cofins": None,
                "quantidade": float(_text(prod, "qCom", "0") or 0),
                "valor_unitario": float(_text(prod, "vUnCom", "0") or 0),
                "valor_total": float(_text(prod, "vProd", "0") or 0),
                "desconto": float(_text(prod, "vDesc", "0") or 0),
                "aliquotas": {},
            }
            itens.append(item)

        totais = {
            "valor_produtos": float(_text(total, "vProd", "0") or 0),
            "descontos": float(_text(total, "vDesc", "0") or 0),
            "frete": float(_text(total, "vFrete", "0") or 0),
            "outras_despesas": float(_text(total, "vOutro", "0") or 0),
            "base_icms": float(_text(total, "vBC", "0") or 0),
            "icms": float(_text(total, "vICMS", "0") or 0),
            "ipi": float(_text(total, "vIPI", "0") or 0),
            "pis": float(_text(total, "vPIS", "0") or 0),
            "cofins": float(_text(total, "vCOFINS", "0") or 0),
            "valor_total_nfe": float(_text(total, "vNF", "0") or 0),
        }

        nota = {
            "id_unico": chave or hashlib.sha1(f"{emit_doc}|{dest_doc}|{numero}|{serie}|{dt.date()}".encode()).hexdigest(),
            "modelo": "NFe",
            "chave": chave,
            "numero": numero,
            "serie": serie,
            "data_emissao": dt.isoformat(),
            "mes_competencia": _mk_mes_comp(dt),
            "emitente": {
                "documento": emit_doc,
                "razao_social": _text(emit, "xNome", ""),
                "uf": _text(emit, "enderEmit/UF", ""),
                "municipio": _text(emit, "enderEmit/xMun", ""),
                "inscricao_estadual": _text(emit, "IE", None),
            },
            "destinatario": {
                "documento": dest_doc,
                "razao_social": _text(dest, "xNome", ""),
                "uf": _text(dest, "enderDest/UF", ""),
                "municipio": _text(dest, "enderDest/xMun", ""),
                "inscricao_estadual": _text(dest, "IE", None),
            },
            "natureza_operacao": natureza,
            "cfops": sorted(set(cfops)),
            "itens": itens,
            "totais": totais,
            "regiao": regiao,
            "market": market,
            "tipo_documento": None,  # opcional inferir por emitente/destinatario
            "status_parse": "ok",
            "origem_arquivo": origem_arquivo,
        }
        return nota
    except Exception as e:
        return {
            "id_unico": hashlib.sha1(xml_bytes[:512]).hexdigest(),
            "modelo": "NFe",
            "chave": None,
            "numero": "",
            "serie": "",
            "data_emissao": datetime.now(timezone.utc).isoformat(),
            "mes_competencia": _mk_mes_comp(datetime.now(timezone.utc)),
            "emitente": {},
            "destinatario": {},
            "natureza_operacao": "",
            "cfops": [],
            "itens": [],
            "totais": {k: 0.0 for k in [
                "valor_produtos","descontos","frete","outras_despesas",
                "base_icms","icms","ipi","pis","cofins","valor_total_nfe"
            ]},
            "regiao": regiao,
            "market": market,
            "tipo_documento": None,
            "status_parse": "error",
            "mensagem_erro": str(e),
            "origem_arquivo": origem_arquivo,
        }

def parse_xml_nfse(xml_bytes: bytes, *, regiao: str, market: str, origem_arquivo: str) -> Dict[str, Any]:
    """
    Parser placeholder para NFSe — estruturas variam por prefeitura.
    Por ora, marcamos como não suportado para evoluir com amostras reais.
    """
    return {
        "id_unico": None,
        "modelo": "NFSe",
        "status_parse": "warning",
        "mensagem_erro": "Parser NFSe não implementado ainda.",
        "regiao": regiao,
        "market": market,
        "origem_arquivo": origem_arquivo,
        "cfops": [],
        "itens": [],
        "totais": {k: 0.0 for k in [
            "valor_produtos","descontos","frete","outras_despesas",
            "base_icms","icms","ipi","pis","cofins","valor_total_nfe"
        ]},
    }
