import gzip
import json
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib import request

from src.ui.icons import Icons
import streamlit as st
import pandas as pd
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
    PLOTLY_IMPORT_ERROR = None
except ImportError:
    PLOTLY_AVAILABLE = False
    PLOTLY_IMPORT_ERROR = "Plotly não está instalado. Usando visualizações nativas simplificadas."
from src.database.repository import RESULTADOS_EMPRESAS_LIMITE, buscar_empresas_dto, buscar_cnaes_flexivel, buscar_cnaes_por_secao, listar_cidades_do_banco, buscar_dados_dashboard_executivo, contar_empresas_por_cnae
from src.database.crm_repository import adicionar_lista_ao_crm
from src.services.excel_service import gerar_excel_de_dtos
from src.ui.tab_crm import render_tab_crm
from src.ui.tab_rota import render_tab_rota

#  CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Hunter Leads", layout="wide", page_icon=Icons.LOGO_PAGINA)

CNAE_GRANDES_SECOES = {
    "Seção A - Agricultura, pecuária, produção florestal, pesca e aquicultura": [(1, 3)],
    "Seção B - Indústrias extrativas": [(5, 9)],
    "Seção C - Indústrias de transformação": [(10, 33)],
    "Seção D - Eletricidade e gás": [(35, 35)],
    "Seção E - Água, esgoto, resíduos e descontaminação": [(36, 39)],
    "Seção F - Construção": [(41, 43)],
    "Seção G - Comércio e reparação de veículos": [(45, 47)],
    "Seção H - Transporte, armazenagem e correio": [(49, 53)],
    "Seção I - Alojamento e alimentação": [(55, 56)],
    "Seção J - Informação e comunicação": [(58, 63)],
    "Seção K - Atividades financeiras, seguros e serviços relacionados": [(64, 66)],
    "Seção L - Atividades imobiliárias": [(68, 68)],
    "Seção M - Atividades profissionais, científicas e técnicas": [(69, 75)],
    "Seção N - Atividades administrativas e serviços complementares": [(77, 82)],
    "Seção O - Administração pública, defesa e seguridade social": [(84, 84)],
    "Seção P - Educação": [(85, 85)],
    "Seção Q - Saúde humana e serviços sociais": [(86, 88)],
    "Seção R - Artes, cultura, esporte e recreação": [(90, 93)],
    "Seção S - Outras atividades de serviços": [(94, 96)],
    "Seção T - Serviços domésticos": [(97, 97)],
    "Seção U - Organismos internacionais e instituições extraterritoriais": [(99, 99)],
}
DASH_PRIMARY = "#C0392B"
DASH_CATEGORICAL = [
    DASH_PRIMARY,
    "#A93226",
    "#D35400",
    "#CD6155",
    "#7B241C",
    "#E67E22",
]
DASH_CONTINUOUS_SCALE = [[0, "#FDEDEC"], [0.55, "#E6A09A"], [1, DASH_PRIMARY]]
MAP_PRIMARY = "#7F0000"
MAP_CATEGORICAL = [
    MAP_PRIMARY,
    "#B30000",
    "#E34A33",
    "#FC8D59",
    "#FDBB84",
    "#FECC5C",
]
MAP_CONTINUOUS_SCALE = "YlOrRd"
ESCALAS_POPULACIONAIS = {
    "Por 1 mil habitantes": 1_000,
    "Por 10 mil habitantes": 10_000,
    "Por 100 mil habitantes": 100_000,
}
IBGE_MALHAS_BASE_URL = "https://servicodados.ibge.gov.br/api/v3/malhas"
GEOJSON_CACHE_DIR = Path("dados/geojson")
ESTADOS_IBGE_CODIGOS = {
    "AC": 12,
    "AL": 27,
    "AP": 16,
    "AM": 13,
    "BA": 29,
    "CE": 23,
    "DF": 53,
    "ES": 32,
    "GO": 52,
    "MA": 21,
    "MT": 51,
    "MS": 50,
    "MG": 31,
    "PA": 15,
    "PB": 25,
    "PR": 41,
    "PE": 26,
    "PI": 22,
    "RJ": 33,
    "RN": 24,
    "RS": 43,
    "RO": 11,
    "RR": 14,
    "SC": 42,
    "SP": 35,
    "SE": 28,
    "TO": 17,
}
def aplicar_cnae_pendente() -> None:
    if "cnae_input_widget" not in st.session_state:
        st.session_state.cnae_input_widget = "4711302"

    codigos_pendentes = st.session_state.pop("cnae_codigos_pendentes", None)
    codigo_unico = st.session_state.pop("cnae_codigo_pendente", None)
    if codigos_pendentes is None and codigo_unico:
        codigos_pendentes = [codigo_unico]

    if not codigos_pendentes:
        return

    codigos = [
        c.strip()
        for c in st.session_state.cnae_input_widget.split(",")
        if c.strip()
    ]
    for codigo in codigos_pendentes:
        codigo = str(codigo).strip()
        if codigo and codigo not in codigos:
            codigos.append(codigo)
    st.session_state.cnae_input_widget = ", ".join(codigos)


aplicar_cnae_pendente()


def formatar_intervalos_cnae(intervalos: list[tuple[int, int]]) -> str:
    partes = []
    for inicio, fim in intervalos:
        partes.append(f"{inicio:02d}" if inicio == fim else f"{inicio:02d} a {fim:02d}")
    return ", ".join(partes)


