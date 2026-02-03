from src.ui.icons import Icons
import streamlit as st
import pandas as pd
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.error(" Plotly não está instalado. Execute: pip install plotly")
from src.database.repository import buscar_empresas_dto, buscar_cnae_por_texto, listar_cidades_do_banco, buscar_dados_dashboard_executivo, analise_pipeline 
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
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "🔍 Descobrir Código", 
    "📊 Gerar Leads ", 
    "💼 Meu Pipeline ", 
    "📈 Dashboard",
    "📊 Analytics Pipeline"
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
        c1.metric("🏢 Total de Empresas ", total)
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

# --- ABA 4: DASHBOARD EXECUTIVO ---
with aba4:
    st.header("📊 Dashboard Executivo - Inteligência de Mercado")
    st.caption("Análise estratégica de oportunidades e expansão territorial")
    st.info("💡 Use os filtros da barra lateral para personalizar a análise.")
    
    # Processa filtros da sidebar principal
    lista_cnaes_dash = [c.strip() for c in cnae_input.split(',') if c.strip()] if cnae_input else []
    lista_estados_filtro = None if estado == "BRASIL" else [estado]
    lista_cidades_filtro = None if cidade == "TODAS" else [cidade]
    
    # Busca dados usando os filtros da sidebar principal
    with st.spinner("🔍 Carregando dados do dashboard..."):
        dados_dash = buscar_dados_dashboard_executivo(
            lista_estados=lista_estados_filtro,
            lista_cidades=lista_cidades_filtro,
            lista_cnaes=lista_cnaes_dash if lista_cnaes_dash else None
        )
    
    if not dados_dash or dados_dash.get('kpis') is None or dados_dash['kpis'].empty:
        st.warning("⚠️ Nenhum dado encontrado com os filtros selecionados. Tente ajustar os filtros.")
    else:
        kpis = dados_dash['kpis'].iloc[0]
        
        # ========== LINHA 1: BIG NUMBERS / KPIs ==========
        st.markdown("---")
        st.markdown("### 📈 Indicadores Principais")
        
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
        
        total_empresas = int(kpis['total_empresas'])
        total_cidades = int(kpis['total_cidades'])
        total_estados = int(kpis['total_estados'])
        setor_pred = dados_dash.get('setor_predominante', 'N/A')
        
        col_kpi1.metric(
            "🏢 Total de Empresas Mapeadas",
            f"{total_empresas:,}",
            help="Total de empresas ativas encontradas"
        )
        col_kpi2.metric(
            "🗺️ Cobertura Geográfica",
            f"{total_cidades:,} cidades",
            delta=f"{total_estados} estados",
            help="Quantidade de cidades únicas com empresas"
        )
        col_kpi3.metric(
            "🏭 Setor Predominante",
            setor_pred[:30] + "..." if len(setor_pred) > 30 else setor_pred,
            help="CNAE com maior concentração de empresas"
        )
        col_kpi4.metric(
            "📊 Diversidade de Setores",
            f"{int(kpis['total_cnaes']):,} CNAEs",
            help="Quantidade de setores diferentes"
        )
        
        st.markdown("---")
        
        # ========== LINHA 2: MAPA GEOGRÁFICO ==========
        if dados_dash.get('mapa') is not None and not dados_dash['mapa'].empty:
            st.markdown("### 🗺️ Inteligência Geográfica - Distribuição de Oportunidades")
            
            df_mapa = dados_dash['mapa'].copy()
            
            # Coordenadas aproximadas por UF (centro do estado)
            coordenadas_uf = {
                'AC': (-9.0238, -70.8120), 'AL': (-9.5713, -36.7820), 'AP': (1.4144, -51.7865),
                'AM': (-4.2633, -65.2432), 'BA': (-12.9714, -38.5014), 'CE': (-3.7172, -38.5433),
                'DF': (-15.7942, -47.8822), 'ES': (-19.1834, -40.3089), 'GO': (-16.6864, -49.2643),
                'MA': (-2.5387, -44.2825), 'MT': (-15.6014, -56.0979), 'MS': (-20.7722, -54.7852),
                'MG': (-19.9167, -43.9345), 'PA': (-1.4558, -48.5044), 'PB': (-7.2400, -36.7820),
                'PR': (-25.4284, -49.2733), 'PE': (-8.0476, -34.8770), 'PI': (-5.0892, -42.8019),
                'RJ': (-22.9068, -43.1729), 'RN': (-5.7945, -35.2110), 'RS': (-30.0346, -51.2177),
                'RO': (-8.7612, -63.9039), 'RR': (1.4144, -61.4444), 'SC': (-27.2423, -50.2189),
                'SP': (-23.5505, -46.6333), 'SE': (-10.5741, -37.3857), 'TO': (-10.1753, -48.2982)
            }
            
            # Adiciona coordenadas aproximadas (centro da cidade baseado no estado)
            df_mapa['lat'] = df_mapa['uf'].map(lambda x: coordenadas_uf.get(x, (-14.2350, -51.9253))[0])
            df_mapa['lon'] = df_mapa['uf'].map(lambda x: coordenadas_uf.get(x, (-14.2350, -51.9253))[1])
            
            # Adiciona pequena variação para não sobrepor pontos
            import numpy as np
            np.random.seed(42)
            df_mapa['lat'] = df_mapa['lat'] + np.random.normal(0, 0.5, len(df_mapa))
            df_mapa['lon'] = df_mapa['lon'] + np.random.normal(0, 0.5, len(df_mapa))
            
            # Cria mapa scatter
            if not PLOTLY_AVAILABLE:
                st.error("Plotly não está disponível. Instale com: pip install plotly")
            else:
                fig_mapa = px.scatter_mapbox(
                df_mapa,
                lat='lat',
                lon='lon',
                size='quantidade',
                color='quantidade',
                hover_name='cidade',
                hover_data={'uf': True, 'quantidade': True, 'cnaes_diferentes': True, 'lat': False, 'lon': False},
                color_continuous_scale=px.colors.sequential.Viridis,
                size_max=50,
                zoom=4,
                height=500,
                mapbox_style="open-street-map",
                title="Densidade de Empresas por Região"
            )
                fig_mapa.update_layout(margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_mapa, use_container_width=True)
            
            with st.expander("📋 Ver dados do mapa"):
                st.dataframe(df_mapa[['cidade', 'uf', 'quantidade', 'cnaes_diferentes']], use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # ========== LINHA 3: ANÁLISE DE MERCADO ==========
        st.markdown("### 📊 Análise de Mercado")
        
        col_graf1, col_graf2 = st.columns(2)
        
        # Gráfico 1: Top 10 Cidades (Barras Horizontais)
        with col_graf1:
            if dados_dash.get('top10_cidades') is not None and not dados_dash['top10_cidades'].empty:
                st.markdown("#### 🏆 Top 10 Cidades com Maior Potencial")
                df_top10 = dados_dash['top10_cidades'].copy()
                
                # Gráfico de barras horizontais
                if not PLOTLY_AVAILABLE:
                    st.bar_chart(df_top10.set_index('cidade_uf')['total'])
                else:
                    fig_top10 = px.bar(
                    df_top10,
                    x='total',
                    y='cidade_uf',
                    orientation='h',
                    color='total',
                    color_continuous_scale='Reds',
                    labels={'total': 'Quantidade de Empresas', 'cidade_uf': 'Cidade'},
                    height=400
                )
                    fig_top10.update_layout(
                        showlegend=False,
                        yaxis={'categoryorder': 'total ascending'},
                        margin=dict(l=0, r=0, t=0, b=0)
                    )
                    st.plotly_chart(fig_top10, use_container_width=True)
            else:
                st.info("Sem dados suficientes para Top 10")
        
        # Gráfico 2: Distribuição por CNAE/Setor (Treemap ou Donut)
        with col_graf2:
            if dados_dash.get('distribuicao_cnae') is not None and not dados_dash['distribuicao_cnae'].empty:
                st.markdown("#### 🏭 Distribuição por Setor (CNAE)")
                df_cnae = dados_dash['distribuicao_cnae'].copy()
                
                # Treemap
                if not PLOTLY_AVAILABLE:
                    st.bar_chart(df_cnae.set_index('setor')['total'])
                else:
                    fig_treemap = px.treemap(
                    df_cnae,
                    path=['setor'],
                    values='total',
                    color='total',
                    color_continuous_scale='Blues',
                    height=400
                )
                    fig_treemap.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig_treemap, use_container_width=True)
                
                # Tabela resumida
                with st.expander("📋 Ver distribuição completa"):
                    st.dataframe(df_cnae, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados suficientes para distribuição por setor")
        
        st.markdown("---")
        
        # ========== LINHA 4: DISTRIBUIÇÃO POR ESTADO ==========
        if dados_dash.get('distribuicao_uf') is not None and not dados_dash['distribuicao_uf'].empty:
            st.markdown("### 📍 Distribuição por Estado")
            df_uf = dados_dash['distribuicao_uf'].copy()
            
            # Gráfico de barras
            if not PLOTLY_AVAILABLE:
                st.bar_chart(df_uf.set_index('uf')['total'])
            else:
                fig_uf = px.bar(
                df_uf,
                x='uf',
                y='total',
                color='total',
                color_continuous_scale='Greens',
                labels={'uf': 'Estado (UF)', 'total': 'Quantidade de Empresas'},
                height=400
            )
                fig_uf.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_uf, use_container_width=True)
            
            # Tabela
            col_tab1, col_tab2 = st.columns([2, 1])
            with col_tab1:
                st.dataframe(df_uf, use_container_width=True, hide_index=True)
            with col_tab2:
                # Estatísticas rápidas
                st.metric("Estado Líder", df_uf.iloc[0]['uf'] if not df_uf.empty else "N/A")
                st.metric("Maior Concentração", f"{int(df_uf.iloc[0]['total']):,}" if not df_uf.empty else "0")
                if not df_uf.empty:
                    percentual_lider = (df_uf.iloc[0]['total'] / df_uf['total'].sum() * 100)
                    st.metric("Participação do Líder", f"{percentual_lider:.1f}%")

