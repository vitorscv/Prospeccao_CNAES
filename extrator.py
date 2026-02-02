import streamlit as st
import duckdb
import pandas as pd

st.set_page_config(page_title="hunter_leads - Lead Generator", layout="wide")

st.title(" Gerador de Leads Estratégicos")
st.subheader("Filtre por CNAE, Estado e Cidade em tempo real")

# BARRA LATERAL DE FILTROS
with st.sidebar:
    st.header("Configurações da Busca")
    
    # Input de CNAEs (aceita vários separados por vírgula)
    cnaes_input = st.text_input("Lista de CNAEs (ex: 2391601, 6201501)", "2391601")
    lista_cnaes = [c.strip() for c in cnaes_input.split(',')]
    
    uf = st.selectbox("Estado (UF)", ["BA", "SP", "RJ", "MG", "PR", "SC", "PE", "CE"])
    
    cidade_id = st.text_input("Código do Município (Opcional)", "")
    
    botao_buscar = st.button("🔍 Gerar Lista de Prospecção")

#  LÓGICA DE BUSCA 
if botao_buscar:
    con = duckdb.connect('base_leads.db')
    
    with st.spinner('Processando base de dados da Receita...'):
        # Construção dinâmica da Query
        query = f"""
        SELECT 
            column00 || column01 || column02 as cnpj,
            column04 as nome_fantasia,
            column11 as cnae_principal,
            column19 as uf,
            column20 as municipio,
            '(' || column21 || ') ' || column22 as telefone,
            column27 as email,
            column10 as data_abertura
        FROM read_csv_auto('dados/ESTABELE0.zip', sep=';', encoding='latin1', header=False, all_varchar=True)
        WHERE column19 = '{uf}'
        AND column11 IN ({','.join([f"'{c}'" for c in lista_cnaes])})
        """
        
        if cidade_id:
            query += f" AND column20 = '{cidade_id}'"
            
        df = con.execute(query).df()

    if not df.empty:
        st.success(f"Encontramos {len(df)} empresas para esses critérios!")
        st.dataframe(df) # Mostra a prévia na tela
        
        # Botão para baixar o CSV formatado
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=" Baixar Lista para Excel/CSV",
            data=csv,
            file_name=f"leads_{uf}_{cnaes_input[:10]}.csv",
            mime="text/csv",
        )
    else:
        st.warning("Nenhuma empresa encontrada com esses filtros no arquivo.")

# DICA PARA O USUÁRIO 
st.info(" Dica: Se precisar de cidades específicas, consulte o código do município no site do IBGE ou na base da Receita.")