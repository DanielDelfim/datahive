from __future__ import annotations
import streamlit as st
from datetime import date
from typing import Optional
from app.config.paths import Regiao

def ano_mes_defaults():
    t = date.today()
    return t.year, t.month

def select_regiao(label_key: str, label: str = "Região") -> Optional[Regiao]:
    reg_names = [r.name for r in Regiao]
    choice = st.selectbox(label, options=["(sem)"] + reg_names, key=label_key)
    return None if choice == "(sem)" else Regiao[choice]

def modo_operacao(label_key: str, default: str = "todos") -> str:
    options = ["vendas", "transferencias", "outros", "todos"]
    idx = options.index(default) if default in options else 0
    return st.selectbox("Tipo de operação", options, index=idx, key=label_key)
