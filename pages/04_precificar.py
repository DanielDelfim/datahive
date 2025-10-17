# C:\Apps\Datahive\pages\04_precificar.py
from __future__ import annotations
import streamlit as st

# A página é apenas uma casca; toda a lógica/UI está no compositor.
from app.dashboard.precificar.compositor import render

def main():
    st.set_page_config(page_title="Precificação", page_icon="💸", layout="wide")
    render()

if __name__ == "__main__":
    main()