def formatar_numero(valor: int | float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def formatar_percentual(valor: float) -> str:
    return f"{valor:.1f}%".replace(".", ",")


def montar_filtros_leads(cnae_input: str, estado: str, cidade: str) -> dict:
    return {
        "lista_cnaes": [c.strip() for c in cnae_input.split(",") if c.strip()],
        "estado": estado,
        "cidade": cidade,
    }


def descrever_filtros_leads(filtros: dict | None) -> str:
    if not filtros:
        return "Nenhum filtro aplicado."

    cnaes = ", ".join(filtros.get("lista_cnaes", [])) or "Nenhum CNAE"
    estado_filtro = filtros.get("estado", "BRASIL")
    cidade_filtro = filtros.get("cidade", "TODAS")
    local = estado_filtro if cidade_filtro == "TODAS" else f"{cidade_filtro} - {estado_filtro}"
    return f"CNAE(s): {cnaes} | Local: {local}"


if "resultados_busca" not in st.session_state:
    st.session_state.resultados_busca = None
if "filtros_busca" not in st.session_state:
    st.session_state.filtros_busca = None
if "busca_atingiu_limite" not in st.session_state:
    st.session_state.busca_atingiu_limite = False


def estilizar_tabela_dashboard(
    df: pd.DataFrame,
    destaque_col: str | None = None,
    formatos: dict | None = None,
):
    styler = (
        df.style
        .format(formatos or {}, na_rep="-")
        .set_properties(**{"text-align": "left"})
    )

    colunas_texto = [c for c in ["Cidade", "UF", "CNAE", "Setor"] if c in df.columns]
    if colunas_texto:
        styler = styler.set_properties(subset=colunas_texto, **{"font-weight": "600"})

    if destaque_col and destaque_col in df.columns and pd.api.types.is_numeric_dtype(df[destaque_col]):
        styler = styler.background_gradient(subset=[destaque_col], cmap="Reds")

    return styler


def renderizar_mapa_nativo(df_mapa: pd.DataFrame, titulo_cor: str) -> None:
    st.info(f"{PLOTLY_IMPORT_ERROR} O mapa abaixo mantém latitude, longitude e tamanho das oportunidades.")
    df_fallback = df_mapa.rename(columns={"lat": "latitude", "lon": "longitude"}).copy()
    df_fallback["size"] = df_fallback["tamanho_bolha"].clip(lower=4, upper=35)
    st.map(
        df_fallback,
        latitude="latitude",
        longitude="longitude",
        size="size",
        use_container_width=True,
    )
    st.caption(f"Mapa nativo simplificado por {titulo_cor.lower()}. Use a tabela de ranking abaixo para leitura detalhada.")


def titulo_dashboard(setor: str, estado_atual: str, cidade_atual: str, cnaes: list[str]) -> str:
    if cnaes:
        base = setor if setor and setor != "N/A" else f"CNAE {', '.join(cnaes)}"
    else:
        base = "Mercado geral"

    if cidade_atual != "TODAS" and estado_atual != "BRASIL":
        return f"{base} em {cidade_atual} - {estado_atual}"
    if estado_atual != "BRASIL":
        return f"{base} em {estado_atual}"
    return f"{base} no Brasil"


def nivel_dashboard(estado_atual: str, cidade_atual: str) -> str:
    if cidade_atual != "TODAS" and estado_atual != "BRASIL":
        return "municipal"
    if estado_atual != "BRASIL":
        return "estadual"
    return "nacional"


def titulo_mapa_dashboard(nivel: str, estado_atual: str, cidade_atual: str) -> str:
    if nivel == "municipal":
        return f"Inteligência Geográfica - {cidade_atual} - {estado_atual}"
    if nivel == "estadual":
        return f"Inteligência Geográfica - Municípios de {estado_atual}"
    return "Inteligência Geográfica - Brasil"


def titulo_ranking_mapa(nivel: str, estado_atual: str, cidade_atual: str) -> str:
    if nivel == "municipal":
        return f"Resumo do mapa em {cidade_atual} - {estado_atual}"
    if nivel == "estadual":
        return f"Ranking municipal em {estado_atual}"
    return "Ranking nacional do mapa"


def titulo_top_cidades(nivel: str, estado_atual: str) -> str:
    if nivel == "estadual":
        return f"Cidades com maior potencial em {estado_atual}"
    return "Top 10 cidades com maior potencial no Brasil"


def zoom_dashboard(estado_atual: str, cidade_atual: str) -> int:
    if cidade_atual != "TODAS":
        return 11
    if estado_atual != "BRASIL":
        return 6
    return 4


def calcular_tamanho_bolha(valores: pd.Series, total_referencia: int | float | None = None) -> pd.Series:
    serie = pd.to_numeric(valores, errors="coerce").fillna(0).clip(lower=0)
    if serie.empty or serie.max() <= 0:
        return pd.Series([6] * len(serie), index=serie.index)

    if total_referencia and total_referencia > 0:
        escala = (serie / total_referencia).clip(0, 1) ** 0.5
    else:
        referencia = serie.quantile(0.95)
        if not referencia or referencia <= 0:
            referencia = serie.max()
        escala = (serie / referencia).clip(0, 1) ** 0.5

    return (6 + escala * 38).clip(6, 44).round(2)


def _slug_cache(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", nome or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    seguro = "".join(ch.lower() if ch.isalnum() else "_" for ch in texto)
    return "_".join(parte for parte in seguro.split("_") if parte)


def _nome_cache_geojson(nome: str) -> Path:
    return GEOJSON_CACHE_DIR / f"{_slug_cache(nome)}.geojson"


@st.cache_data(show_spinner=False)
def carregar_malha_ibge(nome: str, endpoint: str) -> dict | None:
    GEOJSON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _nome_cache_geojson(nome)

    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    url = (
        f"{IBGE_MALHAS_BASE_URL}/{endpoint}"
        "?formato=application/vnd.geo+json&qualidade=intermediaria"
    )
    try:
        req = request.Request(url, headers={"Accept": "application/vnd.geo+json"})
        with request.urlopen(req, timeout=20) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            payload = raw.decode("utf-8")
        geojson = json.loads(payload)
        cache_path.write_text(json.dumps(geojson), encoding="utf-8")
        return geojson
    except Exception:
        return None


def _camada_linha_geojson(geojson: dict, cor: str, largura: float) -> dict:
    return {
        "sourcetype": "geojson",
        "source": geojson,
        "type": "line",
        "color": cor,
        "line": {"width": largura},
    }


def _camada_preenchimento_geojson(geojson: dict, cor: str) -> dict:
    return {
        "sourcetype": "geojson",
        "source": geojson,
        "type": "fill",
        "color": cor,
        "below": "traces",
    }


def construir_camadas_delimitador_auto(estado_atual: str) -> tuple[list[dict], list[str]]:
    camadas = []
    nomes = []

    brasil = carregar_malha_ibge("Brasil", "paises/BR")
    if brasil:
        camadas.append(_camada_linha_geojson(brasil, "#111827", 2.2))
        nomes.append("Brasil")

    if estado_atual != "BRASIL":
        codigo_uf = ESTADOS_IBGE_CODIGOS.get(estado_atual)
        if codigo_uf:
            nome_estado = f"Estado {estado_atual}"
            geojson_estado = carregar_malha_ibge(nome_estado, f"estados/{codigo_uf}")
            if geojson_estado:
                camadas.append(_camada_preenchimento_geojson(geojson_estado, "rgba(253, 187, 132, 0.16)"))
                camadas.append(_camada_linha_geojson(geojson_estado, MAP_PRIMARY, 3.2))
                nomes.append(estado_atual)

    return camadas, nomes


def interpretar_hhi(hhi: float) -> str:
    if hhi < 1500:
        return "Mercado pulverizado: boa leitura para expansão territorial."
    if hhi < 2500:
        return "Mercado moderadamente concentrado: vale priorizar os polos líderes."
    return "Mercado altamente concentrado: poucas praças concentram grande parte das oportunidades."


def explicar_hhi(hhi: float) -> str:
    return (
        "O IHH mede a concentração das oportunidades entre os municípios: "
        "quanto mais perto de 0, mais distribuído é o mercado; quanto mais perto de 10.000, "
        "mais concentrado ele está em poucas cidades. "
        f"Neste filtro, o valor {formatar_numero(hhi)} indica: {interpretar_hhi(hhi)}"
    )


def insight_lider(nome: str, total: int, total_geral: int) -> str:
    if total_geral <= 0:
        return ""
    participacao = total / total_geral * 100
    return f"{nome} concentra {formatar_percentual(participacao)} das empresas filtradas."


def gerar_pdf_dashboard(dados_dash: dict, titulo: str, contexto: str) -> bytes:
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt

    output = BytesIO()
    kpis = dados_dash.get("kpis", pd.DataFrame()).iloc[0]
    top10 = dados_dash.get("top10_cidades", pd.DataFrame()).copy()
    temporal = dados_dash.get("tendencia_aberturas", pd.DataFrame()).copy()
    hhi_df = dados_dash.get("hhi", pd.DataFrame())
    hhi = float(hhi_df.iloc[0]["hhi"]) if hhi_df is not None and not hhi_df.empty and pd.notna(hhi_df.iloc[0]["hhi"]) else 0

    with PdfPages(output) as pdf:
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.suptitle(titulo, fontsize=18, fontweight="bold", color=DASH_PRIMARY)
        fig.text(0.08, 0.88, contexto, fontsize=10)
        fig.text(0.08, 0.78, f"Total de empresas: {formatar_numero(int(kpis['total_empresas']))}", fontsize=13)
        fig.text(0.08, 0.72, f"Cidades: {formatar_numero(int(kpis['total_cidades']))}", fontsize=13)
        fig.text(0.08, 0.66, f"CNAEs: {formatar_numero(int(kpis['total_cnaes']))}", fontsize=13)
        taxa_contato = (
            float(kpis.get("empresas_com_contato", 0)) / max(float(kpis["total_empresas"]), 1) * 100
        )
        fig.text(0.08, 0.60, f"Com contato: {formatar_percentual(taxa_contato)}", fontsize=13)
        fig.text(0.08, 0.52, f"IHH geográfico: {hhi:.0f} - {interpretar_hhi(hhi)}", fontsize=12)
        fig.text(0.08, 0.12, "Relatório gerado pelo Hunter Leads - Pantex", fontsize=9, color="#555555")
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)

        if not top10.empty:
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            top = top10.sort_values("total", ascending=True).tail(10)
            ax.barh(top["cidade_uf"], top["total"], color=DASH_PRIMARY)
            ax.set_title("Top cidades por volume de oportunidades")
            ax.set_xlabel("Empresas")
            for i, total in enumerate(top["total"]):
                ax.text(total, i, f" {formatar_numero(int(total))}", va="center")
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

        if not temporal.empty:
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            ax.plot(temporal["ano"], temporal["empresas_abertas"], color=DASH_PRIMARY, linewidth=2)
            ax.set_title("Tendência anual de aberturas")
            ax.set_xlabel("Ano")
            ax.set_ylabel("Empresas abertas")
            ax.grid(alpha=0.25)
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

    return output.getvalue()

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

    cnae_input = st.text_input("Cole os Códigos CNAE:", key="cnae_input_widget")
    st.caption("Separe por vírgula. Ex: 4711302, 4729699")
    
    st.divider()
    clicou_buscar = st.button(" GERAR LISTA DE PROSPECÇÃO")

    filtros_aplicados_sidebar = st.session_state.get("filtros_busca")
    if filtros_aplicados_sidebar:
        st.caption("Filtros aplicados na lista atual:")
        st.info(descrever_filtros_leads(filtros_aplicados_sidebar))

    st.caption(f"ℹ️ Limite de segurança: {formatar_numero(RESULTADOS_EMPRESAS_LIMITE)} resultados")
    
    with st.expander(Icons.ALERTA + " Ler sobre o Limite e Riscos"):
        st.warning("""
        **Por segurança, o sistema traz no máximo 50.000 empresas.**
        
        Se precisar de mais, você pode alterar o `LIMIT` no código, mas tenha cuidado:
        
        * **Acima de 100k:** Pode travar o navegador ao tentar exibir a tabela.
        * **Acima de 500k:** Pode estourar a memória RAM (16GB) e fechar o programa.
        
        *Recomendação:* Mantenha em 50k e use filtros de Cidade ou CNAE para segmentar melhor.
        """)

# AREA PRINCIPAL 
st.title(Icons.LOGO_PAGINA + " Hunter Leads - Pantex")

# ABAS 
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    Icons.ABA_CNAE + " Descobrir Código", 
    Icons.ABA_PROSPECT + " Gerar Leads", 
    Icons.ABA_CRM + " Meu Pipeline",
    Icons.ABA_DASH + " Dashboard",
    Icons.MAPA + " Rota",
])

