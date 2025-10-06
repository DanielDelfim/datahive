from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Union
import zipfile
import json
import hashlib
import time
import re

from app.config.paths import Stage, Camada, Regiao
from app.utils.core.result_sink.service import build_sink
from .config import raw_zip_dir, pp_json_path, COLUMNS

# --- constantes de classificação (com fallback se não estiverem no config) ---
try:
    from .config import (
        CSTAT_AUTORIZADA, CSTAT_CANCELADA, CSTAT_DENEGADA,
        EVT_CANCELAMENTO, EVT_CCE, EVT_EPEC, CFOPS_DEVOLUCAO
    )
except Exception:
    CSTAT_AUTORIZADA = {"100", "150"}
    CSTAT_CANCELADA  = {"101", "151"}
    CSTAT_DENEGADA   = {"110", "301", "302", "303"}
    EVT_CANCELAMENTO = "110111"
    EVT_CCE          = "110110"
    EVT_EPEC         = "110140"
    CFOPS_DEVOLUCAO  = {"1202","1203","1209","2202","2203","2209","5202","5203","5209","6202","6203","6209"}

# --- parsers ---
from .mappers.nfe_xml import parse_nfe_xml_bytes
try:
    from .mappers.evento_generico import parse_evento   # tpEvento/chNFe/cStat/dhEvento/nProt/xJust
except Exception:
    parse_evento = None  # opcional

try:
    from .mappers.inut_xml import parse_inutilizacao    # inutilização de numeração
except Exception:
    parse_inutilizacao = None  # opcional


# ----------------- utils internos -----------------
def _list_candidate_files(base: Path) -> Tuple[List[Path], List[Path]]:
    if not base or not base.exists():
        return [], []
    zips = sorted(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() == ".zip")
    xmls = sorted(p for p in base.rglob("*") if p.is_file() and p.suffix.lower() == ".xml")
    return list(zips), list(xmls)

_digits = re.compile(r"\D+")
def _digits_only(s: str) -> str:
    return _digits.sub("", s or "")

def _cnpj_from_chave(chave: str) -> str:
    d = _digits_only(chave)
    return d[6:20] if len(d) >= 20 else ""

def _infer_devolucao(cfop: str, nat: str) -> bool:
    cf = (cfop or "").strip()
    if cf in CFOPS_DEVOLUCAO:
        return True
    return "devolu" in (nat or "").casefold()


# ----------------- primeira fase: coleta de eventos/inutilizações -----------------
def _coletar_eventos_inutilizacoes(zips: List[Path], xmls: List[Path], debug: bool = False) -> Tuple[Dict[str, List[Dict[str, str]]], List[Dict[str, str]]]:
    """
    Retorna:
      eventos_por_chave: {chNFe: [evento, ...]}
      inutilizacoes:     [ {cStat, CNPJ, ano, serie, nNFIni, nNFFin, ...}, ...]
    """
    eventos: Dict[str, List[Dict[str, str]]] = {}
    inutil: List[Dict[str, str]] = []

    def _handle_xml_bytes(b: bytes):
        if parse_evento:
            try:
                ev = parse_evento(b)
                if ev and ev.get("chNFe"):
                    eventos.setdefault(ev["chNFe"], []).append(ev)
            except Exception as e:
                if debug:
                    print(f"[WARN] Falha parse evento: {e}")
        if parse_inutilizacao:
            try:
                iu = parse_inutilizacao(b)
                if iu:
                    inutil.append(iu)
            except Exception as e:
                if debug:
                    print(f"[WARN] Falha parse inutilização: {e}")

    for z in zips:
        try:
            with zipfile.ZipFile(z, "r") as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".xml"):
                        _handle_xml_bytes(zf.read(name))
        except zipfile.BadZipFile:
            if debug:
                print(f"[WARN] ZIP corrompido (eventos/inut): {z}")

    for x in xmls:
        try:
            _handle_xml_bytes(x.read_bytes())
        except Exception as e:
            if debug:
                print(f"[WARN] Falha lendo XML solto (eventos/inut) {x}: {e}")

    # opcional: filtrar inutilizações homologadas (cStat == 102), se desejar num artefato à parte
    return eventos, inutil


