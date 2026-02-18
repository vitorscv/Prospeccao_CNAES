import streamlit as st
import pandas as pd
from urllib.parse import quote_plus

# CONEXÃO COM O BANCO DE DADOS              
try:
    from src.database.repository import buscar_leads_por_cidade_e_cnae, listar_cidades_disponiveis, listar_cnaes_disponiveis
    BANCO_CONECTADO = True
except ImportError:
    BANCO_CONECTADO = False

def _higienizar_endereco(row) -> str:
    """
    Função auxiliar interna para limpar o endereço bruto da Receita.
    Remove 'SN', '999', resolve Zona Rural e respeita a UF do banco.
    """
    # 1. Extração e Formatação Básica
    rua = str(row.get('logradouro', '')).strip().title()
    num = str(row.get('numero', '')).strip()
    bairro = str(row.get('bairro', '')).strip().title()
    cid = str(row.get('municipio', '')).strip().title()
    uf = str(row.get('uf', '')).strip().upper() # Pega a UF exata do banco

    # 2. Lista de "Sujeira" para remover
    lixo_numeros = ['Sn', 'S/N', 'Sem Numero', 'Nan', 'None', '0', '00', '999', '111', '.', '-']
    termos_rurais = ['Zona Rural', 'Pov', 'Povoado', 'Fazenda', 'Sitio', 'Estrada', 'Rodovia']

    # Limpa Rua e Bairro se forem apenas pontos ou traços
    if rua in ['.', '-', '']: rua = ""
    if bairro in ['.', '-', '']: bairro = ""

    # Limpa Número inválido
    if num.title() in lixo_numeros:
        num = ""
    
    # Se a rua for "Zona Rural" ou "Rodovia", remove o número para o Google achar pelo menos a área
    if any(t in rua for t in termos_rurais):
        num = ""

    # 3. Montagem Inteligente (Fallback)
    partes = []

    # Se não tem rua (comum em cidade pequena), tenta usar o Bairro como referência
    if not rua and bairro:
        partes.append(bairro)
    elif rua:
        partes.append(rua)
        if num: partes.append(num)
    
    # Adiciona a Cidade e UF
    if cid:
        # SE tiver UF válida (2 letras), usa. SE NÃO, manda só a cidade.
        # ISSO CORRIGE O ERRO "TRINDADE - BA" (quando é PE)
        if len(uf) == 2:
            partes.append(f"{cid} - {uf}")
        else:
            partes.append(cid) 

    # Junta tudo
    endereco_limpo = ", ".join(partes)
    
    # Só retorna se o endereço for minimamente útil (mais de 5 letras)
    return endereco_limpo if len(endereco_limpo) > 5 else None


def gerar_link_google_maps(origem: str, leads_df: pd.DataFrame) -> str:
    """
    Gera o link oficial de navegação (DIR) usando endereços higienizados.
    """
    if leads_df.empty:
        return "#"
        
    enderecos_validos = []
    
    # Aplica a higienização linha a linha
    for _, row in leads_df.iterrows():
        end = _higienizar_endereco(row)
        if end:
            enderecos_validos.append(end)

    if not enderecos_validos:
        return "#"

    # Definição de rota
    destino = enderecos_validos[-1]      # Último cliente = Destino Final
    waypoints = enderecos_validos[:-1]   # Outros = Paradas

    # Limite de segurança da URL (aprox 9 paradas)
    if len(waypoints) > 9:
        waypoints = waypoints[:9]

    # URL Oficial de Navegação Universal (Funciona melhor que a antiga)
    base_url = "https://www.google.com/maps/dir/?api=1"
    
    params = f"&destination={quote_plus(destino)}"
    
    if origem:
        params += f"&origin={quote_plus(origem)}"
        
    if waypoints:
        waypoints_str = "|".join([quote_plus(p) for p in waypoints])
        params += f"&waypoints={waypoints_str}"
        
    params += "&travelmode=driving"

    return base_url + params

    # Limite do Google
    if len(meio_caminho) > 9:
        meio_caminho = meio_caminho[:9]

    # Usando a API oficial de Direções do Google Maps  
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
            
                            colunas_ideais = ['nome_fantasia', 'telefone', 'logradouro', 'numero', 'cnae']
                            colunas_exibir = [c for c in colunas_ideais if c in df_cidade.columns]
                            
                            st.dataframe(
                                df_cidade[colunas_exibir],
                                use_container_width=True,
                                hide_index=True
                            )