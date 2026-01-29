import streamlit as st
import duckdb
import pandas as pd
from io import BytesIO

# --- FUNÇÃO DE EXCEL CORRIGIDA ---
def gerar_excel_formatado(df):
    output = BytesIO() # Corrigido: BytesIO com B e I e O maiúsculos

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: # Corrigido: ExcelWriter
        df.to_excel(writer, index=False, sheet_name='Leads') # Corrigido: sheet_name

        workbook = writer.book
        worksheet = writer.sheets['Leads'] # Corrigido: variável worksheet

        formato_texto = workbook.add_format({'num_format': '@', 'align': 'left', 'valign': 'vcenter'})

        # Ajustes de largura 
        for i, col in enumerate(df.columns):
            # Corrigido: lógica do max estava quebrada em várias linhas
            tam_max = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            )
            worksheet.set_column(i, i, tam_max + 2, formato_texto)

    return output.getvalue() 


# 1. CONFIGURAÇÃO E ESTILO
st.set_page_config(page_title="Hunter Leads", page_icon="🏹", layout="wide")

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

st.title("🏹 Hunter Leads - Pantex")


# 2. FUNÇÃO DE CONEXÃO E AUXILIARES
def get_connection():
    try:
        return duckdb.connect('hunter_leads.db', read_only=True)
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return None

# Função para buscar cidades no banco
def get_cidades(uf_selecionada):
    con = get_connection()
    if con:
        try:
            # Busca apenas cidades que existem no estado selecionado
            query = f"""
                SELECT DISTINCT m.descricao 
                FROM estabelecimentos e
                JOIN municipios m ON e.municipio = m.codigo
                WHERE e.uf = '{uf_selecionada}'
                ORDER BY m.descricao
            """
            df = con.execute(query).df()
            con.close()
            return df['descricao'].tolist()
        except:
            return []
    return []


# 3. BARRA LATERAL (FILTROS)
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/107/107799.png", width=100)
    st.header("Filtros de Busca")
    
    estado = st.selectbox("Selecione o Estado Alvo:", 
                          ["BA", "SP", "RJ", "MG", "RS", "SC", "PR", "PE", "CE", "GO", "ES", "SE", "AL", "PB", "RN", "MA", "PI", "PA", "AM", "MT", "MS", "DF"])
    
    # Lógica da Cidade
    lista_cidades = get_cidades(estado)
    lista_cidades.insert(0, "TODAS")
    cidade = st.selectbox("Selecione a Cidade:", lista_cidades)

    codigo_cnae = st.text_input("Cole o Código CNAE:", placeholder="Ex: 0111301")
    
    st.markdown("---")
    
    # Variável que guarda o clique do botão
    clicou_buscar = st.button(" GERAR LISTA DE PROSPECÇÃO")

# 4. ÁREA PRINCIPAL (ABAS)
aba1, aba2, aba3 = st.tabs(["🔍 Descobrir Código", "📊 Gerar Leads", "📈 Dashboard"])

# ABA 1: Descobrir o CNAE 
with aba1:
    st.header("Encontre o código da atividade")
    st.info("Passo 1: Digite o nome da atividade para descobrir o código.")
    
    termo_busca = st.text_input("Digite a atividade (ex: Arroz, Gesso, Padaria):")

    if termo_busca:
        con = get_connection()
        if con:
            # Query simples para achar o código
            query = f"SELECT codigo, descricao FROM cnaes WHERE descricao ILIKE '%{termo_busca}%' LIMIT 15"
            results = con.execute(query).df()
            con.close()
            
            if not results.empty:
                st.dataframe(results, hide_index=True, use_container_width=True)
            else:
                st.warning("Nenhum CNAE encontrado.")


