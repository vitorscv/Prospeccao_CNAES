import streamlit as st
from src.database.crm_repository import buscar_meu_pipeline, atualizar_lead_crm, excluir_do_crm, atualizar_leads_em_lote, excluir_leads_em_lote

def render_tab_crm():
    """
    Função que desenha a tela do CRM (Tabela Editável).
    OTIMIZADO: Usa cache em session_state para evitar buscas repetidas.
    """
    st.header("💼 Carteira de Clientes")
    
    # Botão de refresh no topo
    col_header, col_refresh = st.columns([4, 1])
    with col_header:
        st.caption("Gerencie seus leads importados. Edite status e valores direto na tabela.")
    with col_refresh:
        if st.button("🔄 Atualizar", use_container_width=True):
            # Limpa o cache e força nova busca
            if 'df_pipeline_cache' in st.session_state:
                del st.session_state.df_pipeline_cache
            st.rerun()
    
    # 1. CACHE: Só busca do banco se não tiver em cache ou se forçou refresh
    if 'df_pipeline_cache' not in st.session_state:
        with st.spinner("Carregando pipeline..."):
            df_pipeline = buscar_meu_pipeline()
            # Salva no cache
            st.session_state.df_pipeline_cache = df_pipeline
    else:
        # Usa dados do cache (INSTANTÂNEO!)
        df_pipeline = st.session_state.df_pipeline_cache.copy()
    
    if df_pipeline.empty:
        st.info("Sua carteira está vazia. Vá na aba 'Gerar Leads' e importe leads.")
        return

    # 2. Métricas (OTIMIZADO: calcula direto do DataFrame em memória)
    total = len(df_pipeline)
    valor_total = df_pipeline['valor'].sum()
    
    # Métricas de vendas (baseado na fase "Vendido")
    vendas = len(df_pipeline[df_pipeline['status'] == 'Vendido'])
    valor_vendas = df_pipeline[df_pipeline['status'] == 'Vendido']['valor'].sum()
    
    # Métricas em negociação
    em_negociacao = len(df_pipeline[df_pipeline['status'] == 'Em Negociação'])
    valor_negociacao = df_pipeline[df_pipeline['status'] == 'Em Negociação']['valor'].sum()
    
    # Exibe métricas em 4 colunas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Total de Leads", total)
    c2.metric("💰 Potencial Total", f"R$ {valor_total:,.2f}")
    c3.metric("✅ Vendas Realizadas", vendas, help="Leads com status 'Vendido'")
    c4.metric("💵 Valor em Vendas", f"R$ {valor_vendas:,.2f}", help="Soma dos valores vendidos")
    
    # Segunda linha de métricas
    st.divider()
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("🤝 Em Negociação", em_negociacao)
    c6.metric("💼 Valor Negociação", f"R$ {valor_negociacao:,.2f}")
    taxa_conversao = (vendas / total * 100) if total > 0 else 0
    c7.metric("📈 Taxa Conversão", f"{taxa_conversao:.1f}%", help="Vendas / Total de Leads")
    c8.metric("🎯 Novos Leads", len(df_pipeline[df_pipeline['status'] == 'Novo']))
    
    st.divider()

    # 3. Configuração da Tabela Editável
    config_colunas = {
        "cnpj": st.column_config.TextColumn("CNPJ", disabled=True),
        "nome_fantasia": st.column_config.TextColumn("Empresa", disabled=True),
        "status": st.column_config.SelectboxColumn(
            "Fase",
            options=["Novo", "Tentativa", "Em Negociação", "Vendido", "Perdido"],
            required=True
        ),
        "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
        "anotacao": st.column_config.TextColumn("Anotações"),
        "local": st.column_config.TextColumn("Local", disabled=True),
        "excluir": st.column_config.CheckboxColumn("Excluir?", default=False)
    }

    # Adiciona coluna de controle visual para exclusão
    df_pipeline["excluir"] = False

    # 4. Renderiza a Tabela
    df_editado = st.data_editor(
        df_pipeline,
        use_container_width=True,
        hide_index=True,
        column_config=config_colunas,
        num_rows="fixed",
        key="tabela_crm_editor"
    )

    # 5. Botão de Salvar (OTIMIZADO: usa batch update + atualiza cache)
    if st.button("💾 SALVAR ALTERAÇÕES", type="primary", use_container_width=True):
        alteracoes = 0
        cnpjs_excluir = []
        updates_lote = []
        
        # Primeiro, separa exclusões e atualizações
        for index, row in df_editado.iterrows():
            cnpj = row['cnpj']
            
            # Se marcou excluir
            if row.get('excluir', False):
                cnpjs_excluir.append(cnpj)
                alteracoes += 1
            else:
                # Prepara para atualização em lote
                status = row.get('status', 'Novo')
                valor = row.get('valor', 0.0)
                anotacao = row.get('anotacao', '') or ''
                updates_lote.append((cnpj, status, valor, anotacao))
                alteracoes += 1
        
        # Executa exclusões em lote (muito mais rápido)
        if cnpjs_excluir:
            excluir_leads_em_lote(cnpjs_excluir)
        
        # Executa atualizações em lote (muito mais rápido)
        if updates_lote:
            if atualizar_leads_em_lote(updates_lote):
                st.success(f"✅ {alteracoes} alterações salvas com sucesso!")
            else:
                st.error("❌ Erro ao salvar algumas alterações. Tente novamente.")
        
        if alteracoes > 0:
            # ATUALIZA O CACHE: Remove para forçar nova busca na próxima renderização
            if 'df_pipeline_cache' in st.session_state:
                del st.session_state.df_pipeline_cache
            st.rerun()