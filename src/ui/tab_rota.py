import streamlit as st
import pandas as pd
from urllib.parse import quote_plus

# --- CONEXÃO COM O BANCO DE DADOS ---
try:
    from src.database.repository import buscar_leads_por_cidade_e_cnae, listar_cidades_disponiveis, listar_cnaes_disponiveis
    BANCO_CONECTADO = True
except ImportError:
    BANCO_CONECTADO = False

def gerar_link_google_maps(origem: str, leads_df: pd.DataFrame) -> str:
    """Gera o link oficial de navegação do Google Maps com base no DataFrame filtrado."""
    if leads_df.empty:
        return "#"
        
    enderecos = []
    for _, row in leads_df.iterrows():
        rua = str(row.get('logradouro', '')).strip()
        num = str(row.get('numero', '')).strip()
        cid = str(row.get('municipio', '')).strip()
        
        endereco_completo = f"{rua}, {num}, {cid}, BA".strip(', ')
        if len(endereco_completo) > 5:
            enderecos.append(endereco_completo)

    if not enderecos:
        return "#"

    destino = enderecos[-1]
    meio_caminho = enderecos[:-1]

    # Limite do Google: Corta se tiver mais de 9 paradas (waypoints)
    if len(meio_caminho) > 9:
        meio_caminho = meio_caminho[:9]

    # 🔥 AQUI ESTÁ A CORREÇÃO: Usando a API oficial de Direções do Google Maps
    url = f"https://www.google.com/maps/dir/?api=1&origin={quote_plus(origem)}&destination={quote_plus(destino)}"
    
    if meio_caminho:
        waypoints_str = "|".join([quote_plus(end) for end in meio_caminho])
        url += f"&waypoints={waypoints_str}"
        
    url += "&travelmode=driving"

    return url

def render_tab_rota():
    """Renderiza a interface da aba de Rotas usando a base de dados."""
    st.header("🗺️ Planejador de Rota Regional", divider="blue")
    st.markdown("Otimize a viagem cruzando a rota com leads não prospectados da Receita Federal.")

    if not BANCO_CONECTADO:
        st.error("🚨 Erro: Conexão com o banco de dados não encontrada.")
        return

    col1, col2 = st.columns([1, 2])

    cidades_selecionadas = []
    cnaes_selecionados = []
    cidade_partida = ""

    with col1:
        st.subheader("1. Ponto de Partida")
        
        todas_cidades = listar_cidades_disponiveis()
        if not todas_cidades:
            todas_cidades = []
            
        idx_padrao = todas_cidades.index("FEIRA DE SANTANA") if "FEIRA DE SANTANA" in todas_cidades else 0 if todas_cidades else None
        
        cidade_partida = st.selectbox(
            "📍 De qual cidade o vendedor vai sair?", 
            options=todas_cidades,
            index=idx_padrao
        )

        st.divider()

        st.subheader("2. Destinos da Viagem")
        cidades_selecionadas = st.multiselect(
            "Selecione as cidades da rota (em ordem de parada):",
            options=todas_cidades,
            placeholder="Ex: Santa Bárbara, Serrinha..."
        )

        st.subheader("3. Oportunidades Alvo")
        
        df_cnaes = listar_cnaes_disponiveis(limite=5000)
        cnae_opcoes = []
        mapa_cnaes = {} 
        
        if isinstance(df_cnaes, pd.DataFrame) and not df_cnaes.empty:
            for _, row in df_cnaes.iterrows():
                cod = str(row.get('codigo', '')).strip()
                desc = str(row.get('descricao', '')).strip()
                
                if cod:
                    texto_exibicao = cod 
                    cnae_opcoes.append(texto_exibicao)
                    mapa_cnaes[texto_exibicao] = desc 
        
        cnaes_selecionados_visuais = st.multiselect(
            "Quais códigos visitar?",
            options=cnae_opcoes,
            placeholder="Ex: 2392 (Use pontuação se precisar)"
        )
        
        cnaes_selecionados = [mapa_cnaes[c] for c in cnaes_selecionados_visuais if c in mapa_cnaes]

    with col2:
        if not cidades_selecionadas:
            st.info("👈 Selecione as cidades e clique em 'Gerar Roteiro'.")
            return

        if st.button("🚀 Gerar Roteiro de Visitas", type="primary", use_container_width=True):
            
            with st.spinner("Buscando empresas na base de dados..."):
                df_rota = buscar_leads_por_cidade_e_cnae(cidades_selecionadas, cnaes_selecionados)

            if df_rota.empty:
                st.warning("Nenhum cliente encontrado com esse perfil nas cidades selecionadas.")
            else:
                qtd_leads = len(df_rota)
                st.success(f"🎯 Encontramos **{qtd_leads} oportunidades** ao longo desta rota!")
                
                if cidade_partida:
                    origem_maps = f"{cidade_partida}, BA" 
                    link_maps = gerar_link_google_maps(origem_maps, df_rota)
                    st.link_button("🚗 Abrir Rota no Google Maps (Celular)", link_maps, type="primary")

                st.markdown("### 📋 Clientes para Visitar:")
                col_cidade = 'municipio' if 'municipio' in df_rota.columns else 'cidade'
                
                for cidade in cidades_selecionadas:
                    df_cidade = df_rota[df_rota[col_cidade] == cidade]
                    
                    if not df_cidade.empty:
                        with st.expander(f"📍 Parada: {cidade} ({len(df_cidade)} clientes)", expanded=True):
                            # 🔥 AQUI: Adicionei o 'telefone' na lista de colunas preferidas
                            colunas_ideais = ['nome_fantasia', 'telefone', 'logradouro', 'numero', 'cnae']
                            colunas_exibir = [c for c in colunas_ideais if c in df_cidade.columns]
                            
                            st.dataframe(
                                df_cidade[colunas_exibir],
                                use_container_width=True,
                                hide_index=True
                            )