#  ABA 2: Gerar Leads 
with aba2:
    st.header("Base de Empresas")
    
    if clicou_buscar:
        # 1. TRATAMENTO INTELIGENTE DOS CNAES
        lista_cnaes = [c.strip() for c in codigo_cnae.split(',') if c.strip()]
        
        if not lista_cnaes:
            st.warning("⚠️ Digite pelo menos um código CNAE.")
        else:
            con = get_connection()
            if con:
                # Define o local para mostrar na mensagem
                local_busca = f"{cidade}-{estado}" if cidade != "TODAS" else f"Estado de {estado}"
                
                with st.spinner(f"Minerando dados em {local_busca}..."):
                    try:
                        # === LÓGICA DE FILTRO ===
                        filtro_cidade_sql = ""
                        
                        # Se escolheu uma cidade específica
                        if cidade != "TODAS":
                            try:
                                cidade_safe = cidade.replace("'", "''")
                                q_cod = f"SELECT codigo FROM municipios WHERE descricao = '{cidade_safe}' LIMIT 1"
                                res_cod = con.execute(q_cod).fetchone()
                                if res_cod:
                                    filtro_cidade_sql = f"AND estabelecimentos.municipio = '{res_cod[0]}'"
                            except:
                                pass

                        # FORMATAR PARA SQL
                        cnaes_para_sql = "', '".join(lista_cnaes)

                        # Query Atualizada
                        query_leads = f"""
                            SELECT 
                                nome_fantasia AS "Nome Fantasia",
                                cnpj_basico || cnpj_ordem || cnpj_dv AS "CNPJ",
                                ddd_1 || ' ' || telefone_1 AS "Telefone Principal",
                                ddd_2 || ' ' || telefone_2 AS "Telefone Secundário",
                                correio_eletronico AS "E-mail",
                                m.descricao AS "Cidade",
                                uf AS "UF",
                                cnae_principal AS "CNAE"
                            FROM estabelecimentos 
                            LEFT JOIN municipios m ON estabelecimentos.municipio = m.codigo
                            WHERE cnae_principal IN ('{cnaes_para_sql}') 
                            AND uf = '{estado}'
                            AND situacao_cadastral = '02'
                            {filtro_cidade_sql}
                            LIMIT 1000
                        """
                        
                        df_leads = con.execute(query_leads).df()
                        con.close()
                        
                        if not df_leads.empty:
                            st.success(f"✅ Sucesso! Encontramos {len(df_leads)} empresas com esses CNAEs.")
                            
                            # Métricas
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Total Encontrado", len(df_leads))
                            col2.metric("Com E-mail", df_leads["E-mail"].notnull().sum())
                            col3.metric("Com Telefone Extra", df_leads["Telefone Secundário"].notnull().sum())
                            st.divider()

                            # Tabela
                            st.dataframe(df_leads, hide_index=True, use_container_width=True)
                            
                            # --- TRATAMENTO DO CNPJ E DOWNLOAD ---
                            # Importante: Use df_leads aqui, não df_filtrado
                            if 'CNPJ' in df_leads.columns:
                                df_leads['CNPJ'] = df_leads['CNPJ'].astype(str).str.replace(r'\.0$', '', regex=True)

                            # --- GERA O ARQUIVO BONITÃO ---
                            excel_pronto = gerar_excel_formatado(df_leads)

                            # --- BOTÃO DE DOWNLOAD ---
                            st.download_button(
                                label="📥 Baixar Planilha Formatada",
                                data=excel_pronto,
                                file_name="Leads_Formatados.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.warning(f"Nenhuma empresa encontrada em {local_busca} para os CNAEs informados.")
                                                
                    except Exception as e:
                        st.error(f"Erro na extração: {e}")

# ABA 3: Dashboard de Mercado
with aba3:
    st.header("📈 Inteligência de Mercado")
    st.info("Analise onde estão as maiores oportunidades.")

    # Aproveita os filtros que já estão na barra lateral
    if st.button("📊 ANALISAR MERCADO"):
        if not codigo_cnae:
            st.warning("⚠️ Digite um CNAE na barra lateral primeiro.")
        else:
            con = get_connection()
            if con:
                with st.spinner(f"Analisando o mercado em {estado}..."):
                    try:
                        # 1. Trata os CNAES (igual na aba 2)
                        lista_cnaes = [c.strip() for c in codigo_cnae.split(',') if c.strip()]
                        cnaes_sql = "', '".join(lista_cnaes)
                        
                        # 2. Query de Agrupamento
                        query_dashboard = f"""
                            SELECT 
                                m.descricao AS "Cidade",
                                COUNT(*) AS "Total de Empresas"
                            FROM estabelecimentos
                            LEFT JOIN municipios m ON estabelecimentos.municipio = m.codigo
                            WHERE cnae_principal IN ('{cnaes_sql}')
                            AND uf = '{estado}'
                            AND situacao_cadastral = '02'
                            GROUP BY m.descricao
                            ORDER BY "Total de Empresas" DESC
                            LIMIT 10
                        """
                        
                        df_dash = con.execute(query_dashboard).df()
                        con.close()

                        if not df_dash.empty:
                            # Mostra números gerais
                            total_estado = df_dash["Total de Empresas"].sum()
                            st.metric(label=f"Top 10 Cidades em {estado}", value=total_estado)
                            
                            # GRÁFICO DE BARRAS 
                            st.bar_chart(df_dash.set_index("Cidade"))
                            
                            # Mostra a tabelinha também
                            with st.expander("Ver dados detalhados"):
                                st.dataframe(df_dash, use_container_width=True)
                        else:
                            st.warning("Nenhum dado encontrado para gerar gráficos.")

                    except Exception as e:
                        st.error(f"Erro ao gerar dashboard: {e}")