# fachada leve: exports das duas trilhas
from app.utils.billing.excel.service import consolidar_excel
from app.utils.billing.xml.service import carregar_e_normalizar, agregar_metricas

__all__ = [
    "consolidar_excel",
    "carregar_e_normalizar",
    "agregar_metricas",
]
