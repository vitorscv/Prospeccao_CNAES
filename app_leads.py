import streamlit as st
import duckdb
import pandas as pd

# ==========================================
# 1. CONFIGURAÇÃO E ESTILO
# ==========================================
st.set_page_config(page_title="Hunter Leads", page_icon="🏹", layout="wide")

st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #FF4B4B;
        color: white;
        font-weight: bold;
        border-radius: 10px;
    }
    div[data-testid="stDataFrame"] {
        width: 100%;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏹 Hunter Leads - Pantex")

# ==========================================
# 2. FUNÇÃO DE CONEXÃO
# ==========================================
def get_connection():
    try:
        return duckdb.connect('hunter_leads.db', read_only=True)
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return None

# ==========================================
# 3. BARRA LATERAL (FILTROS)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2518/2518048.png", width=100)
    st.header("Filtros de Busca")
    
    estado = st.selectbox("Selecione o Estado Alvo:", 
                          ["BA", "SP", "RJ", "MG", "RS", "SC", "PR", "PE", "CE", "GO", "ES", "SE", "AL", "PB", "RN", "MA", "PI", "PA", "AM", "MT", "MS", "DF"])
    
    codigo_cnae = st.text_input("Cole o Código CNAE:", placeholder="Ex: 0111301")
    
    st.markdown("---")
    
    # Variável que guarda o clique do botão
    clicou_buscar = st.button("🚀 GERAR LISTA DE PROSPECÇÃO")

# ==========================================
# 4. ÁREA PRINCIPAL (ABAS)
# ==========================================
# As abas ficam FORA do sidebar para ocupar a tela toda
aba1, aba2, aba3 = st.tabs(["🔍 Descobrir Código", "📊 Gerar Leads", "📈 Dashboard"])

# --- ABA 1: Descobrir o CNAE ---
with aba1:
    st.header("Encontre o código da atividade")
    st.info("Passo 1: Digite o nome da atividade para descobrir o código.")
    
    termo_busca = st.text_input("Digite a atividade (ex: Arroz, Gesso, Padaria):")

    if termo_busca:
        con = get_connection()
        if con:
            # Query simples para achar o código
            query = f"SELECT codigo, descricao FROM cnaes WHERE descricao ILIKE '%{termo_busca}%' LIMIT 15"
            results = con.execute(query).df()
            con.close()
            
            if not results.empty:
                st.dataframe(results, hide_index=True, use_container_width=True)
            else:
                st.warning("Nenhum CNAE encontrado.")

# --- ABA 2: Gerar Leads (Ouro) ---
with aba2:
    st.header("Base de Empresas")
    
    # Só executa se o botão lá da esquerda foi clicado
    if clicou_buscar:
        if len(codigo_cnae) < 7:
            st.error("⚠️ O código CNAE deve ter 7 dígitos numéricos.")
        else:
            con = get_connection()
            if con:
                with st.spinner(f"Minerando dados para {estado}..."):
                    try:
                        # Query Poderosa (CNAE + Estado + Contatos)
                        query_leads = f"""
                            SELECT 
                                nome_fantasia AS "Nome Fantasia",
                                cnpj_basico || cnpj_ordem || cnpj_dv AS "CNPJ",
                                ddd_1 || ' ' || telefone_1 AS "Telefone Principal",
                                ddd_2 || ' ' || telefone_2 AS "Telefone Secundário",
                                correio_eletronico AS "E-mail",
                                municipio AS "Cidade",
                                uf AS "UF"
                            FROM estabelecimentos 
                            WHERE cnae_principal = '{codigo_cnae}' 
                            AND uf = '{estado}'
                            AND situacao_cadastral = '02'
                            LIMIT 1000
                        """
                        df_leads = con.execute(query_leads).df()
                        con.close()
                        
                        if not df_leads.empty:
                            st.success(f"✅ Sucesso! Encontramos {len(df_leads)} empresas ativas.")
                            
                            # --- MÉTRICAS ---
                            col1, col2, col3 = st.columns(3)
                            
                            col1.metric("Total Encontrado", len(df_leads))
                            
                            # Conta quantos tem email preenchido
                            qtd_email = df_leads[df_leads["E-mail"].notnull()].shape[0]
                            col2.metric("Com E-mail", qtd_email)
                            
                            # Conta quantos tem telefone secundário
                            qtd_tel2 = df_leads[df_leads["Telefone Secundário"].notnull()].shape[0]
                            col3.metric("Com Telefone Extra", qtd_tel2)
                            
                            st.divider()
                            # ----------------

                            # Tabela
                            st.dataframe(df_leads, hide_index=True, use_container_width=True)
                            
                            # Download
                            csv = df_leads.to_csv(index=False, sep=';', encoding='utf-8-sig')
                            st.download_button(
                                label="📥 BAIXAR PLANILHA",
                                data=csv,
                                file_name=f"Leads_{codigo_cnae}_{estado}.csv",
                                mime="text/csv"
                            )
                        else:
                            st.warning("Nenhuma empresa encontrada com esses filtros.")
                            
                    except Exception as e:
                        st.error(f"Erro na extração: {e}")

# --- ABA 3: Futuro ---
with aba3:
    st.info("🚧 Em breve: Gráficos e Estatísticas de Mercado")