# ABA 1: DESCOBRIR CNAE 
with aba1:
    st.header("Encontre o código da atividade")
    st.caption("Digite palavras-chave ou filtre por uma Grande Seção oficial da CNAE.")

    termo_cnae = st.text_input(
        "Busca flexível por palavra-chave",
        placeholder="Ex: farmácia, comércio roupas, manutenção veículos",
        key="termo_cnae_flexivel",
    )
    grande_secao = st.selectbox(
        "Filtrar por Grande Seção",
        ["Todas as seções"] + list(CNAE_GRANDES_SECOES.keys()),
        key="grande_secao_cnae",
    )
    intervalos_secao = None if grande_secao == "Todas as seções" else CNAE_GRANDES_SECOES[grande_secao]

    if intervalos_secao:
        intervalo_texto = formatar_intervalos_cnae(intervalos_secao)
        st.info(f"{Icons.INFO} Regra aplicada: divisão CNAE nos primeiros dois dígitos: {intervalo_texto}.")
    else:
        st.info(f"{Icons.INFO} Digite termos para buscar em todas as seções ou escolha uma Grande Seção para navegar.")

    termo_cnae = termo_cnae.strip()
    df_cnaes = pd.DataFrame(columns=["codigo", "descricao", "empresas_no_banco"])
    if termo_cnae and len(termo_cnae) < 2:
        st.warning("Digite pelo menos 2 caracteres para buscar por palavra-chave.")
    elif termo_cnae or intervalos_secao:
        with st.spinner(Icons.CARREGANDO + " Carregando CNAEs..."):
            if termo_cnae:
                df_cnaes = buscar_cnaes_flexivel(termo_cnae, intervalos_secao)
            else:
                df_cnaes = buscar_cnaes_por_secao(intervalos_secao)

            if df_cnaes is not None and not df_cnaes.empty:
                codigos = df_cnaes["codigo"].astype(str).tolist()
                totais = contar_empresas_por_cnae(codigos, estado, cidade)
                df_cnaes["empresas_no_banco"] = (
                    df_cnaes["codigo"].astype(str).map(totais).fillna(0).astype(int)
                )

    if df_cnaes is None or df_cnaes.empty:
        if termo_cnae or intervalos_secao:
            st.warning("Nenhum CNAE encontrado para os filtros selecionados.")
    else:
        st.divider()
        contexto_cnae = f"para \"{termo_cnae}\"" if termo_cnae else f"em {grande_secao}"
        st.markdown(f"#### {len(df_cnaes)} CNAEs encontrados {contexto_cnae}")
        st.caption(f"Contagem considerando os filtros atuais: {estado}" + (f" / {cidade}" if cidade != "TODAS" else ""))

        ordenacao_cnae = st.selectbox(
            "Ordenar tabela por",
            [
                "Código CNAE",
                "Empresas no banco - decrescente",
                "Empresas no banco - crescente",
                "Descrição A-Z",
            ],
            key="ordenacao_cnae_secao",
        )
        if ordenacao_cnae == "Empresas no banco - decrescente":
            df_cnaes = df_cnaes.sort_values(["empresas_no_banco", "codigo"], ascending=[False, True])
        elif ordenacao_cnae == "Empresas no banco - crescente":
            df_cnaes = df_cnaes.sort_values(["empresas_no_banco", "codigo"], ascending=[True, True])
        elif ordenacao_cnae == "Descrição A-Z":
            df_cnaes = df_cnaes.sort_values(["descricao", "codigo"], ascending=[True, True])
        else:
            df_cnaes = df_cnaes.sort_values("codigo", ascending=True)

        df_editor = df_cnaes.rename(columns={
            "codigo": "Código",
            "descricao": "Descrição",
            "empresas_no_banco": "Empresas no banco",
        })
        df_editor.insert(0, "Usar", False)
        df_editado = st.data_editor(
            df_editor,
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            disabled=["Código", "Descrição", "Empresas no banco"],
            key=f"editor_cnae_{grande_secao}_{termo_cnae}",
            column_config={
                "Usar": st.column_config.CheckboxColumn("Usar"),
                "Código": st.column_config.TextColumn("Código"),
                "Descrição": st.column_config.TextColumn("Descrição"),
                "Empresas no banco": st.column_config.NumberColumn("Empresas no banco"),
            },
        )
        codigos_selecionados = (
            df_editado.loc[df_editado["Usar"], "Código"].astype(str).tolist()
            if "Usar" in df_editado.columns
            else []
        )
        if st.button(
            "Usar CNAEs selecionados",
            type="primary",
            width="stretch",
            disabled=not codigos_selecionados,
        ):
            st.session_state.cnae_codigos_pendentes = codigos_selecionados
            st.toast(f"{len(codigos_selecionados)} CNAE(s) enviados para a busca.", icon=Icons.SUCESSO)
            st.rerun()

