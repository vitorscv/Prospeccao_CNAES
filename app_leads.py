import streamlit as st
import duckdb

# Configuração da página
st.set_page_config(page_title="HunterHardware - Prospecção", layout="wide")

st.title("🎯 Sistema de Prospecção Pantex")

# 1. Input de busca de CNAE
st.subheader("1️⃣ Encontre os códigos das atividades")
termo = st.text_input("Digite o ramo de atividade (ex: Construção, Alimentos, TI)")

if termo:
    # Aqui simulamos a busca (quando o banco terminar de baixar ele funcionará)
    st.info(f"Buscando CNAEs relacionados a: {termo}")
    # No futuro, aqui chamaremos a função buscar_cnae_por_termo(termo)

# 2. Formulário de Filtro
st.divider()
st.subheader("2️⃣ Configure os filtros de busca")

col1, col2, col3 = st.columns(3)

with col1:
    uf_selecionada = st.selectbox("Estado", ["BA", "SP", "MG", "RJ"])
    
with col2:
    # O multiselect permite escolher vários de uma vez
    cnaes_selecionados = st.multiselect(
        "CNAEs selecionados para a busca",
        ["2391601", "2391602", "6201501"], # Isso será preenchido dinamicamente depois
        default=["2391601"]
    )

with col3:
    cidade = st.text_input("Código da Cidade (Opcional)", help="Ex: 3545 para Feira de Santana")

if st.button("🚀 GERAR LISTA DE LEADS"):
    st.write("Conectando ao banco hunter_leads.db e extraindo...")
    # Aqui virá a lógica do DuckDB que fizemos antes