# ----------------- API: carregar linhas já enriquecidas -----------------
def carregar_linhas(provider: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]] = None, *, debug: bool = False) -> List[Dict[str, Any]]:
    base = raw_zip_dir(provider, ano, mes, regiao)
    if debug:
        print(f"[DEBUG] Base de leitura: {base}")
    zips, xmls = _list_candidate_files(base)
    if debug:
        print(f"[DEBUG] Arquivos encontrados → ZIPs: {len(zips)} | XMLs soltos: {len(xmls)}")

    # 1) coletar eventos/inutilizações
    eventos_by_key, inutilizacoes = _coletar_eventos_inutilizacoes(zips, xmls, debug=debug)
    if debug:
        # resumo mínimo
        ev_count = sum(len(v) for v in eventos_by_key.values())
        print(f"[DEBUG] Eventos coletados: {ev_count} (para {len(eventos_by_key)} chaves) | Inutilizações: {len(inutilizacoes)}")

    rows: List[Dict[str, Any]] = []

    # 2) parse de NFe e enriquecimento linha-a-linha
    def _process_xml_bytes(xml_bytes: bytes, src: Optional[str] = None):
        try:
            item_rows = parse_nfe_xml_bytes(xml_bytes) or []
        except Exception as e:
            if debug:
                print(f"[WARN] Falha parse NFe ({src or 'xml'}): {e}")
            return

        for r in item_rows:
            chave = (r.get("Chave de acesso") or r.get("ID Nota") or "").strip()

            # CNPJ Emissor: se veio vazio do mapper, tenta fallback pela chave
            cnpj = (r.get("CNPJ Emissor") or "").strip()
            if not cnpj:
                cnpj = _cnpj_from_chave(chave)
                if cnpj:
                    r["CNPJ Emissor"] = cnpj

            # situação padrão (protNFe cStat, se o mapper tiver deixado)
            cstat = (r.get("cStat_aut") or "").strip()
            if cstat in CSTAT_CANCELADA:
                r["Situacao NFe"] = "cancelada"
            elif cstat in CSTAT_DENEGADA:
                r["Situacao NFe"] = "denegada"
            elif cstat in CSTAT_AUTORIZADA:
                r["Situacao NFe"] = "autorizada"
            else:
                r.setdefault("Situacao NFe", "autorizada")

            # eventos: sobrepõem/registram
            for ev in eventos_by_key.get(chave, []):
                tp, ev_stat = ev.get("tpEvento"), ev.get("cStat")
                if tp == EVT_CANCELAMENTO and ev_stat in {"135", "155"}:
                    r["Situacao NFe"] = "cancelada"
                    r["Cancelada em"] = ev.get("dhEvento", "")
                    r["Prot Cancel"] = ev.get("nProt", "")
                    r["Justificativa Cancel"] = ev.get("xJust", "")
                elif tp == EVT_CCE and ev_stat in {"135", "136"}:
                    r["Possui CC-e"] = True
                elif tp == EVT_EPEC:
                    r["Em Contingencia"] = True

            # devolução por CFOP/natureza
            if _infer_devolucao(str(r.get("Item CFOP", "")), str(r.get("Natureza", ""))):
                r["Eh Devolucao"] = True

            rows.append(r)

    # processa ZIPs
    for zpath in zips:
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                members = [n for n in zf.namelist() if n.lower().endswith(".xml")]
                if debug:
                    print(f"[DEBUG] ZIP {zpath.name}: {len(members)} XML(s)")
                for name in members:
                    _process_xml_bytes(zf.read(name), src=f"{zpath.name}:{name}")
        except zipfile.BadZipFile:
            if debug:
                print(f"[WARN] ZIP corrompido: {zpath}")

    # processa XMLs soltos
    for x in xmls:
        try:
            _process_xml_bytes(x.read_bytes(), src=str(x))
        except Exception as e:
            if debug:
                print(f"[WARN] Falha lendo XML solto {x}: {e}")

    rows.sort(key=lambda r: (r.get("ID Nota", ""), r.get("Item Codigo", ""), r.get("Item Descricao", "")))
    if debug:
        print(f"[DEBUG] Linhas extraídas: {len(rows)}")
    return rows


# ----------------- meta + gravação -----------------
def _meta(payload_rows: List[Dict[str, Any]], *, provider: str, ano: int, mes: int, regiao, script, schema_v="1.0.0") -> Dict[str, Any]:
    ordered = json.dumps(payload_rows, ensure_ascii=False, sort_keys=True).encode()
    return {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage": getattr(Stage, "DEV", "dev").value if hasattr(Stage, "DEV") else "dev",
        "marketplace": provider.lower(),
        "regiao": (regiao.value if isinstance(regiao, Regiao) else (regiao or "")),
        "camada": Camada.PP.value,
        "schema_version": schema_v,
        "script_name": script,
        "script_version": "1.0.0",
        "source_paths": [],
        "row_count": len(payload_rows),
        "hash": hashlib.sha256(ordered).hexdigest(),
        "competencia": f"{ano:04d}-{mes:02d}",
    }

def gravar_pp(provider: str, ano: int, mes: int, regiao: Optional[Union[Regiao, str]], rows: List[Dict[str, Any]], *, dry_run: bool, debug: bool, sink_kind: str = "json_file") -> str:
    if len(rows) == 0:
        base = raw_zip_dir(provider, ano, mes, regiao)
        zips, xmls = _list_candidate_files(base)
        raise ValueError(
            "DQ: nenhum item encontrado.\n"
            f"→ Base verificada: {base}\n"
            f"→ ZIPs: {len(zips)} | XMLs soltos: {len(xmls)}"
        )

    # ⚠️ Só o que estiver em COLUMNS vai para o JSON!
    norm = [{col: r.get(col, "") for col in COLUMNS} for r in rows]

    payload = {"_meta": {}, "rows": norm}
    payload["_meta"] = _meta(norm, provider=provider, ano=ano, mes=mes, regiao=regiao, script="agregar_pp.py")
    payload["_meta"]["source_paths"] = [str(raw_zip_dir(provider, ano, mes, regiao))]

    target_json = pp_json_path(provider, ano, mes, regiao)
    sink = build_sink(sink_kind, target_path=target_json, do_backup=True, pretty=True)
    sink.write(payload, dry_run=dry_run, debug=debug)
    if debug:
        print(f"[INFO] Gravado JSON: {target_json}")
    return str(target_json)