# ABA 2: RESULTADOS 
with aba2:
    st.header("Resultado da Busca")
    filtros_sidebar_atual = montar_filtros_leads(cnae_input, estado, cidade)

    if clicou_buscar:
        lista_cnaes = filtros_sidebar_atual["lista_cnaes"]

        if not lista_cnaes:
            st.warning(Icons.ALERTA + " Você esqueceu de colocar o CNAE na barra lateral!")
            st.session_state.resultados_busca = None
            st.session_state.filtros_busca = None
            st.session_state.busca_atingiu_limite = False
        else:
            with st.spinner(Icons.CARREGANDO + " Minerando dados... Aguarde..."):
                resultados = buscar_empresas_dto(lista_cnaes, estado, cidade)
                # Salva os resultados no session_state
                st.session_state.resultados_busca = resultados
                st.session_state.filtros_busca = filtros_sidebar_atual
                st.session_state.busca_atingiu_limite = len(resultados) >= RESULTADOS_EMPRESAS_LIMITE

    resultados = st.session_state.resultados_busca
    filtros_aplicados = st.session_state.filtros_busca

    if filtros_aplicados:
        st.info(Icons.INFO + " Filtros aplicados na lista atual: " + descrever_filtros_leads(filtros_aplicados))
        if filtros_sidebar_atual != filtros_aplicados:
            st.warning(
                "Os filtros da barra lateral foram alterados, mas a lista abaixo ainda usa a busca anterior. "
                "Clique em GERAR LISTA DE PROSPECÇÃO para atualizar os resultados."
            )
    
    if resultados:
        # PARTE A: MÉTRICAS
        total = len(resultados)
        com_email = sum(1 for r in resultados if r.email)
        com_tel = sum(1 for r in resultados if r.telefone_principal)

        if st.session_state.busca_atingiu_limite:
            st.warning(
                f"Aviso: sua busca atingiu o limite máximo de {formatar_numero(RESULTADOS_EMPRESAS_LIMITE)} registros. "
                "Recomendamos refinar por estado, cidade ou CNAE para não deixar leads ocultos fora da amostra."
            )
        
        c1, c2, c3 = st.columns(3)
        c1.metric(Icons.LOGO_PAGINA + " Total de Empresas", total)
        c2.metric(Icons.INFO + " Com E-mail", com_email)
        c3.metric(Icons.INFO + " Com Telefone", com_tel)
        
        st.divider()

        # PARTE B: BOTÃO BAIXAR TUDO 
        col_txt, col_btn = st.columns([3, 1])
        with col_txt:
            st.info(Icons.BUSCAR + " Selecione as empresas na tabela para enviar ao CRM ou baixar separado.")
        with col_btn:
            excel_total = gerar_excel_de_dtos(resultados)
            st.download_button(
                label=Icons.DOWNLOAD + " BAIXAR TUDO",
                data=excel_total,
                file_name="Lista_Completa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch'
            )
        
        # Botão para limpar resultados
        if st.button(Icons.BUSCAR + " Nova Busca", width='stretch'):
            st.session_state.resultados_busca = None
            st.session_state.filtros_busca = None
            st.session_state.busca_atingiu_limite = False
            st.rerun()

        #  PARTE C: TABELA COM CHECKBOX
        df_view = pd.DataFrame([vars(r) for r in resultados])
        
        # Filtra colunas visíveis
        cols = ['nome_fantasia', 'cnpj', 'cidade', 'telefone_principal', 'email']
        cols_finais = [c for c in cols if c in df_view.columns]

        evento = st.dataframe(
            df_view[cols_finais],
            width='stretch',
            hide_index=True,
            selection_mode="multi-row", 
            on_select="rerun",
            key="grid_principal"
        )
        
        #  PARTE D: AÇÕES DOS SELECIONADOS 

        indices = evento.selection.rows
        
        if indices:
            st.success(Icons.SUCESSO + f" **{len(indices)} empresas selecionadas.**")
            
            # Pega os dados dos selecionados
            lista_selecionados_dto = [resultados[i] for i in indices]
            lista_selecionados_dict = [vars(r) for r in lista_selecionados_dto]
            
            col_a, col_b = st.columns(2)
            
            # Botão 1: CRM
            with col_a:
                if st.button(" ENVIAR PARA CRM LEADS ", type="primary", width='stretch'):
                    if adicionar_lista_ao_crm(lista_selecionados_dict):
                        st.toast("Enviado para o Pipeline!", icon=Icons.SUCESSO)
                    else:
                        st.error("Erro ao salvar.")
            
            # Botão 2: Baixar Selecionados
            with col_b:
                excel_parcial = gerar_excel_de_dtos(lista_selecionados_dto)
                st.download_button(
                    label=Icons.DOWNLOAD + " BAIXAR SELECIONADOS",
                    data=excel_parcial,
                    file_name="Selecionados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch'
                )
    elif filtros_aplicados:
        st.warning(Icons.ALERTA + " Nenhuma empresa encontrada para os filtros aplicados.")
        if st.button(Icons.BUSCAR + " Nova Busca", width='stretch', key="nova_busca_sem_resultado"):
            st.session_state.resultados_busca = None
            st.session_state.filtros_busca = None
            st.session_state.busca_atingiu_limite = False
            st.rerun()

