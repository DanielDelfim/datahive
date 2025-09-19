# scripts/reposicao/gerar_latest.py  (opcional, só se você quiser rodar via PowerShell)
from app.utils.reposicao.service import estimativa_por_mlb, escrever_latest

def main():
    for loja in ("mg", "sp"):
        registros = estimativa_por_mlb(loja, "7d", target_dias=15, estoque_seguranca=0)
        path = escrever_latest(loja, "7d", registros)
        print(f"OK: {loja.upper()} → {path}")

if __name__ == "__main__":
    main()
