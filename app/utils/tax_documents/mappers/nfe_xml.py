from __future__ import annotations
from typing import Any, Dict, List
from xml.etree import ElementTree as ET

# Helpers seguros p/ namespaces variados
def T(elem, path):
    x = elem.find(path)
    return (x.text or "").strip() if x is not None and x.text else ""

def N(elem, path):
    v = T(elem, path)
    try:
        return float(v.replace(",", ".")) if v else 0.0
    except:  # noqa
        return 0.0
    
def cnpj_from_chave(chave: str) -> str:
    # Chave NFe: [UF(2)][AAMM(4)][CNPJ(14)][modelo(2)][serie(3)][nNF(9)]...
    s = "".join([c for c in chave if c.isdigit()])
    return s[6:20] if len(s) >= 20 else ""

def parse_nfe_xml_bytes(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Recebe um XML (bytes) da NF-e e retorna UMA lista de linhas (uma por <det> item),
    já flatten com cabeçalho + item.
    Suporta NFe procNFe e NFe pura.
    """
    root = ET.fromstring(xml_bytes)

    # tentativa de lidar com namespaces distintos
    # procuramos a tag NFe onde estiver
    nfe = root.find(".//{*}NFe")
    if nfe is None and root.tag.endswith("NFe"):
        nfe = root
    if nfe is None:
        return []

    infNFe = nfe.find(".//{*}infNFe")
    if infNFe is None:
        return []

    ide   = infNFe.find(".//{*}ide")
    emit  = infNFe.find(".//{*}emit")
    dest  = infNFe.find(".//{*}dest")
    total = infNFe.find(".//{*}total")
    transp= infNFe.find(".//{*}transp")
    infAdic = infNFe.find(".//{*}infAdic")

    # Cabeçalho
    chave = infNFe.attrib.get("Id","").replace("NFe","")
    cab = {
        "ID Nota": chave,
        "Serie": T(ide,".{*}serie"),
        "Numero Nota": T(ide,".{*}nNF"),
        "Data emissao": T(ide,".{*}dhEmi") or T(ide,".{*}dEmi"),
        "Data saída": T(ide,".{*}dhSaiEnt") or T(ide,".{*}dSaiEnt"),
        "Regime Tributario": T(emit,".{*}CRT"),
        "Natureza": T(ide,".{*}natOp"),
        "Observacoes": T(infAdic,".{*}infCpl"),
        "Chave de acesso": chave,
    }

    # Totais
    ICMSTot = total.find(".//{*}ICMSTot") if total is not None else None
    cab.update({
        "Base ICMS": N(ICMSTot,".{*}vBC") if ICMSTot is not None else 0.0,
        "Valor ICMS": N(ICMSTot,".{*}vICMS") if ICMSTot is not None else 0.0,
        "Base ICMS Subst": N(ICMSTot,".{*}vBCST") if ICMSTot is not None else 0.0,
        "Valor ICMS Subst": N(ICMSTot,".{*}vST") if ICMSTot is not None else 0.0,
        "Valor Servicos": N(ICMSTot,".{*}vServ") if ICMSTot is not None else 0.0,
        "Valor Produtos": N(ICMSTot,".{*}vProd") if ICMSTot is not None else 0.0,
        "Frete": N(ICMSTot,".{*}vFrete") if ICMSTot is not None else 0.0,
        "Seguro": N(ICMSTot,".{*}vSeg") if ICMSTot is not None else 0.0,
        "Outras Despesas": N(ICMSTot,".{*}vOutro") if ICMSTot is not None else 0.0,
        "Valor IPI": N(ICMSTot,".{*}vIPI") if ICMSTot is not None else 0.0,
        "Valor Nota": N(ICMSTot,".{*}vNF") if ICMSTot is not None else 0.0,
        "Desconto": N(ICMSTot,".{*}vDesc") if ICMSTot is not None else 0.0,
    })

    # Emitente/Destinatário (usaremos DEST como "Contato"/comprador)
    contato = dest if dest is not None else emit
    ender = contato.find(".//{*}enderDest") if contato is dest else contato.find(".//{*}enderEmit")
    cab.update({
        "Contato": T(contato,".{*}xNome"),
        "Fantasia": T(emit,".{*}xFant"),
        "CPF / CNPJ": T(contato,".{*}CNPJ") or T(contato,".{*}CPF"),
        "Municipio": T(ender,".{*}xMun") if ender is not None else "",
        "UF": T(ender,".{*}UF") if ender is not None else "",
        "Cep": T(ender,".{*}CEP") if ender is not None else "",
        "Endereco": T(ender,".{*}xLgr") if ender is not None else "",
        "Nro": T(ender,".{*}nro") if ender is not None else "",
        "Bairro": T(ender,".{*}xBairro") if ender is not None else "",
        "Complemento": T(ender,".{*}xCpl") if ender is not None else "",
        "E-mail": T(contato,".{*}email"),
        "Fone": T(contato,".{*}fone"),
        "Peso líquido": T(infNFe,".{*}transp/{*}vol/{*}pesoL"),
        "Peso bruto": T(infNFe,".{*}transp/{*}vol/{*}pesoB"),
        "Frete por conta": T(transp,".{*}modFrete") if transp is not None else "",
    })

    # Itens
    rows: List[Dict[str,Any]] = []
    for det in infNFe.findall(".//{*}det"):
        prod = det.find(".//{*}prod")
        imposto = det.find(".//{*}imposto")

        icms_tag = imposto.find(".//{*}ICMS/*") if imposto is not None else None
        csosn_ou_cst = T(icms_tag,".{*}CSOSN") or T(icms_tag,".{*}CST")

        simples_base = N(icms_tag,".{*}vBC")
        simples_imp  = N(icms_tag,".{*}vICMS")
        simples_base_calc = simples_base  # mantido por compat.

        st_imp = N(icms_tag,".{*}vICMSST")
        aliq_credito = N(icms_tag,".{*}pCredSN")
        val_credito  = N(icms_tag,".{*}vCredICMSSN")

        pis = imposto.find(".//{*}PIS/*") if imposto is not None else None
        cof = imposto.find(".//{*}COFINS/*") if imposto is not None else None
        ipi = imposto.find(".//{*}IPI/{*}IPITrib") if imposto is not None else None
        ii  = imposto.find(".//{*}II") if imposto is not None else None

        row = dict(cab)
        row.update({
            "CNPJ Emissor": (T(emit, ".{*}CNPJ") or cnpj_from_chave(cab.get("Chave de acesso",""))),
            "Item Descricao": T(prod,".{*}xProd"),
            "Item Codigo": T(prod,".{*}cProd"),
            "Item Quantidade": N(prod,".{*}qCom"),
            "Item UN": T(prod,".{*}uCom"),
            "Item Valor": N(prod,".{*}vUnCom"),
            "Item Total": N(prod,".{*}vProd"),
            "Item Frete": N(prod,".{*}vFrete"),
            "Item Seguro": N(prod,".{*}vSeg"),
            "Item Outras Despesas": N(prod,".{*}vOutro"),
            "Item Desconto": N(prod,".{*}vDesc"),
            "Item CFOP": T(prod,".{*}CFOP"),
            "Item NCM": T(prod,".{*}NCM"),
            "ST / CSOSN": csosn_ou_cst,
            "Valor Base Simples / ICMS": simples_base,
            "Valor Imposto Simples / ICMS": simples_imp,
            "Valor Base Calculo Simples / ICMS": simples_base_calc,
            "Valor Imposto ST / ICMS": st_imp,
            "Alíquota Crédito Simples": aliq_credito,
            "Valor Crédito Simples": val_credito,
            "Valor Base COFINS": N(cof,".{*}vBC") if cof is not None else 0.0,
            "Valor Imposto COFINS": N(cof,".{*}vCOFINS") if cof is not None else 0.0,
            "Valor Base PIS": N(pis,".{*}vBC") if pis is not None else 0.0,
            "Valor Imposto PIS": N(pis,".{*}vPIS") if pis is not None else 0.0,
            "Valor Base IPI": N(ipi,".{*}vBC") if ipi is not None else 0.0,
            "Valor Imposto IPI": N(ipi,".{*}vIPI") if ipi is not None else 0.0,
            "Valor Base II": N(ii,".{*}vBC") if ii is not None else 0.0,
            "Valor Imposto II": N(ii,".{*}vII") if ii is not None else 0.0,
            "Item Origem": T(icms_tag,".{*}orig"),
        })
        rows.append(row)

    return rows