#ABA 3: pipeline
with aba3:
    render_tab_crm()

# ABA 5: ROTA / PLANEJAMENTO
with aba5:
    # A aba de rota agora busca seus próprios dados do banco
    render_tab_rota()

# ABA 4: DASHBOARD
with aba4:
    st.caption("Análise estratégica de oportunidades e expansão territorial")
    st.info(Icons.INFO + " Use os filtros da barra lateral para personalizar a análise.")
    
    # Processa filtros da sidebar principal
    lista_cnaes_dash = [c.strip() for c in cnae_input.split(',') if c.strip()] if cnae_input else []
    lista_estados_filtro = None if estado == "BRASIL" else [estado]
    lista_cidades_filtro = None if cidade == "TODAS" else [cidade]
    
    
    with st.spinner(Icons.CARREGANDO + " Carregando dados do dashboard..."):
        dados_dash = buscar_dados_dashboard_executivo(
            lista_estados=lista_estados_filtro,
            lista_cidades=lista_cidades_filtro,
            lista_cnaes=lista_cnaes_dash if lista_cnaes_dash else None
        )
    
    if not dados_dash or dados_dash.get('kpis') is None or dados_dash['kpis'].empty:
        st.warning(Icons.ALERTA + " Nenhum dado encontrado com os filtros selecionados. Tente ajustar os filtros.")
    else:
        kpis = dados_dash['kpis'].iloc[0]
        
        # BIG NUMBERS / KPIs
        st.markdown("---")
        total_empresas = int(kpis['total_empresas'])
        total_cidades = int(kpis['total_cidades'])
        total_estados = int(kpis['total_estados'])
        empresas_com_contato = int(kpis.get('empresas_com_contato', 0) or 0)
        taxa_contato = (empresas_com_contato / total_empresas * 100) if total_empresas else 0
        setor_pred = dados_dash.get('setor_predominante', 'N/A')
        nivel_dash = nivel_dashboard(estado, cidade)
        titulo_contextual = titulo_dashboard(setor_pred, estado, cidade, lista_cnaes_dash)
        contexto_relatorio = f"Filtros: estado={estado}; cidade={cidade}; CNAEs={', '.join(lista_cnaes_dash) if lista_cnaes_dash else 'todos'}"

        st.header(Icons.ABA_DASH + " " + titulo_contextual)
        col_rel1, col_rel2 = st.columns([4, 1])
        with col_rel1:
            st.caption(contexto_relatorio)
        with col_rel2:
            pdf_dashboard = gerar_pdf_dashboard(dados_dash, titulo_contextual, contexto_relatorio)
            st.download_button(
                Icons.DOWNLOAD + " Relatório PDF",
                data=pdf_dashboard,
                file_name="dashboard_hunter_leads.pdf",
                mime="application/pdf",
                width='stretch'
            )

        st.markdown("### " + Icons.ABA_DASH + " Indicadores Principais")
        col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)

        col_kpi1.metric(
            Icons.LOGO_PAGINA + " Total de Empresas Mapeadas",
            formatar_numero(total_empresas),
            help="Total de empresas ativas encontradas"
        )
        col_kpi2.metric(
            Icons.ABA_PROSPECT + " Cobertura Geográfica",
            f"{formatar_numero(total_cidades)} cidades",
            delta=f"{total_estados} estados",
            help="Quantidade de cidades únicas com empresas"
        )
        col_kpi3.metric(
            Icons.ABA_DASH + " Setor Predominante",
            setor_pred[:30] + "..." if len(setor_pred) > 30 else setor_pred,
            help="CNAE com maior concentração de empresas"
        )
        col_kpi4.metric(
            Icons.ABA_DASH + " Diversidade de Setores",
            f"{formatar_numero(int(kpis['total_cnaes']))} CNAEs",
            help="Quantidade de setores diferentes"
        )
        col_kpi5.metric(
            Icons.PHONE + " Com Contato",
            formatar_percentual(taxa_contato),
            delta=f"{formatar_numero(empresas_com_contato)} empresas",
            help="Empresas com e-mail ou telefone cadastrado"
        )
        
        st.markdown("---")
        
        #  MAPA GEOGRÁFICO
        if dados_dash.get('mapa') is not None and not dados_dash['mapa'].empty:
            st.markdown("### " + Icons.ABA_DASH + " " + titulo_mapa_dashboard(nivel_dash, estado, cidade))
            
            df_mapa = dados_dash['mapa'].copy()
            df_mapa = df_mapa.dropna(subset=['lat', 'lon'])
            modo_mapa = st.radio(
                "Modo do mapa",
                ["Volume absoluto", "Indicador relativo"],
                horizontal=True,
                key="modo_mapa_dashboard",
            )
            camadas_delimitador, nomes_delimitador = construir_camadas_delimitador_auto(estado)
            if nomes_delimitador:
                st.caption("Delimitador automático: " + " + ".join(nomes_delimitador))
            else:
                st.caption("Delimitador automático indisponível no momento.")
            escala_label = "Por 10 mil habitantes"
            escala_populacional = ESCALAS_POPULACIONAIS[escala_label]
            if modo_mapa == "Indicador relativo":
                escala_label = st.selectbox(
                    "Escala populacional",
                    list(ESCALAS_POPULACIONAIS.keys()),
                    index=1,
                    key="escala_populacional_dashboard",
                )
                escala_populacional = ESCALAS_POPULACIONAIS[escala_label]

                if dados_dash.get('tem_populacao') and 'populacao' in df_mapa.columns and df_mapa['populacao'].notna().any():
                    df_mapa['valor_mapa'] = (df_mapa['quantidade'] / df_mapa['populacao'] * escala_populacional).round(2)
                    escala_titulo = f"Empresas {escala_label.lower()}"
                    hover_extra = {'uf': True, 'quantidade': True, 'populacao': True, 'valor_mapa': True, 'cnaes_diferentes': True, 'lat': False, 'lon': False}
                else:
                    st.warning("Indicador relativo indisponível: a tabela municipios ainda não possui coluna populacao.")
                    df_mapa['valor_mapa'] = df_mapa['quantidade']
                    escala_titulo = "Quantidade de empresas"
                    hover_extra = {'uf': True, 'quantidade': True, 'cnaes_diferentes': True, 'lat': False, 'lon': False}
            else:
                df_mapa['valor_mapa'] = df_mapa['quantidade']
                escala_titulo = "Quantidade de empresas"
                hover_extra = {'uf': True, 'quantidade': True, 'cnaes_diferentes': True, 'lat': False, 'lon': False}

            if modo_mapa == "Volume absoluto":
                df_mapa['tamanho_bolha'] = calcular_tamanho_bolha(df_mapa['quantidade'], total_empresas)
            else:
                df_mapa['tamanho_bolha'] = calcular_tamanho_bolha(df_mapa['valor_mapa'])
            hover_extra['tamanho_bolha'] = False
            colorir_por_cnae = len(lista_cnaes_dash) >= 2 and 'cnae_predominante' in df_mapa.columns
            if colorir_por_cnae:
                df_mapa['cnae_mapa'] = df_mapa['cnae_predominante'].fillna('Sem CNAE')
                hover_extra.update({
                    'cnae_predominante': True,
                    'setor_predominante': True,
                    'percentual_cnae_predominante': True,
                })
                cor_mapa = 'cnae_mapa'
                mapa_cores = {
                    'color_discrete_sequence': MAP_CATEGORICAL,
                }
                titulo_cor = "CNAE predominante"
            else:
                cor_mapa = 'valor_mapa'
                mapa_cores = {
                    'color_continuous_scale': MAP_CONTINUOUS_SCALE,
                }
                titulo_cor = escala_titulo
            
      
            if df_mapa.empty:
                st.warning("Nenhum município com coordenadas válidas foi encontrado para os filtros selecionados.")
            elif not PLOTLY_AVAILABLE:
                renderizar_mapa_nativo(df_mapa, titulo_cor)
            else:
                fig_mapa = px.scatter_mapbox(
                    df_mapa,
                    lat='lat',
                    lon='lon',
                    size='tamanho_bolha',
                    color=cor_mapa,
                    hover_name='cidade',
                    hover_data=hover_extra,
                    size_max=50,
                    zoom=zoom_dashboard(estado, cidade),
                    center={'lat': df_mapa['lat'].mean(), 'lon': df_mapa['lon'].mean()},
                    height=500,
                    mapbox_style="carto-positron",
                    title=f"Densidade de Empresas por Região - {titulo_cor}",
                    labels={
                        'cnae_mapa': 'CNAE predominante',
                        'valor_mapa': escala_titulo,
                        'quantidade': 'Empresas',
                        'populacao': 'População',
                        'cnaes_diferentes': 'CNAEs diferentes',
                        'percentual_cnae_predominante': '% do CNAE predominante',
                    },
                    **mapa_cores,
                )
                fig_mapa.update_traces(
                    marker_sizeref=1,
                    marker_sizemode='diameter',
                    marker_sizemin=4,
                    marker_opacity=1.0,
                )
                layout_mapa = {
                    'margin': dict(l=0, r=0, t=30, b=0),
                    'mapbox_layers': camadas_delimitador,
                }
                if colorir_por_cnae:
                    layout_mapa['legend_title_text'] = "CNAE predominante"
                else:
                    layout_mapa['coloraxis'] = {
                        'colorbar': {
                            'title': escala_titulo,
                        },
                    }
                fig_mapa.update_layout(**layout_mapa)
                if not camadas_delimitador:
                    st.warning("Não foi possível carregar as malhas do IBGE. Verifique a internet ou o cache em dados/geojson.")
                elif estado != "BRASIL" and estado not in nomes_delimitador:
                    st.warning(f"Não foi possível carregar a malha de {estado}. O contorno do Brasil continua ativo.")
                st.plotly_chart(
                    fig_mapa,
                    width='stretch',
                    config={
                        "scrollZoom": True,
                        "displayModeBar": True,
                    },
                )
                lider_mapa = df_mapa.sort_values('valor_mapa', ascending=False).iloc[0]
                st.caption(insight_lider(f"{lider_mapa['cidade']} - {lider_mapa['uf']}", int(lider_mapa['quantidade']), total_empresas))

            if not df_mapa.empty:
                st.markdown("#### " + titulo_ranking_mapa(nivel_dash, estado, cidade))
                ordem_ranking = 'valor_mapa' if modo_mapa == "Indicador relativo" else 'quantidade'
                df_ranking = df_mapa.sort_values(ordem_ranking, ascending=False).head(10).copy()
                df_ranking['Empresas'] = df_ranking['quantidade'].astype(int)

                colunas_ranking = ['cidade', 'uf', 'Empresas']
                nomes_ranking = {
                    'cidade': 'Cidade',
                    'uf': 'UF',
                }
                destaque_ranking = 'Empresas'
                formatos_ranking = {
                    'Empresas': lambda v: formatar_numero(v),
                }

                if 'populacao' in df_ranking.columns and df_ranking['populacao'].notna().any():
                    df_ranking['População'] = df_ranking['populacao'].round(0).astype('Int64')
                    indicador_col = f"Empresas {escala_label.lower()}"
                    df_ranking[indicador_col] = (
                        df_ranking['quantidade'] / df_ranking['populacao'] * escala_populacional
                    ).round(2)
                    colunas_ranking.extend(['População', indicador_col])
                    formatos_ranking['População'] = lambda v: formatar_numero(v)
                    formatos_ranking[indicador_col] = "{:.2f}"
                    if modo_mapa == "Indicador relativo":
                        destaque_ranking = indicador_col

                df_ranking_view = df_ranking[colunas_ranking].rename(columns=nomes_ranking)
                st.dataframe(
                    estilizar_tabela_dashboard(
                        df_ranking_view,
                        destaque_col=destaque_ranking,
                        formatos=formatos_ranking,
                    ),
                    width='stretch',
                    hide_index=True,
                )
            
            with st.expander(Icons.COPIAR + " Ver dados do mapa"):
                cols_mapa = ['cidade', 'uf', 'quantidade', 'valor_mapa', 'cnaes_diferentes']
                if colorir_por_cnae:
                    cols_mapa.extend(['cnae_predominante', 'setor_predominante', 'percentual_cnae_predominante'])
                if 'populacao' in df_mapa.columns:
                    cols_mapa.insert(3, 'populacao')
                df_mapa_view = df_mapa[[c for c in cols_mapa if c in df_mapa.columns]].rename(columns={
                    'cidade': 'Cidade',
                    'uf': 'UF',
                    'quantidade': 'Empresas',
                    'populacao': 'População',
                    'valor_mapa': escala_titulo,
                    'cnaes_diferentes': 'CNAEs diferentes',
                    'cnae_predominante': 'CNAE predominante',
                    'setor_predominante': 'Setor predominante',
                    'percentual_cnae_predominante': '% do CNAE predominante',
                })
                st.dataframe(
                    estilizar_tabela_dashboard(
                        df_mapa_view,
                        destaque_col=escala_titulo,
                        formatos={
                            'Empresas': lambda v: formatar_numero(v),
                            'População': lambda v: formatar_numero(v),
                            escala_titulo: "{:.2f}" if escala_titulo != "Quantidade de empresas" else lambda v: formatar_numero(v),
                            'CNAEs diferentes': lambda v: formatar_numero(v),
                            '% do CNAE predominante': "{:.2f}",
                        },
                    ),
                    width='stretch',
                    hide_index=True,
                )
        
        st.markdown("---")
        
        #  ANÁLISE DE MERCADO 
        titulo_analise = {
            "nacional": "Análise de Mercado",
            "estadual": f"Análise Municipal em {estado}",
            "municipal": f"Análise Operacional em {cidade} - {estado}",
        }[nivel_dash]
        st.markdown(Icons.ABA_DASH + " " + titulo_analise)
        
        col_graf1 = st.container()
        
        with col_graf1:
            if dados_dash.get('top10_cidades') is not None and not dados_dash['top10_cidades'].empty:
                df_top10 = dados_dash['top10_cidades'].copy()

                if nivel_dash == "municipal":
                    resumo_cidade = df_top10.iloc[0]
                    col_mun1, col_mun2, col_mun3, col_mun4 = st.columns(4)
                    col_mun1.metric("Empresas na cidade", formatar_numero(int(resumo_cidade['total'])))
                    col_mun2.metric("Taxa de contato", formatar_percentual(float(resumo_cidade['taxa_contato'])))
                    col_mun3.metric("CNAEs diferentes", formatar_numero(int(resumo_cidade['cnaes_diferentes'])))
                    col_mun4.metric("Índice de oportunidade", f"{float(resumo_cidade['indice_oportunidade']):.1f}".replace(".", ","))
                    st.caption(
                        f"Recorte municipal ativo: {resumo_cidade['cidade_uf']}, {formatar_numero(int(resumo_cidade['total']))} empresas filtradas e {formatar_percentual(float(resumo_cidade['taxa_contato']))} com contato."
                    )
                else:
                    st.markdown(Icons.ABA_DASH + " " + titulo_top_cidades(nivel_dash, estado))

                    # Gráfico de barras horizontais
                    if not PLOTLY_AVAILABLE:
                        st.bar_chart(df_top10.set_index('cidade_uf')['total'])
                    else:
                        fig_top10 = px.bar(
                            df_top10,
                            x='total',
                            y='cidade_uf',
                            orientation='h',
                            text='total',
                            color_discrete_sequence=[DASH_PRIMARY],
                            labels={'total': 'Quantidade de Empresas', 'cidade_uf': 'Cidade'},
                            height=400
                        )
                        fig_top10.update_traces(texttemplate='%{x:,}', textposition='outside', marker_color=DASH_PRIMARY)
                        fig_top10.update_layout(
                            showlegend=False,
                            yaxis={'categoryorder': 'total ascending'},
                            margin=dict(l=0, r=0, t=0, b=0)
                        )
                        st.plotly_chart(fig_top10, width='stretch')
                        cidade_lider = df_top10.iloc[0]
                        st.caption(insight_lider(cidade_lider['cidade_uf'], int(cidade_lider['total']), total_empresas))

                with st.expander(Icons.COPIAR + " Ver ranking detalhado"):
                    df_top10_view = df_top10[['cidade_uf', 'total', 'taxa_contato', 'cnaes_diferentes', 'indice_oportunidade']].rename(columns={
                        'cidade_uf': 'Cidade',
                        'total': 'Empresas',
                        'taxa_contato': 'Taxa de contato (%)',
                        'cnaes_diferentes': 'CNAEs diferentes',
                        'indice_oportunidade': 'Índice de oportunidade',
                    })
                    st.dataframe(
                        estilizar_tabela_dashboard(
                            df_top10_view,
                            destaque_col='Índice de oportunidade',
                            formatos={
                                'Empresas': lambda v: formatar_numero(v),
                                'Taxa de contato (%)': "{:.1f}",
                                'CNAEs diferentes': lambda v: formatar_numero(v),
                                'Índice de oportunidade': "{:.1f}",
                            },
                        ),
                        width='stretch',
                        hide_index=True
                    )
            else:
                st.info("Sem dados suficientes para a análise do recorte selecionado.")

        st.markdown("---")

        col_temp, col_hhi = st.columns([2, 1])
        with col_temp:
            if dados_dash.get('tendencia_aberturas') is not None and not dados_dash['tendencia_aberturas'].empty:
                st.markdown(Icons.ABA_DASH + " Tendência de Aberturas por Ano")
                df_temporal = dados_dash['tendencia_aberturas'].copy()
                if not PLOTLY_AVAILABLE:
                    st.line_chart(df_temporal.set_index('ano')['empresas_abertas'])
                else:
                    fig_temporal = px.line(
                        df_temporal,
                        x='ano',
                        y='empresas_abertas',
                        markers=True,
                        labels={'ano': 'Ano', 'empresas_abertas': 'Empresas abertas'},
                        height=360
                    )
                    fig_temporal.update_traces(line_color=DASH_PRIMARY, marker_color=DASH_PRIMARY)
                    fig_temporal.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig_temporal, width='stretch')

                ano_pico = df_temporal.sort_values('empresas_abertas', ascending=False).iloc[0]
                st.caption(f"O pico da série foi {int(ano_pico['ano'])}, com {formatar_numero(int(ano_pico['empresas_abertas']))} empresas abertas.")
            else:
                st.info("Sem dados suficientes para tendência temporal.")

        with col_hhi:
            if dados_dash.get('hhi') is not None and not dados_dash['hhi'].empty:
                hhi_valor = float(dados_dash['hhi'].iloc[0]['hhi'] or 0)
                mercados_hhi = int(dados_dash['hhi'].iloc[0]['mercados'] or 0)
                st.markdown(Icons.ABA_DASH + " Concentração de Mercado")
                st.metric("IHH geográfico", formatar_numero(hhi_valor))
                st.caption(f"{mercados_hhi} mercados municipais analisados.")
                st.info(explicar_hhi(hhi_valor))

        if dados_dash.get('comparativo_cnaes') is not None and not dados_dash['comparativo_cnaes'].empty:
            st.markdown("---")
            st.markdown(Icons.ABA_DASH + " Comparativo entre CNAEs")
            df_comp = dados_dash['comparativo_cnaes'].copy()
            if not PLOTLY_AVAILABLE:
                st.bar_chart(df_comp.set_index('codigo')['total'])
            else:
                fig_comp = px.bar(
                    df_comp,
                    x='codigo',
                    y='total',
                    color='codigo',
                    color_discrete_sequence=DASH_CATEGORICAL,
                    text='total',
                    hover_name='setor',
                    labels={'codigo': 'CNAE', 'total': 'Empresas'},
                    height=360
                )
                fig_comp.update_traces(texttemplate='%{y:,}', textposition='outside')
                fig_comp.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_comp, width='stretch')
            df_comp_view = df_comp[['codigo', 'setor', 'total', 'cidades', 'estados', 'taxa_contato']].rename(columns={
                'codigo': 'CNAE',
                'setor': 'Setor',
                'total': 'Empresas',
                'cidades': 'Cidades',
                'estados': 'Estados',
                'taxa_contato': 'Taxa de contato (%)',
            })
            st.dataframe(
                estilizar_tabela_dashboard(
                    df_comp_view,
                    destaque_col='Empresas',
                    formatos={
                        'Empresas': lambda v: formatar_numero(v),
                        'Cidades': lambda v: formatar_numero(v),
                        'Estados': lambda v: formatar_numero(v),
                        'Taxa de contato (%)': "{:.1f}",
                    },
                ),
                width='stretch',
                hide_index=True,
            )
        
        # DISTRIBUIÇÃO POR ESTADO
        if (
            nivel_dash == "nacional"
            and dados_dash.get('distribuicao_uf') is not None
            and not dados_dash['distribuicao_uf'].empty
            and len(dados_dash['distribuicao_uf']) > 1
        ):
            st.markdown("---")
            st.markdown(Icons.ABA_DASH + " Distribuição por Estado")
            df_uf = dados_dash['distribuicao_uf'].copy()
            
            # Gráfico de barras
            if not PLOTLY_AVAILABLE:
                st.bar_chart(df_uf.set_index('uf')['total'])
            else:
                fig_uf = px.bar(
                df_uf,
                x='uf',
                y='total',
                text='total',
                color_discrete_sequence=[DASH_PRIMARY],
                labels={'uf': 'Estado (UF)', 'total': 'Quantidade de Empresas'},
                height=400
            )
                fig_uf.update_traces(texttemplate='%{y:,}', textposition='outside', marker_color=DASH_PRIMARY)
                fig_uf.update_layout(showlegend=False, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_uf, width='stretch')
            
            # Tabela
            col_tab1, col_tab2 = st.columns([2, 1])
            with col_tab1:
                df_uf_view = df_uf.rename(columns={
                    'uf': 'UF',
                    'total': 'Empresas',
                })
                st.dataframe(
                    estilizar_tabela_dashboard(
                        df_uf_view,
                        destaque_col='Empresas',
                        formatos={'Empresas': lambda v: formatar_numero(v)},
                    ),
                    width='stretch',
                    hide_index=True,
                )
            with col_tab2:
                # Estatísticas rápidas
                st.metric(Icons.ABA_PROSPECT + " Estado Líder", df_uf.iloc[0]['uf'] if not df_uf.empty else "N/A")
                st.metric(Icons.ABA_DASH + " Maior Concentração", f"{int(df_uf.iloc[0]['total']):,}" if not df_uf.empty else "0")
                if not df_uf.empty:
                    percentual_lider = (df_uf.iloc[0]['total'] / df_uf['total'].sum() * 100)
                    st.metric(Icons.INFO + " Participação do Líder", f"{percentual_lider:.1f}%")
                    st.caption(f"{df_uf.iloc[0]['uf']} lidera a distribuição estadual com {formatar_percentual(percentual_lider)} das empresas filtradas.")
