import duckdb
import streamlit as st

def get_connection():
    try:
       
        return duckdb.connect('hunter_leads.db', read_only=True)
    except Exception as e:
        st.error(f"Erro ao conectar no banco: {e}")
        return None