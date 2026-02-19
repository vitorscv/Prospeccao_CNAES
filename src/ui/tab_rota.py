import streamlit as st
import pandas as pd
from urllib.parse import quote_plus

# CONEXÃO COM O BANCO DE DADOS
try:
    from src.database.repository import (
        buscar_leads_por_cidade_e_cnae,
        listar_cidades_disponiveis,
        listar_cnaes_disponiveis,
    )
    BANCO_CONECTADO = True
except ImportError:
    BANCO_CONECTADO = False


import json

try:
    import requests
except Exception:
    requests = None


@st.cache_data
def geocode_place(query: str):
    """Geocodifica usando Nominatim OpenStreetMap. Retorna (lat, lon) ou None."""
    if not query:
        return None
    q = f"{query}, Brasil"
    headers = {"User-Agent": "HunterLeads/1.0 (contact:not-provided)"}
    try:
        if requests:
            resp = requests.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "json", "limit": 1}, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
        # Fallback para urllib
        from urllib import parse, request
        url = "https://nominatim.openstreetmap.org/search?" + parse.urlencode({"q": q, "format": "json", "limit": 1})
        req = request.Request(url, headers=headers)
        with request.urlopen(req, timeout=10) as r:
            payload = json.loads(r.read().decode())
            if payload:
                return float(payload[0]["lat"]), float(payload[0]["lon"])
    except Exception:
        return None
    return None

@st.cache_data
def get_osrm_route(coords):
    """
    coords: list of (lat, lon) tuples in order.
    Retorna lista de (lat, lon) para a geometria da rota ou None em caso de falha.
    """
    if not coords or len(coords) < 2:
        return None
    
    coord_str = ";".join([f"{lon},{lat}" for lat, lon in coords])
    url = f"https://router.project-osrm.org/route/v1/driving/{coord_str}"
    params = {"overview": "full", "geometries": "geojson"}
    try:
        if requests:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get("routes")
                if routes:
                    geom = routes[0].get("geometry", {}).get("coordinates", [])

                    return [(lat, lon) for lon, lat in geom]

        from urllib import parse, request
        full_url = url + "?" + parse.urlencode(params)
        req = request.Request(full_url, headers={"User-Agent": "HunterLeads/1.0"})
        with request.urlopen(req, timeout=15) as r:
            payload = json.loads(r.read().decode())
            routes = payload.get("routes")
            if routes:
                geom = routes[0].get("geometry", {}).get("coordinates", [])
                return [(lat, lon) for lon, lat in geom]
    except Exception:
        return None
    return None

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

    lixo_numeros = ['Sn', 'S/N', 'Sem Numero', 'Nan', 'None', '0', '00', '999', '111', '.', '-']
    termos_rurais = ['Zona Rural', 'Pov', 'Povoado', 'Fazenda', 'Sitio', 'Estrada', 'Rodovia']


    if rua in ['.', '-', '']: rua = ""
    if bairro in ['.', '-', '']: bairro = ""

    if num.title() in lixo_numeros:
        num = ""
    
    if any(t in rua for t in termos_rurais):
        num = ""

    partes = []

    if not rua and bairro:
        partes.append(bairro)
    elif rua:
        partes.append(rua)
        if num: partes.append(num)
    
    if cid:
        if len(uf) == 2:
            partes.append(f"{cid} - {uf}")
        else:
            partes.append(cid) 

    endereco_limpo = ", ".join(partes)
    
    return endereco_limpo if len(endereco_limpo) > 5 else None


