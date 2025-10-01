# app/utils/billing/__init__.py

# Fachada leve: exponha apenas o que está implementado
from .excel.service import consolidar_excel

# Os serviços da trilha XML podem não estar todos prontos; importe de forma segura
try:
    from .xml.service import carregar_e_normalizar, agregar_metricas  # se existir
except Exception:
    carregar_e_normalizar = None  # opcional: mantenha nomes para type hints
    agregar_metricas = None

__all__ = [
    "consolidar_excel",
    "carregar_e_normalizar",
    "agregar_metricas",
]
