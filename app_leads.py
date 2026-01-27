import streamlit as st
import duckdb
import pandas as pd

# Configuração da página
st.set_page_config(page_title="Hunter Leads - Pantex", page_icon="🏹", layout="wide")

st.title("🏹 Sistema de Prospecção Pantex")
st.markdown("---")

# Conexão com o Banco de Dados (Modo Leitura)
try:
    con = duckdb.connect(database='hunter_leads.db', read_only=True)
except Exception as e:
    st.error(f"Erro ao conectar no banco de dados: {e}")
    st.stop()

# --- SEÇÃO 1: DESCOBRIR O CÓDIGO CNAE ---
st.subheader("1️⃣ Encontre o código da atividade")
termo_busca = st.text_input("Digite o nome da atividade para descobrir o código (ex: Gesso, Construção, Padaria)")

if termo_busca:
    # Busca na tabela 'cnaes' que criamos
    query_cnae = f"SELECT codigo, descricao FROM cnaes WHERE descricao ILIKE '%{termo_busca}%' LIMIT 20"
    df_cnaes = con.execute(query_cnae).df()
    
    if not df_cnaes.empty:
        st.dataframe(df_cnaes, hide_index=True, use_container_width=True)
        st.info("💡 Copie o código numérico (coluna 'codigo') para usar no filtro abaixo.")
    else:
        st.warning("Nenhum CNAE encontrado com esse nome.")

st.markdown("---")

# --- SEÇÃO 2: GERAR LISTA DE LEADS ---
st.subheader("2️⃣ Gerar Lista de Leads")

col1, col2 = st.columns(2)

with col1:
    uf_selecionada = st.selectbox(
        "Selecione o Estado", 
        ["BA", "SP", "RJ", "MG", "RS", "PR", "SC", "PE", "CE", "GO", "ES"]
    )

with col2:
    cnae_input = st.text_input("Cole o Código CNAE aqui (Apenas números)", placeholder="Ex: 4744099")

# Botão de Ação
if st.button("🚀 GERAR LISTA AGORA"):
    if not cnae_input:
        st.error("⚠️ Você precisa digitar um código CNAE antes de buscar.")
    else:
        st.info(f"🔍 Buscando empresas de CNAE **{cnae_input}** na **{uf_selecionada}**...")
        
        try:
            # A Query que busca os dados reais na tabela 'estabelecimentos'
            query_leads = f"""
                SELECT 
                    nome_fantasia, 
                    cnpj, 
                    telefone, 
                    email, 
                    municipio, 
                    uf 
                FROM estabelecimentos 
                WHERE uf = '{uf_selecionada}' 
                AND cnae_principal = '{cnae_input}'
                LIMIT 1000
            """
            
            df_leads = con.execute(query_leads).df()
            
            if len(df_leads) > 0:
                st.success(f"✅ Encontramos **{len(df_leads)}** potenciais clientes!")
                st.dataframe(df_leads, use_container_width=True)
                
                # Botão de Download
                csv = df_leads.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Baixar Planilha (CSV)",
                    data=csv,
                    file_name=f"Leads_Pantex_{cnae_input}_{uf_selecionada}.csv",
                    mime="text/csv",
                )
            else:
                st.warning("😕 Nenhuma empresa encontrada com este filtro exato.")
                
        except Exception as e:
            st.error(f"Erro na busca: {e}")

# Fecha a conexão ao encerrar o script (boa prática)
# O Streamlit roda o script inteiro a cada interação, o DuckDB gerencia isso bem.