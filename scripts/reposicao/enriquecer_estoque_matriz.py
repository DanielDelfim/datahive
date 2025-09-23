# scripts/reposicao/enriquecer_estoque_matriz.py
from collections import defaultdict
from app.utils.estoques_matriz_filial.service import get_estoque_pp_mg  # leitura PP normalizada :contentReference[oaicite:32]{index=32}
from app.utils.reposicao.config import RESULTS_DIR  # :contentReference[oaicite:33]{index=33}
from app.utils.reposicao.service import salvar_json_atomic  # :contentReference[oaicite:34]{index=34}

def main():
    rows = get_estoque_pp_mg()
    acc = defaultdict(float)
    for r in rows:
        e = str(r.get("ean", "")).strip()
        if not e:
            continue
        try:
            acc[e] += float(r.get("quantidade") or 0)
        except Exception:
            pass

    # opcional: materializa um mapa auxiliar para auditoria
    dest = RESULTS_DIR() / "estoque_matriz_map.json"
    salvar_json_atomic({"items": acc}, dest)
    print(f"[ok] escrito {dest}")

if __name__ == "__main__":
    main()