# --- ABA 5: ANALYTICS PIPELINE ---
with aba5:
    st.header("📊 Analytics do Pipeline")
    st.caption("Análise avançada e insights sobre seu pipeline de vendas")
    
    # Carrega dados automaticamente ao abrir a aba
    if 'analises_pipe_cache' not in st.session_state:
        with st.spinner("🔍 Carregando análise do pipeline..."):
            st.session_state.analises_pipe_cache = analise_pipeline()
    
    analises_pipe = st.session_state.analises_pipe_cache
    
    # Botão para atualizar
    if st.button("🔄 Atualizar Análise", type="primary", use_container_width=True):
        with st.spinner("🔍 Atualizando análise do pipeline..."):
            st.session_state.analises_pipe_cache = analise_pipeline()
            st.rerun()
    
    if analises_pipe and analises_pipe.get('estatisticas') is not None and not analises_pipe['estatisticas'].empty:
        # ===== SEÇÃO 1: MÉTRICAS PRINCIPAIS =====
        st.markdown("### 📊 Visão Geral do Pipeline")
        
        stats = analises_pipe['estatisticas'].iloc[0]
        total_leads = int(stats['total_leads'])
        vendas = int(stats['vendas'])
        em_negociacao = int(stats['em_negociacao'])
        novos = int(stats['novos'])
        valor_total = float(stats['valor_total']) if stats['valor_total'] else 0
        valor_vendido = float(stats['valor_vendido']) if stats['valor_vendido'] else 0
        ticket_medio = float(stats['ticket_medio']) if stats['ticket_medio'] else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📊 Total de Leads", f"{total_leads:,}")
        col2.metric("✅ Vendas", f"{vendas:,}", f"{(vendas/total_leads*100):.1f}%" if total_leads > 0 else "0%")
        col3.metric("💰 Valor Total", f"R$ {valor_total:,.2f}")
        col4.metric("💵 Valor Vendido", f"R$ {valor_vendido:,.2f}")
        
        col5, col6, col7, col8 = st.columns(4)
        col5.metric("🤝 Em Negociação", f"{em_negociacao:,}")
        col6.metric("🆕 Novos Leads", f"{novos:,}")
        col7.metric("📈 Taxa Conversão", f"{(vendas/total_leads*100):.1f}%" if total_leads > 0 else "0%")
        col8.metric("🎫 Ticket Médio", f"R$ {ticket_medio:,.2f}" if ticket_medio > 0 else "R$ 0,00")
        
        st.divider()
        
        # ===== SEÇÃO 2: DISTRIBUIÇÃO POR STATUS =====
        if analises_pipe.get('distribuicao_status') is not None and not analises_pipe['distribuicao_status'].empty:
            st.markdown("### 📊 Distribuição por Fase do Pipeline")
            df_status = analises_pipe['distribuicao_status']
            
            col1, col2 = st.columns(2)
            with col1:
                st.bar_chart(df_status.set_index("Status")[["Quantidade"]], color="#9C27B0", height=400)
            with col2:
                st.bar_chart(df_status.set_index("Status")[["Valor Total"]], color="#FF5722", height=400)
            
            st.dataframe(df_status, use_container_width=True, hide_index=True)
            
            st.divider()
        
        # ===== SEÇÃO 3: EVOLUÇÃO TEMPORAL =====
        if analises_pipe.get('evolucao_temporal') is not None and not analises_pipe['evolucao_temporal'].empty:
            st.markdown("### 📈 Evolução Temporal (Últimos 12 Meses)")
            df_temporal = analises_pipe['evolucao_temporal']
            
            col1, col2 = st.columns(2)
            with col1:
                st.line_chart(df_temporal.set_index("Mês")[["Leads", "Vendas"]], height=300)
            with col2:
                st.area_chart(df_temporal.set_index("Mês")[["Valor Vendido"]], color="#4CAF50", height=300)
            
            with st.expander("Ver dados temporais completos"):
                st.dataframe(df_temporal, use_container_width=True, hide_index=True)
            
            st.divider()
        
        # ===== SEÇÃO 4: TOP 10 POR VALOR =====
        if analises_pipe.get('top_valor') is not None and not analises_pipe['top_valor'].empty:
            st.markdown("### 💎 Top 10 Leads por Valor")
            df_top_valor = analises_pipe['top_valor']
            st.dataframe(df_top_valor, use_container_width=True, hide_index=True)
            
            st.divider()
        
        # ===== SEÇÃO 5: TAXA DE CONVERSÃO POR FASE =====
        if analises_pipe.get('taxa_conversao') is not None and not analises_pipe['taxa_conversao'].empty:
            st.markdown("### 🎯 Distribuição Percentual por Fase")
            df_conv = analises_pipe['taxa_conversao']
            st.bar_chart(df_conv.set_index("Fase")[["Percentual"]], color="#00BCD4", height=300)
            st.dataframe(df_conv, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ Seu pipeline está vazio. Vá na aba 'Gerar Leads' e importe leads para ver análises.")