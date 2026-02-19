import streamlit as st
import pandas as pd
from urllib.parse import quote_plus
from src.ui.icons import Icons

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
    
    st.header(f"{Icons.MAPA} Planejador de Rota Regional", divider="blue")

    if not BANCO_CONECTADO:
        st.error(f"{Icons.ALARM} Erro: Conexão com o banco de dados não encontrada.")
        return

    # Usamos 98% da tela para um visual mais imersivo tipo Dashboard
    container = st.container()
    spacer_left, center_col, spacer_right = container.columns([0.01, 0.98, 0.01])
    
    with center_col:
        # Divide a parte superior em: Filtros (30%) e Resultados (70%)
        inner_left, inner_right = st.columns([0.6, 0.7], gap="large")
        
        # --- COLUNA ESQUERDA: CONFIGURAÇÃO ---
        with inner_left:
            with st.container(border=True):
                st.markdown(f"#### {Icons.GEAR} Configurar Viagem")
                form = st.form("form_rota", clear_on_submit=False)
                
                with form:
                    todas_cidades = listar_cidades_disponiveis() or []
                    idx_padrao = todas_cidades.index("FEIRA DE SANTANA") if "FEIRA DE SANTANA" in todas_cidades else 0
                    
                    cidade_partida = st.selectbox(f"{Icons.PIN} Ponto de Partida", options=todas_cidades, index=idx_padrao)
                    
                    cidades_selecionadas = st.multiselect(
                        f"{Icons.CITY} Cidades Destino (Ordem)",
                        options=todas_cidades,
                        placeholder="Selecione as cidades..."
                    )

                    st.divider()

                    df_cnaes = listar_cnaes_disponiveis(limite=5000)
                    cnae_opcoes = []
                    mapa_cnaes = {} 
                    
                    if isinstance(df_cnaes, pd.DataFrame) and not df_cnaes.empty:
                        for _, row in df_cnaes.iterrows():
                            cod = str(row.get('codigo', '')).strip()
                            desc = str(row.get('descricao', '')).strip()
                            if cod:
                                cnae_opcoes.append(cod)
                                mapa_cnaes[cod] = desc 
                    
                    cnaes_visuais = st.multiselect(
                        f"{Icons.FACTORY} Segmentos (CNAE)",
                        options=cnae_opcoes,
                        placeholder="Códigos"
                    )
                    cnaes_selecionados = [mapa_cnaes[c] for c in cnaes_visuais if c in mapa_cnaes]

                    st.markdown("###")
                    submit = st.form_submit_button(f"{Icons.COMPASS} Gerar Roteiro", type="primary", use_container_width=True)

        # Lógica de Estado
        if 'rota_gerada' not in st.session_state: st.session_state.rota_gerada = False
        if 'mostrar_mapa_rota' not in st.session_state: st.session_state.mostrar_mapa_rota = False

        if submit:
            if not cidades_selecionadas:
                st.toast(f"{Icons.WARNING} Selecione pelo menos uma cidade!", icon=Icons.WARNING)
                st.session_state.rota_gerada = False
                st.session_state.mostrar_mapa_rota = False
            else:
                st.session_state.rota_gerada = True
                st.session_state.mostrar_mapa_rota = False # Reseta o mapa ao fazer nova busca

        origem_maps = ""
        # --- COLUNA DIREITA: RESULTADOS ---
        with inner_right:
            if st.session_state.rota_gerada:
                with st.spinner("Analisando rota e buscando leads..."):
                    df_rota = buscar_leads_por_cidade_e_cnae(cidades_selecionadas, cnaes_selecionados)

                if df_rota.empty:
                    st.warning("Nenhum cliente encontrado com esse perfil nas cidades selecionadas.")
                else:
                    st.success(f"{Icons.LOGO_PAGINA} **{len(df_rota)} oportunidades** encontradas na rota!", icon=Icons.CHECK)
                    
                    link_maps = "#"
                    if cidade_partida:
                        origem_maps = f"{cidade_partida}, BA"
                        link_maps = gerar_link_google_maps(origem_maps, df_rota)

                    st.markdown(f"##### {Icons.LISTA} Lista de Paradas")
                    col_cidade = 'municipio' if 'municipio' in df_rota.columns else 'cidade'

                    for cidade in cidades_selecionadas:
                        df_cidade = df_rota[df_rota[col_cidade] == cidade]

                        if not df_cidade.empty:
                            with st.expander(f"{Icons.PIN} {cidade} ({len(df_cidade)} clientes)", expanded=False):
                                cols_ideais = ['nome_fantasia', 'telefone', 'logradouro', 'numero', 'cnae']
                                cols_exibir = [c for c in cols_ideais if c in df_cidade.columns]
                                st.dataframe(df_cidade[cols_exibir], use_container_width=True, hide_index=True)
                    
                    st.divider()

                    # Botões de Ação na Direita
                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if cidade_partida:
                            st.link_button(f"{Icons.PHONE} Abrir GPS (Google Maps)", link_maps, type="primary", use_container_width=True)
                    with c_btn2:
                        if st.button(f"{Icons.MAPA} Ver Mapa Visual", type="secondary", use_container_width=True):
                            st.session_state.mostrar_mapa_rota = True
            else:
                st.info(f"{Icons.POINT_LEFT} Configure sua viagem no menu à esquerda e clique em **Gerar Roteiro**.")

        # ==========================================================
        # O SEGREDO DO DASHBOARD: O MAPA VEM AQUI EMBAIXO, FULL WIDTH!
        # ==========================================================
        if st.session_state.rota_gerada and st.session_state.mostrar_mapa_rota:
            st.markdown("---")
            st.markdown(f"### {Icons.MAPA} Visão Geográfica da Rota")
            
            origem_coord = geocode_place(origem_maps) if cidade_partida else None
            cidade_coords = []
            cidades_nao_geo = []
            
            with st.spinner("Desenhando mapa panorâmico..."):
                for cid in cidades_selecionadas:
                    coord = geocode_place(f"{cid}, BA")
                    if coord: cidade_coords.append((cid, coord))
                    else: cidades_nao_geo.append(cid)

            if cidades_nao_geo:
                st.warning(f"{Icons.WARNING} Não foi possível localizar: {', '.join(cidades_nao_geo)}")

            points = []
            if origem_coord: points.append(origem_coord)
            for _, coord in cidade_coords: points.append(coord)

            route_geom = get_osrm_route(points) if len(points) >= 2 else None
            if route_geom is None and points: route_geom = points

            try:
                import plotly.graph_objects as go
                lats = [p[0] for p in route_geom] if route_geom else []
                lons = [p[1] for p in route_geom] if route_geom else []

                fig = go.Figure()
                
                if route_geom and len(route_geom) >= 2:
                    fig.add_trace(go.Scattermapbox(
                        lat=lats, lon=lons, mode='lines',
                        line=dict(width=4, color='blue'), name='Trajeto'
                    ))

                marker_lats, marker_lons, marker_texts = [], [], []
                if origem_coord:
                    marker_lats.append(origem_coord[0])
                    marker_lons.append(origem_coord[1])
                    marker_texts.append("Origem")
                
                for cid, coord in cidade_coords:
                    marker_lats.append(coord[0])
                    marker_lons.append(coord[1])
                    marker_texts.append(cid)

                if marker_lats:
                    colors = ['green'] + ['red'] * (len(marker_lats)-1) if len(marker_lats) > 1 else ['green']
                    fig.add_trace(go.Scattermapbox(
                        lat=marker_lats, lon=marker_lons, mode='markers+text',
                        text=marker_texts, textposition="top right",
                        marker=dict(size=12, color=colors), name='Paradas'
                    ))

                center_lat = marker_lats[0] if marker_lats else (lats[0] if lats else -12.97)
                center_lon = marker_lons[0] if marker_lons else (lons[0] if lons else -38.50)

                fig.update_layout(
                    mapbox_style="carto-positron", # Estilo mais limpo de Dashboard
                    mapbox=dict(center=dict(lat=center_lat, lon=center_lon), zoom=7),
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=600 # Altura ideal para mapa de tela cheia
                )
                
                # Renderiza ocupando a largura total (use_container_width=True)
                st.plotly_chart(fig, use_container_width=True)

            except Exception:
                # Fallback Leaflet adaptado para 100% da largura
                try:
                    import streamlit.components.v1 as components
                    markers = []
                    if origem_coord: markers.append({"lat": origem_coord[0], "lon": origem_coord[1], "label": "Origem"})
                    for cid, coord in cidade_coords: markers.append({"lat": coord[0], "lon": coord[1], "label": cid})

                    poly_pts = [[p[0], p[1]] for p in route_geom] if route_geom else []
                    
                    leaflet_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                      <meta charset="utf-8" />
                      <meta name="viewport" content="width=device-width, initial-scale=1.0">
                      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
                      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                      <style>body{{margin:0;padding:0;}} #map{{height:600px; width:100%;}}</style>
                    </head>
                    <body>
                      <div id="map"></div>
                      <script>
                        const map = L.map('map').setView([{markers[0]['lat'] if markers else -12.97}, {markers[0]['lon'] if markers else -38.50}], 7);
                        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
                          attribution: '© OpenStreetMap'
                        }}).addTo(map);
                        const markers = {json.dumps(markers)};
                        markers.forEach(m => {{ L.marker([m.lat, m.lon]).addTo(map).bindPopup(m.label); }});
                        const poly = {json.dumps(poly_pts)};
                        if(poly && poly.length > 0) {{
                           L.polyline(poly, {{color:'blue', weight: 4}}).addTo(map);
                           map.fitBounds(L.polyline(poly).getBounds(), {{padding:[20,20]}})
                        }}
                      </script>
                    </body>
                    </html>
                    """
                    components.html(leaflet_html, height=600)
                except Exception:
                    st.info("Mapa indisponível no momento.")