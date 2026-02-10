"""
Aba de planejamento de rotas para representantes (versão melhorada).
Suporta: rota automática por densidade ou rota existente (lista de cidades),
dedupe por matriz e export do roteiro.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import List, Tuple

from src.config.scoring_config import SEGMENTOS_PANTEX
from src.database.estabelecimentos_repository import (
    buscar_leads_enriquecidos,
    dedupe_leads_por_cnpj_basico,
)
from src.database.repository import buscar_dados_dashboard_executivo, listar_cidades_do_banco
from src.services.scoring_service import qualificar_leads
from src.services.route_service import planejar_rota
from src.services.excel_service import gerar_excel_roteiro
from src.ui.icons import Icons


def render_tab_rota():
    """Renderiza a aba de planejamento de rotas."""
    st.header(Icons.ABA_PROSPECT + " Planejador de Rota do Representante")
    st.caption("Forneça uma rota (lista de cidades) ou deixe o sistema gerar automaticamente.")

    # ===== SEÇÃO 1: CONFIGURAÇÃO DA ROTA =====
    st.markdown("### " + Icons.BUSCAR + " Configuração da Rota")
    col1, col2 = st.columns(2)

    with col1:
        cidade_base = st.text_input("Cidade Base", placeholder="Ex: São Paulo")
        dias_de_rota = st.number_input("Dias de Rota", min_value=1, max_value=30, value=5)
        visitas_por_dia = st.number_input("Visitas por Dia", min_value=1, max_value=20, value=8)

    with col2:
        uf_base = st.selectbox(
            "UF Base",
            ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "PE", "CE", "GO",
             "PA", "AM", "MA", "ES", "PB", "RN", "MT", "MS", "PI", "AL",
             "SE", "RO", "TO", "AC", "AP", "RR", "DF"],
        )
        somente_matriz = st.checkbox("Apenas Matrizes", value=False)

    st.divider()

    # ===== SEÇÃO 2: FILTROS DE LEADS =====
    st.markdown("### " + Icons.ABA_CNAE + " Filtros de Leads")
    col1, col2 = st.columns(2)

    with col1:
        segmentos_disponiveis = list(SEGMENTOS_PANTEX.keys())
        segmentos_labels = [SEGMENTOS_PANTEX[s].nome for s in segmentos_disponiveis]
        # Presets rápidos
        PRESETS = {
            "Todos": None,
            "Sacaria de Rafia (recomendado)": ["industria_alimentos", "atacado_alimentos", "material_construcao"]
        }
        preset = st.selectbox("Preset de Perfil", options=list(PRESETS.keys()), index=1)
        if PRESETS.get(preset) is not None:
            segmentos_selecionados = [SEGMENTOS_PANTEX[k].nome for k in PRESETS[preset] if k in SEGMENTOS_PANTEX]
        else:
            segmentos_selecionados = st.multiselect("Segmentos de Interesse", options=segmentos_labels)
        segmentos_keys = [k for k, v in SEGMENTOS_PANTEX.items() if v.nome in segmentos_selecionados]

    with col2:
        cnaes_manuais = st.text_input("CNAEs Específicos (opcional)", placeholder="4711302,4729699")
        modo_rota = st.radio(
            "Modo de Rota",
            options=["Gerar automaticamente (por densidade)", "Usar rota existente (lista de cidades)"],
            index=0,
        )
        cidades_input = None
        # detecta corretamente o modo "rota existente" (mais robusto que endswith)
        cidades_selecionadas = []
        if "rota existente" in modo_rota.lower():
            op_cidades = listar_cidades_do_banco(uf_base) if uf_base else []
            cidades_selecionadas = st.multiselect(
                "Cidades (escolha uma ou mais)", options=op_cidades, key="rota_cidades_selecionadas"
            )
        else:
            cidades_input = st.text_area("Lista de cidades para rota (uma por linha, opcional)", height=80)

    st.divider()

    # ===== SEÇÃO 3: GERAR ROTA =====
    if st.button(Icons.BUSCAR + " GERAR ROTA", type="primary", use_container_width=True):
        if not cidade_base or not uf_base:
            st.error(Icons.ALERTA + " Preencha a cidade base e UF!")
            return

        # Determina CNAEs
        cnaes_buscar: List[str] = []
        if cnaes_manuais:
            cnaes_buscar = [c.strip() for c in cnaes_manuais.split(',') if c.strip()]
        elif segmentos_keys:
            for seg_key in segmentos_keys:
                cnaes_buscar.extend(SEGMENTOS_PANTEX[seg_key].cnaes)
        else:
            st.error(Icons.ALERTA + " Selecione segmentos ou informe CNAEs!")
            return

        with st.spinner(Icons.CARREGANDO + " Gerando rota e buscando leads..."):
            # Monta cidades alvo
            cidades_alvo: List[Tuple[str, str]] = []

            if modo_rota.startswith("Gerar"):
                dados_dash = buscar_dados_dashboard_executivo(
                    lista_estados=[uf_base], lista_cidades=None, lista_cnaes=cnaes_buscar
                )
                df_top = dados_dash.get('top10_cidades') if dados_dash else None
                if df_top is None or df_top.empty:
                    st.warning(Icons.ALERTA + "Não há cidades suficientes para gerar rota. Ajuste filtros.")
                    return
                for _, row in df_top.iterrows():
                    cidade_field = row.get('cidade_uf') or row.get('Cidade') or row.get('cidade')
                    if pd.isna(cidade_field):
                        continue
                    parts = str(cidade_field).split(' - ')
                    cidade = parts[0].strip()
                    uf = parts[1].strip() if len(parts) > 1 else uf_base
                    cidades_alvo.append((cidade, uf))
            else:
                # rota existente via multiselect (renderizado fora do clique) ou via input manual
                escolhas = cidades_selecionadas or []
                if escolhas:
                    for escolha in escolhas:
                        cidades_alvo.append((escolha, uf_base))
                else:
                    linhas = [l.strip() for l in (cidades_input or "").splitlines() if l.strip()]
                    if not linhas:
                        st.warning(Icons.ALERTA + "Forneça cidades para usar a rota existente.")
                        return
                    for linha in linhas:
                        if '-' in linha:
                            parts = [p.strip() for p in linha.split('-', 1)]
                            cidades_alvo.append((parts[0], parts[1]))
                        else:
                            cidades_alvo.append((linha, uf_base))

            # Busca leads por cidade e seleciona
            leads_por_cidade: dict[str, List] = {}
            counts_by_city: dict[str, int] = {}
            total_encontrados = 0
            for cidade_nome, cidade_uf in cidades_alvo:
                leads_local = buscar_leads_enriquecidos(
                    lista_cnaes=cnaes_buscar, uf=cidade_uf, cidade=cidade_nome, somente_matriz=somente_matriz, limite=2000
                )
                count_local = len(leads_local) if leads_local else 0
                counts_by_city[f"{cidade_nome} - {cidade_uf}"] = count_local
                leads_scored = qualificar_leads(leads_local, score_minimo=0) if leads_local else []
                chave = f"{cidade_nome} - {cidade_uf}"
                leads_por_cidade[chave] = leads_scored
                total_encontrados += len(leads_scored)

            if total_encontrados == 0:
                st.warning(Icons.ALERTA + "Nenhum lead encontrado para as cidades selecionadas.")
                # mostra detalhes por cidade para debugging
                try:
                    df_counts = pd.DataFrame([{'cidade': k, 'encontrados': v} for k, v in counts_by_city.items()])
                    st.dataframe(df_counts, use_container_width=True)
                except Exception:
                    pass
                return
            else:
                # mostra cidades com zero encontrados (opcional)
                zeros = {k: v for k, v in counts_by_city.items() if v == 0}
                if zeros:
                    st.info(f"Algumas cidades não retornaram leads: {len(zeros)} (veja tabela abaixo)")
                    try:
                        df_zeros = pd.DataFrame([{'cidade': k, 'encontrados': v} for k, v in counts_by_city.items()])
                        st.dataframe(df_zeros, use_container_width=True)
                    except Exception:
                        pass

            # Seleciona top 1 por cidade e completa por score geral
            selecionados: List = []
            for chave, lista in leads_por_cidade.items():
                if lista:
                    selecionados.append(lista[0])

            vagas = dias_de_rota * visitas_por_dia - len(selecionados)
            if vagas > 0:
                restantes = []
                for lista in leads_por_cidade.values():
                    restantes.extend(lista)
                selecionados_cnpjs = {l.cnpj for l in selecionados}
                restantes = [l for l in restantes if l.cnpj not in selecionados_cnpjs]
                if somente_matriz:
                    restantes = dedupe_leads_por_cnpj_basico(restantes)
                restantes_sorted = sorted(restantes, key=lambda x: x.score, reverse=True)
                selecionados.extend(restantes_sorted[:vagas])

            # Gera rota e salva
            rota = planejar_rota(selecionados, dias_de_rota, visitas_por_dia, cidade_base, uf_base)
            st.session_state['rota_planejada'] = rota
            st.session_state['leads_rota'] = selecionados
            st.success(Icons.SUCESSO + f" Rota gerada com {rota.total_visitas} visitas em {rota.total_dias} dias!")

    st.divider()

    # ===== SEÇÃO 4: EXIBIR ROTA =====
    if 'rota_planejada' in st.session_state:
        rota = st.session_state['rota_planejada']
        st.markdown("### " + Icons.ABA_DASH + " Rota Planejada")

        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(Icons.ABA_PROSPECT + " Total de Visitas", rota.total_visitas)
        col2.metric(Icons.ABA_DASH + " Dias de Rota", rota.total_dias)
        col3.metric(Icons.LOGO_PAGINA + " Score Médio", f"{rota.score_medio_geral:.1f}")
        col4.metric(Icons.INFO + " Cidade Base", f"{rota.cidade_base} - {rota.uf_base}")

        st.divider()

        # Mapa aproximado por UF (centroides)
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
 
        pontos = []
        for dia in rota.dias:
            for stop in dia.stops:
                lead = stop.lead
                uf = lead.uf or rota.uf_base
                lat, lon = coordenadas_uf.get(uf, (-14.2350, -51.9253))
                pontos.append({'dia': dia.dia, 'ordem': stop.ordem, 'empresa': lead.nome_fantasia,
                               'cnpj': lead.cnpj, 'score': getattr(lead, 'score', 0), 'lat': lat, 'lon': lon})
 
        if pontos:
            df_map = pd.DataFrame(pontos)
            try:
                import plotly.express as px
                fig = px.scatter_mapbox(df_map, lat='lat', lon='lon', color='dia', size='score',
                                        hover_name='empresa', zoom=5, height=400, mapbox_style='open-street-map')
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                df_map = df_map.rename(columns={'lat': 'latitude', 'lon': 'longitude'})
                st.map(df_map)
 
        st.divider()
 
        # Tabela por dia e downloads
        for dia_plan in rota.dias:
            with st.expander(f"📅 Dia {dia_plan.dia} - {dia_plan.total_visitas} visitas (Score médio: {dia_plan.score_medio:.1f})", expanded=(dia_plan.dia == 1)):
                dados_dia = []
                for stop in dia_plan.stops:
                    lead = stop.lead
                    dados_dia.append({'Ordem': stop.ordem, 'Empresa': lead.nome_fantasia, 'CNPJ': lead.cnpj,
                                      'Score': getattr(lead, 'score', 0), 'Endereço': lead.endereco.formatado if lead.endereco else '',
                                      'Telefone': lead.telefone_principal or '', 'Email': lead.email or ''})
                df_dia = pd.DataFrame(dados_dia)
                st.dataframe(df_dia, use_container_width=True, hide_index=True)
                if dia_plan.link_maps_rota:
                    st.markdown(f"🗺️ [Abrir rota do dia no Google Maps]({dia_plan.link_maps_rota})")
 
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            excel_roteiro = gerar_excel_roteiro(rota, incluir_links=True)
            st.download_button(label=Icons.DOWNLOAD + " BAIXAR ROTEIRO COMPLETO", data=excel_roteiro,
                               file_name=f"Roteiro_{cidade_base}_{uf_base}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with col2:
            if st.button(Icons.BUSCAR + " NOVA ROTA"):
                del st.session_state['rota_planejada']
                del st.session_state['leads_rota']
                st.rerun()
