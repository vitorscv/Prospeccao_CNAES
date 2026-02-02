import streamlit as st
import pandas as pd
from src.database.repository import buscar_empresas_dto, buscar_cnae_por_texto, listar_cidades_do_banco, buscar_top_cidades 
from src.database.crm_repository import adicionar_lista_ao_crm
from src.services.excel_service import gerar_excel_de_dtos
from src.ui.tab_crm import render_tab_crm
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
aba1, aba2, aba3, aba4 = st.tabs([
    "🔍 Descobrir Código", 
    "📊 Gerar Leads ", 
    "💼 Meu Pipeline ", 
    "📈 Dashboard"
])

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
    
    # Inicializa session_state se não existir
    if 'resultados_busca' not in st.session_state:
        st.session_state.resultados_busca = None
    if 'filtros_busca' not in st.session_state:
        st.session_state.filtros_busca = None
    
    if clicou_buscar:
        lista_cnaes = [c.strip() for c in cnae_input.split(',') if c.strip()]
        
        if not lista_cnaes:
            st.warning("⚠️ Você esqueceu de colocar o CNAE na barra lateral!")
            st.session_state.resultados_busca = None
        else:
            with st.spinner("Minerando dados... Aguarde..."):
                resultados = buscar_empresas_dto(lista_cnaes, estado, cidade)
                # Salva os resultados no session_state
                st.session_state.resultados_busca = resultados
                st.session_state.filtros_busca = {
                    'lista_cnaes': lista_cnaes,
                    'estado': estado,
                    'cidade': cidade
                }
    
    # Usa os resultados do session_state se existirem
    resultados = st.session_state.resultados_busca
    
    if resultados:
        # --- PARTE A: MÉTRICAS (Igual antes) ---
        total = len(resultados)
        com_email = sum(1 for r in resultados if r.email)
        com_tel = sum(1 for r in resultados if r.telefone_principal)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("🏢 Total", total)
        c2.metric("📧 Com E-mail", com_email)
        c3.metric("📞 Com Telefone", com_tel)
        
        st.divider()

        # --- PARTE B: BOTÃO BAIXAR TUDO ---
        col_txt, col_btn = st.columns([3, 1])
        with col_txt:
            st.info("👇 Selecione as empresas na tabela para enviar ao CRM ou baixar separado.")
        with col_btn:
            excel_total = gerar_excel_de_dtos(resultados)
            st.download_button(
                label="📥 BAIXAR TUDO",
                data=excel_total,
                file_name="Lista_Completa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        # Botão para limpar resultados
        if st.button("🔄 Nova Busca", use_container_width=True):
            st.session_state.resultados_busca = None
            st.session_state.filtros_busca = None
            st.rerun()

        # --- PARTE C: TABELA COM CHECKBOX ---
        df_view = pd.DataFrame([vars(r) for r in resultados])
        
        # Filtra colunas visíveis
        cols = ['nome_fantasia', 'cnpj', 'cidade', 'telefone_principal', 'email']
        cols_finais = [c for c in cols if c in df_view.columns]

        evento = st.dataframe(
            df_view[cols_finais],
            use_container_width=True,
            hide_index=True,
            selection_mode="multi-row", # <--- O PULO DO GATO
            on_select="rerun",
            key="grid_principal"
        )
        
        # --- PARTE D: AÇÕES DOS SELECIONADOS ---
        indices = evento.selection.rows
        
        if indices:
            st.success(f"✅ **{len(indices)} empresas selecionadas.**")
            
            # Pega os dados dos selecionados
            lista_selecionados_dto = [resultados[i] for i in indices]
            lista_selecionados_dict = [vars(r) for r in lista_selecionados_dto]
            
            col_a, col_b = st.columns(2)
            
            # Botão 1: CRM
            with col_a:
                if st.button(" ENVIAR PARA CRM LEADS ", type="primary", use_container_width=True):
                    if adicionar_lista_ao_crm(lista_selecionados_dict):
                        st.toast("Enviado para o Pipeline!", icon="💼")
                    else:
                        st.error("Erro ao salvar.")
            
            # Botão 2: Baixar Selecionados
            with col_b:
                excel_parcial = gerar_excel_de_dtos(lista_selecionados_dto)
                st.download_button(
                    label="📊 BAIXAR SELECIONADOS",
                    data=excel_parcial,
                    file_name="Selecionados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

#ABA 3: pipeline
with aba3:
    render_tab_crm()

# --- ABA 4: DASHBOARD DE MERCADO ---
with aba4:
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