import streamlit as st
from src.database.repository import buscar_empresas_dto, buscar_cnae_por_texto, listar_cidades_do_banco, buscar_top_cidades
from src.services.excel_service import gerar_excel_de_dtos

#  CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Hunter Leads", layout="wide", page_icon="🏹")

# CSS 
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
# BARRA LATERAL 
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/107/107799.png", width=100)
    st.header("Filtros de Busca")
    
    # LISTA ESTADOS
    lista_estados = [
        "BRASIL", "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", 
        "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", 
        "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
    ]
    estado = st.selectbox("Estado Alvo:", lista_estados)
    
    # LÓGICA DA CIDADE 
    cidade = "TODAS"
    if estado != "BRASIL":
        
        lista_cidades = listar_cidades_do_banco(estado)
        cidade = st.selectbox(f"Cidades de {estado}:", ["TODAS"] + lista_cidades)

    cnae_input = st.text_input("Cole os Códigos CNAE:", "4711302")
    st.caption("Separe por vírgula. Ex: 4711302, 4729699")
    
    st.divider()
    clicou_buscar = st.button(" GERAR LISTA DE PROSPECÇÃO")

    st.caption(f"ℹ️ Limite de segurança: 50.000 resultados")
    
    with st.expander("⚠️ Ler sobre o Limite e Riscos"):
        st.warning("""
        **Por segurança, o sistema traz no máximo 50.000 empresas.**
        
        Se precisar de mais, você pode alterar o `LIMIT` no código, mas tenha cuidado:
        
        * **Acima de 100k:** Pode travar o navegador ao tentar exibir a tabela.
        * **Acima de 500k:** Pode estourar a memória RAM (16GB) e fechar o programa.
        
        *Recomendação:* Mantenha em 50k e use filtros de Cidade ou CNAE para segmentar melhor.
        """)

# AREA PRINCIPAL 
st.title("🏹 Hunter Leads - Pantex")

# ABAS 
aba1, aba2, aba3 = st.tabs(["🔍 Descobrir Código", "📊 Gerar Leads", "📈 Dashboard"])

# ABA 1: DESCOBRIR CNAE 
with aba1:
    st.header("Encontre o código da atividade")
    st.info("Passo 1: Digite o nome da atividade para descobrir o código.")
    termo_busca = st.text_input("Digite a atividade (ex: Arroz, Gesso, Padaria):")

    if termo_busca:
        df_cnaes = buscar_cnae_por_texto(termo_busca)
        if df_cnaes is not None and not df_cnaes.empty:
            st.dataframe(df_cnaes, hide_index=True, use_container_width=True)
            st.success("👆 Copie o código da coluna 'codigo' e cole na barra lateral.")
        else:
            st.warning("Nenhum CNAE encontrado.")

# ABA 2: RESULTADOS 
with aba2:
    st.header("Resultado da Busca")
    
    if clicou_buscar:
        lista_cnaes = [c.strip() for c in cnae_input.split(',') if c.strip()]
        
        if not lista_cnaes:
            st.warning("⚠️ Você esqueceu de colocar o CNAE na barra lateral!")
        else:
            with st.spinner("Minerando dados... Aguarde..."):
                resultados = buscar_empresas_dto(lista_cnaes, estado, cidade)
                
                if resultados:
                    st.success(f"✅ Sucesso! Encontramos {len(resultados)} empresas.")
                    
                    # Métricas
                    total = len(resultados)
                    com_email = sum(1 for r in resultados if r.email)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Total Encontrado", total)
                    c2.metric("Com E-mail", com_email)
                    c3.metric("Com Telefone", sum(1 for r in resultados if r.telefone_principal))
                    
                    # Tabela
                    st.dataframe([vars(r) for r in resultados], use_container_width=True, hide_index=True)
                    
                    # Download
                    excel_bytes = gerar_excel_de_dtos(resultados)
                    st.download_button(
                        label="📥 Baixar Planilha Formatada",
                        data=excel_bytes,
                        file_name="Leads_Hunter.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("Nenhum resultado encontrado.")

# --- ABA 3: DASHBOARD DE MERCADO ---
with aba3:
    st.header("📈 Inteligência de Mercado")
    st.info("Descubra onde estão as maiores concentrações de clientes para esse nicho.")

    # Usamos os filtros que já estão na barra lateral
    if st.button("📊 ANALISAR MERCADO AGORA"):
        
        # Limpeza básica dos CNAEs
        lista_cnaes = [c.strip() for c in cnae_input.split(',') if c.strip()]

        if not lista_cnaes:
            st.warning("⚠️ Digite pelo menos um CNAE na barra lateral esquerda.")
        else:
            with st.spinner(f"Analisando dados de {estado}..."):
                
                # CHAMA A FUNÇÃO NOVA DO REPOSITORY
                df_dash = buscar_top_cidades(lista_cnaes, estado)

                if df_dash is not None and not df_dash.empty:
                    # 1. Métricas de Resumo
                    total_top_10 = df_dash["Total"].sum()
                    maior_cidade = df_dash.iloc[0]["Cidade"]
                    
                    col1, col2 = st.columns(2)
                    col1.metric("Empresas no Top 10", total_top_10)
                    col2.metric("Maior Concentração", maior_cidade)
                    
                    st.divider()

                    # 2. O Gráfico de Barras
                    st.subheader(f"Top 10 Cidades em {estado}")
                    # Ajusta o índice para o nome da cidade aparecer no eixo X
                    st.bar_chart(df_dash.set_index("Cidade"), color="#ff4b4b") 
                    
                    # 3. Tabela detalhada (opcional)
                    with st.expander("Ver dados brutos da análise"):
                        st.dataframe(df_dash, use_container_width=True)
                        
                else:
                    st.warning("Não encontramos dados suficientes para gerar o gráfico com esses filtros.")