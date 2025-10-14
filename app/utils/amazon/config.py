#C:\Apps\Datahive\app\utils\amazon\config.py

import os

API_BASE_URL = os.getenv("AMZ_API_BASE_URL", "https://sellingpartnerapi-na.amazon.com")
MARKETPLACE_ID_BR = os.getenv("AMZ_MARKETPLACE_ID_BR", "A2Q3Y263D00KWC")
LWA_CLIENT_ID = os.getenv("AMZ_LWA_CLIENT_ID", "")
LWA_CLIENT_SECRET = os.getenv("AMZ_LWA_CLIENT_SECRET", "")
LWA_REFRESH_TOKEN_BR = os.getenv("AMZ_LWA_REFRESH_TOKEN_BR", "")
USER_AGENT = os.getenv("AMZ_APP_USER_AGENT", "Datahive/1.0 (lang=python)")
