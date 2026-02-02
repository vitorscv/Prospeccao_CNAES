import duckdb
import streamlit as st

def get_connection():
    """
    Cria uma conexão com o banco DuckDB.
    Configura read_only=False para permitir criar tabelas e salvar CRM.
    """
    try:
        # Tenta conectar permitindo escrita
        con = duckdb.connect("hunter_leads.db", read_only=False)
        return con
    except Exception as e:
        st.error(f" Erro ao conectar no banco: {e}")
        st.warning("Dica: Verifique se o banco não está aberto em outro programa (DBeaver, terminal, etc).")
        return None