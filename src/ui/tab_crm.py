import streamlit as st
from src.database.crm_repository import buscar_meu_pipeline, atualizar_lead_crm, excluir_do_crm, atualizar_leads_em_lote, excluir_leads_em_lote

def render_tab_crm():
    """
    Função que desenha a tela do CRM (Tabela Editável).
    OTIMIZADO: Usa cache em session_state para evitar buscas repetidas.
    """
    st.header("💼 Carteira de Clientes")
    
    
    col_header, col_refresh = st.columns([4, 1])
    with col_header:
        st.caption("Gerencie seus leads importados. Edite status e valores direto na tabela.")
    with col_refresh:
        if st.button("🔄 Atualizar", width='stretch'):
            
            if 'df_pipeline_cache' in st.session_state:
                del st.session_state.df_pipeline_cache
            st.rerun()
    
   
    if 'df_pipeline_cache' not in st.session_state:
        with st.spinner("Carregando pipeline..."):
            df_pipeline = buscar_meu_pipeline()
            # Salva no cache
            st.session_state.df_pipeline_cache = df_pipeline
    else:
        
        df_pipeline = st.session_state.df_pipeline_cache.copy()
    
    if df_pipeline.empty:
        
        try:
            st.write("DEBUG: amostra do df_pipeline", df_pipeline.head())
            st.write("DEBUG: contagem de status", df_pipeline['status'].value_counts(dropna=False))
        except Exception:
            pass
        st.info("Sua carteira está vazia. Vá na aba 'Gerar Leads' e importe leads.")
        return

    
    total = len(df_pipeline)
    valor_total = df_pipeline['valor'].sum()
    
    
    status_upper = df_pipeline['status'].astype(str).str.upper()
    vendas_mask = status_upper.str.contains('VENDID', na=False)
    negociacao_mask = status_upper.str.contains('NEGOC', na=False)
    novo_mask = status_upper.str.contains('NOVO', na=False)

    vendas = int(vendas_mask.sum())
    valor_vendas = float(df_pipeline.loc[vendas_mask, 'valor'].sum() if not df_pipeline.loc[vendas_mask, 'valor'].empty else 0.0)

    
    em_negociacao = int(negociacao_mask.sum())
    valor_negociacao = float(df_pipeline.loc[negociacao_mask, 'valor'].sum() if not df_pipeline.loc[negociacao_mask, 'valor'].empty else 0.0)
    

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📊 Total de Leads", total)
    c2.metric("💰 Potencial Total", f"R$ {valor_total:,.2f}")
    c3.metric("✅ Vendas Realizadas", vendas, help="Leads com status 'Vendido'")
    c4.metric("💵 Valor em Vendas", f"R$ {valor_vendas:,.2f}", help="Soma dos valores vendidos")
    
    
    st.divider()
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("🤝 Em Negociação", em_negociacao)
    c6.metric("💼 Valor Negociação", f"R$ {valor_negociacao:,.2f}")
    taxa_conversao = (vendas / total * 100) if total > 0 else 0
    c7.metric("📈 Taxa Conversão", f"{taxa_conversao:.1f}%", help="Vendas / Total de Leads")
    c8.metric("🎯 Novos Leads", len(df_pipeline[df_pipeline['status'] == 'Novo']))
    
    st.divider()

    
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

    df_pipeline["excluir"] = False

   
    df_editado = st.data_editor(
        df_pipeline,
        width='stretch',
        hide_index=True,
        column_config=config_colunas,
        num_rows="fixed",
        key="tabela_crm_editor"
    )

   
    if st.button("💾 SALVAR ALTERAÇÕES", type="primary", width='stretch'):
        alteracoes = 0
        cnpjs_excluir = []
        updates_lote = []
        
        
        for index, row in df_editado.iterrows():
            cnpj = row['cnpj']
            
            
            if row.get('excluir', False):
                cnpjs_excluir.append(cnpj)
                alteracoes += 1
            else:
                
                status = row.get('status', 'Novo')
                valor = row.get('valor', 0.0)
                anotacao = row.get('anotacao', '') or ''
                updates_lote.append((cnpj, status, valor, anotacao))
                alteracoes += 1
        
        
        if cnpjs_excluir:
            excluir_leads_em_lote(cnpjs_excluir)
        
        
        if updates_lote:
            if atualizar_leads_em_lote(updates_lote):
                st.success(f"✅ {alteracoes} alterações salvas com sucesso!")
            else:
                st.error("❌ Erro ao salvar algumas alterações. Tente novamente.")
        
        if alteracoes > 0:
            
            if 'df_pipeline_cache' in st.session_state:
                del st.session_state.df_pipeline_cache
            st.rerun()