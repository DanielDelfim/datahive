from __future__ import annotations
import os
import json
import sys
from pathlib import Path
from app.utils.amazon.client import AmazonSpApiClient

# load .env simples
root = Path(__file__).resolve().parents[3]
envp = root / ".env"
if envp.exists():
    for line in envp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))

# pegar credenciais que SERÃO usadas
def peek(k): 
    v = os.getenv(k)
    if not v:
        return None
    if "SECRET" in k or "TOKEN" in k:
        return (v[:6] + "..." + v[-4:])  # mascara
    return v

print("== ENV EM USO ==")
print("AMZ_LWA_CLIENT_ID:",  peek("AMZ_LWA_CLIENT_ID") or peek("SPAPI_CLIENT_ID"))
print("AMZ_LWA_CLIENT_SECRET:", peek("AMZ_LWA_CLIENT_SECRET") or peek("SPAPI_CLIENT_SECRET"))
print("AMZ_LWA_REFRESH_TOKEN_BR:", peek("AMZ_LWA_REFRESH_TOKEN_BR") or peek("SPAPI_REFRESH_TOKEN"))
print("AMZ_API_BASE_URL:", os.getenv("AMZ_API_BASE_URL") or os.getenv("SPAPI_BASE_URL"))
print("AMZ_MARKETPLACE_ID_BR:", os.getenv("AMZ_MARKETPLACE_ID_BR", "A2Q3Y263D00KWC"))
print("AMZ_SELLER_ID_BR:", os.getenv("AMZ_SELLER_ID_BR") or os.getenv("SPAPI_SELLER_ID") or os.getenv("AMAZON_SELLER_ID"))
# client
base_url = os.getenv("AMZ_API_BASE_URL") or os.getenv("SPAPI_BASE_URL") or "https://sellingpartnerapi-na.amazon.com"
client_id = os.getenv("AMZ_LWA_CLIENT_ID") or os.getenv("SPAPI_CLIENT_ID")
client_secret = os.getenv("AMZ_LWA_CLIENT_SECRET") or os.getenv("SPAPI_CLIENT_SECRET")
refresh_token = os.getenv("AMZ_LWA_REFRESH_TOKEN_BR") or os.getenv("SPAPI_REFRESH_TOKEN")
user_agent = os.getenv("AMZ_APP_USER_AGENT") or os.getenv("SPAPI_USER_AGENT") or "Datahive/1.0"
user_agent = os.getenv("AMZ_APP_USER_AGENT") or os.getenv("SPAPI_USER_AGENT") or "Datahive/1.0"

if not (client_id and client_secret and refresh_token):
    print("ERRO: faltam credenciais (client_id/secret/refresh_token).")
    sys.exit(2)

cli = AmazonSpApiClient(
    base_url=base_url, client_id=client_id, client_secret=client_secret,
    refresh_token=refresh_token, user_agent=user_agent
)

# teste Pricing (1 asin): GET /products/pricing/v0/items
asin = (sys.argv[1] if len(sys.argv)>1 else "B0FG3BMZ2Q")  # troque se quiser
mkt = os.getenv("AMZ_MARKETPLACE_ID_BR", "A2Q3Y263D00KWC")
params = {"MarketplaceId": mkt, "ItemType":"Asin", "ItemCondition":"New", "Asins": asin}

print("\n== CHAMADA PRICING ==")
print("GET /products/pricing/v0/items", params)
try:
    resp = cli.get("/products/pricing/v0/items", params=params)
    print("HTTP OK")
    print(json.dumps(resp, ensure_ascii=False)[:800])
    print("\nSTATUS: PASSOU ✅ (escopo product-pricing OK)")
    sys.exit(0)
except Exception as e:
    msg = str(e)
    print("HTTP ERROR:", msg)
    if "403" in msg or "Access to requested resource is denied" in msg:
        print("\nSTATUS: 403 ❌ — o access token atual NÃO tem escopo product-pricing.")
        print("Causas comuns: refresh_token antigo ou de outro cliente/app; reautorização na conta errada.")
    sys.exit(1)