def gerar_link_google_maps(origem: str, leads_df: pd.DataFrame) -> str:
    """
    Gera o link oficial de navegação (DIR) usando endereços higienizados.
    """
    if leads_df.empty:
        return "#"
        
    enderecos_validos = []
    
    for _, row in leads_df.iterrows():
        end = _higienizar_endereco(row)
        if end:
            enderecos_validos.append(end)

    if not enderecos_validos:
        return "#"

    destino = enderecos_validos[-1]      
    waypoints = enderecos_validos[:-1]   

    if len(waypoints) > 9:
        waypoints = waypoints[:9]

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

    # API oficial Google Maps  
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

    # layout centralizado: colunas externas atuam como espaçadores e coluna central contém form + resultados
    container = st.container()
    spacer_left, center_col, spacer_right = container.columns([0.05, 0.9, 0.05])
    inner_left, inner_right = center_col.columns([0.35, 0.65], gap="large")
    # form dentro da coluna esquerda (usando container para evitar a borda do st.form)
    with inner_left:
        form_container = st.container()
        with form_container:

            cidades_selecionadas = []
            cnaes_selecionados = []
            cidade_partida = ""

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

            st.write("")  # espaçamento

            st.subheader("2. Destinos da Viagem")
            cidades_selecionadas = st.multiselect(
                "Selecione as cidades da rota (em ordem de parada):",
                options=todas_cidades,
                placeholder="Ex: Santa Bárbara, Serrinha..."
            )

            st.write("")  # espaçamento

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

            st.write("")  # espaçamento
            
            submit = st.button("🧭 Gerar roteiro", type="primary", use_container_width=True)

    # inicializa flag rota_gerada se necessário
    if 'rota_gerada' not in st.session_state:
        st.session_state.rota_gerada = False

    # Ao submeter, atualiza flag
    if submit:
        if not cidades_selecionadas:
            st.info("👈 Selecione as cidades e clique em 'Gerar Roteiro'.")
            st.session_state.rota_gerada = False
        else:
            st.session_state.rota_gerada = True

    # mostra resultados e ações apenas se rota_gerada for True
    if st.session_state.rota_gerada:
        with st.spinner("Buscando empresas na base de dados..."):
            df_rota = buscar_leads_por_cidade_e_cnae(cidades_selecionadas, cnaes_selecionados)

        if df_rota.empty:
            st.warning("Nenhum cliente encontrado com esse perfil nas cidades selecionadas.")
        else:
            qtd_leads = len(df_rota)
            # armazena mensagem para exibir acima dos resultados na coluna direita
            result_message = f"🎯 Encontramos **{qtd_leads} oportunidades** ao longo desta rota!"
            
            # Prepara variáveis de origem/Google Maps; ação (botão + mapa) será exibida abaixo dos resultados
            if cidade_partida:
                origem_maps = f"{cidade_partida}, BA"
                link_maps = gerar_link_google_maps(origem_maps, df_rota)

            # resultados na coluna direita
            with inner_right:
                # mostra mensagem de resultados acima da lista
                st.markdown(result_message)
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
        # --- AÇÕES: Google Maps + Gerar Mapa Interno (botão) ---
        # removido divisor para manter layout contínuo; botões ficam na coluna direita
        if cidade_partida:
            # botão Google Maps (mantém comportamento e texto)
            inner_right.link_button("🚗 Abrir Rota no Google Maps (Celular)", link_maps, type="primary")

        # inicializa flag de sessão se necessário
        if 'mostrar_mapa_rota' not in st.session_state:
            st.session_state.mostrar_mapa_rota = False
        
        if inner_right.button("🗺️ Gerar mapa da rota", type="secondary"):
            st.session_state.mostrar_mapa_rota = True

        if st.session_state.mostrar_mapa_rota:
            # --- Renderiza mapa interno com marcadores e rota (Plotly ou Leaflet fallback) ---
            # 1) Geocodifica origem e cidades (usa cache)
            origem_coord = geocode_place(origem_maps) if cidade_partida else None
            cidade_coords = []
            cidades_nao_geo = []
            for cid in cidades_selecionadas:
                coord = geocode_place(f"{cid}, BA")
                if coord:
                    cidade_coords.append((cid, coord))
                else:
                    cidades_nao_geo.append(cid)

                if cidades_nao_geo:
                    container.warning(f"⚠️ Não foi possível geocodificar: {', '.join(cidades_nao_geo)}. Desenhando o que for possível.")

            # Prepara lista de pontos para rota (lat, lon)
            points = []
            if origem_coord:
                points.append(origem_coord)
            for _cid, coord in cidade_coords:
                points.append(coord)

            route_geom = None
            if len(points) >= 2:
                route_geom = get_osrm_route(points)

            # Se falhou o OSRM, cria linha direta entre pontos
            if route_geom is None and points:
                route_geom = points

            # (Full-screen HTML removed per user request)

            # Renderiza com Plotly se disponível
            try:
                import plotly.graph_objects as go
                lats = [p[0] for p in route_geom] if route_geom else []
                lons = [p[1] for p in route_geom] if route_geom else []

                fig = go.Figure()
                if route_geom and len(route_geom) >= 2:
                    fig.add_trace(go.Scattermapbox(
                        lat=lats,
                        lon=lons,
                        mode='lines',
                        line=dict(width=4, color='blue'),
                        name='Rota'
                    ))

                # Marcadores: origem (diferente ícone) e paradas
                marker_lats = []
                marker_lons = []
                marker_texts = []
                if origem_coord:
                    marker_lats.append(origem_coord[0])
                    marker_lons.append(origem_coord[1])
                    marker_texts.append("Origem")
                for cid, coord in cidade_coords:
                    marker_lats.append(coord[0])
                    marker_lons.append(coord[1])
                    marker_texts.append(cid)

                if marker_lats:
                    fig.add_trace(go.Scattermapbox(
                        lat=marker_lats,
                        lon=marker_lons,
                        mode='markers+text',
                        text=marker_texts,
                        textposition="top right",
                        marker=dict(size=10, color=['green'] + ['red'] * (len(marker_lats)-1) if len(marker_lats) > 1 else ['green']),
                        name='Pontos'
                    ))

                # Centraliza mapa
                center_lat = marker_lats[0] if marker_lats else (lats[0] if lats else 0)
                center_lon = marker_lons[0] if marker_lons else (lons[0] if lons else 0)
                fig.update_layout(
                    mapbox_style="open-street-map",
                    mapbox=dict(center=dict(lat=center_lat, lon=center_lon), zoom=8),
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=900
                )
                inner_right.plotly_chart(fig, use_container_width=True)
                # botão de abrir em tela cheia removido
            except Exception:
                # Fallback: Leaflet embed via HTML if plotly não disponível
                try:
                    import streamlit.components.v1 as components
                    markers = []
                    if origem_coord:
                        markers.append({"lat": origem_coord[0], "lon": origem_coord[1], "label": "Origem"})
                    for cid, coord in cidade_coords:
                        markers.append({"lat": coord[0], "lon": coord[1], "label": cid})

                    poly_pts = [[p[0], p[1]] for p in route_geom] if route_geom else []
                    leaflet_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                      <meta charset="utf-8" />
                      <meta name="viewport" content="width=device-width, initial-scale=1.0">
                      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
                      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                      <style>#map{{height:80vh}}</style>
                    </head>
                    <body>
                      <div id="map"></div>
                      <script>
                        const map = L.map('map').setView([{markers[0]['lat'] if markers else  -14.2350}, {markers[0]['lon'] if markers else -51.9253}], 7);
                        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                          maxZoom: 19,
                          attribution: '© OpenStreetMap'
                        }}).addTo(map);
                        const markers = {json.dumps(markers)};
                        markers.forEach(m => {{
                          L.marker([m.lat, m.lon]).addTo(map).bindPopup(m.label);
                        }});
                        const poly = {json.dumps(poly_pts)};
                        if(poly && poly.length > 0) {{
                           L.polyline(poly, {{color:'blue'}}).addTo(map);
                           map.fitBounds(L.polyline(poly).getBounds(), {{padding:[20,20]}})
                        }}
                      </script>
                    </body>
                    </html>
                    """
                    components.html(leaflet_html, height=900)
                except Exception:
                    center_col.info("Mapa interno não pôde ser carregado (Plotly/Leaflet indisponíveis).")