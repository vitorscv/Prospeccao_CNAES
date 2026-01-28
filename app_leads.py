import streamlit as st
import duckdb
import pandas as pd

# Configuração da Página (Modo Tela Cheia)
st.set_page_config(page_title="Prospecção Pantex", page_icon="🏹", layout="wide")

# Estilo Personalizado (Botão Vermelho Pantex e Tabelas maiores)
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
    }
    div[data-testid="stDataFrame"] {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏹 Sistema de Prospecção Pantex")
st.markdown("### Ferramenta de Geração de Leads Qualificados")

# --- 1. CONEXÃO COM O BANCO ---
def get_connection():
    try:
        # read_only=True é vital para não travar o banco
        return duckdb.connect('hunter_leads.db', read_only=True)
    except Exception as e:
        st.error(f"Erro ao conectar no banco de dados. Verifique se o arquivo 'hunter_leads.db' existe.\nErro: {e}")
        return None

# --- 2. BUSCA DE CÓDIGO CNAE ---
st.info("Passo 1: Descubra o código da atividade econômica")
termo_busca = st.text_input("Digite a atividade (ex: Arroz, Gesso, Padaria, Construção):", placeholder="Digite aqui...")

if termo_busca:
    con = get_connection()
    if con:
        # Busca inteligente (ILIKE ignora maiúsculas/minúsculas)
        query = f"""
            SELECT codigo, descricao 
            FROM cnaes 
            WHERE descricao ILIKE '%{termo_busca}%' 
            LIMIT 15
        """
        results = con.execute(query).df()
        con.close()
        
        if not results.empty:
            st.dataframe(results, hide_index=True, use_container_width=True)
        else:
            st.warning("Nenhum CNAE encontrado. Tente um termo mais genérico.")

st.markdown("---")

# --- 3. GERAR LEADS (AGORA COM EMAIL E TELEFONE 2) ---
st.info("Passo 2: Gere a lista de contatos completa")

col1, col2 = st.columns(2)

with col1:
    estado = st.selectbox("Selecione o Estado Alvo:", 
                          ["BA", "SP", "RJ", "MG", "RS", "SC", "PR", "PE", "CE", "GO", "ES", "SE", "AL", "PB", "RN", "MA", "PI", "PA", "AM", "MT", "MS", "DF"])

with col2:
    codigo_cnae = st.text_input("Cole o Código CNAE (Apenas números):", placeholder="Ex: 0111301")

if st.button("🚀 GERAR LISTA DE PROSPECÇÃO"):
    if len(codigo_cnae) < 7:
        st.error(" O código CNAE deve ter 7 dígitos numéricos.")
    else:
        con = get_connection()
        if con:
            with st.spinner(f" Minérando dados da Receita Federal para {estado}..."):
                try:
                    # AQUI É O PULO DO GATO: Trazendo E-mail e Telefone Secundário
                    query_leads = f"""
                        SELECT 
                            nome_fantasia AS "Nome Fantasia",
                            cnpj_basico || cnpj_ordem || cnpj_dv AS "CNPJ",
                            ddd_1 || ' ' || telefone_1 AS "Telefone Principal",
                            ddd_2 || ' ' || telefone_2 AS "Telefone Secundário",
                            correio_eletronico AS "E-mail",
                            tipo_logradouro || ' ' || logradouro || ', ' || numero || ' ' || complemento AS "Endereço",
                            bairro AS "Bairro",
                            municipio AS "Cidade",
                            uf AS "UF"
                        FROM estabelecimentos 
                        WHERE cnae_principal = '{codigo_cnae}' 
                        AND uf = '{estado}'
                        AND situacao_cadastral = '02' -- Filtra apenas empresas ATIVAS
                        LIMIT 500
                    """
                    
                    df_leads = con.execute(query_leads).df()
                    con.close()
                    
                    if not df_leads.empty:
                        total = len(df_leads)
                        st.success(f" Sucesso! Encontramos {total} empresas ativas.")
                        
                        # Mostra a tabela na tela
                        st.dataframe(df_leads, hide_index=True, use_container_width=True)
                        
                        # Botão de Download Turbinado
                        csv = df_leads.to_csv(index=False, sep=';', encoding='utf-8-sig') # utf-8-sig para abrir certo no Excel
                        st.download_button(
                            label="📥 BAIXAR PLANILHA PARA EXCEL (.csv)",
                            data=csv,
                            file_name=f"Leads_CNAE_{codigo_cnae}_{estado}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning(" Nenhuma empresa ativa encontrada com este filtro. Tente outro Estado ou CNAE.")
                
                except Exception as e:
                    st.error(f"Erro na extração: {e}")