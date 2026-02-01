import streamlit as st
from src.database.connection import get_connection
from src.models.empresa_dto import EmpresaDTO

#FUNCAO 1 BUSCAR EMPRESAS 
def buscar_empresas_dto(lista_cnaes, estado, cidade="TODAS"):
    con = get_connection()
    if not con: return []

    # 1. PREPARA OS FILTROS
    cnaes_sql = "', '".join(lista_cnaes)
    
    filtro_uf = "" if estado == "BRASIL" else f"AND uf = '{estado}'"
    
    filtro_cidade = ""
    if cidade != "TODAS" and estado != "BRASIL":
        try:
            cidade_safe = cidade.replace("'", "''")
            res = con.execute(f"SELECT codigo FROM municipios WHERE descricao = '{cidade_safe}' LIMIT 1").fetchone()
            if res: filtro_cidade = f"AND estabelecimentos.municipio = '{res[0]}'"
        except: pass

    # 2. QUERY PRINCIPAL
    query = f"""
        SELECT 
            nome_fantasia,
            cnpj_basico || cnpj_ordem || cnpj_dv,
            ddd_1 || ' ' || telefone_1,
            ddd_2 || ' ' || telefone_2,
            correio_eletronico,
            m.descricao,
            uf,
            cnae_principal
        FROM estabelecimentos 
        LEFT JOIN municipios m ON estabelecimentos.municipio = m.codigo
        WHERE cnae_principal IN ('{cnaes_sql}') 
        {filtro_uf}
        AND situacao_cadastral = '02'
        {filtro_cidade}
        LIMIT 50000 
    """
    
    # 3. CONVERSÃO PARA DTO
    rows = con.execute(query).fetchall()
    con.close()

    lista_final = []
    for row in rows:
        empresa = EmpresaDTO(
            nome_fantasia=row[0],
            cnpj=str(row[1]),
            telefone_principal=row[2],
            telefone_secundario=row[3],
            email=row[4],
            cidade=row[5],
            uf=row[6],
            cnae=row[7]
        )
        lista_final.append(empresa)
        
    return lista_final 

# FUNÇÃO 2: BUSCAR CNAE POR TEXTO 
def buscar_cnae_por_texto(termo):
    con = get_connection()
    if not con: return None
    
    query = f"SELECT codigo, descricao FROM cnaes WHERE descricao ILIKE '%{termo}%' LIMIT 15"
    df = con.execute(query).df()
    con.close()
    return df

# FUNÇÃO 3: LISTAR CIDADES
@st.cache_data
def listar_cidades_do_banco(uf_filtro="TODAS"):
    con = get_connection()
    if not con: return []
    try:
        if uf_filtro == "TODAS" or uf_filtro == "BRASIL":
            
            query = "SELECT DISTINCT descricao FROM municipios ORDER BY descricao"
        else:
           
            query = f"""
                SELECT DISTINCT m.descricao 
                FROM estabelecimentos e
                JOIN municipios m ON e.municipio = m.codigo
                WHERE e.uf = '{uf_filtro}'
                ORDER BY m.descricao
            """
            
        cidades = con.execute(query).fetchall()
        con.close()
        return [c[0] for c in cidades]
    except:
        return []

        # FUNÇÃO 4: DASHBOARD Top 10
def buscar_top_cidades(lista_cnaes, estado):
    con = get_connection()
    if not con: return None

    # Prepara filtros
    cnaes_sql = "', '".join(lista_cnaes)
    filtro_uf = "" if estado == "BRASIL" else f"AND uf = '{estado}'"

    try:
        query = f"""
            SELECT 
                m.descricao AS "Cidade",
                COUNT(*) AS "Total"
            FROM estabelecimentos
            JOIN municipios m ON estabelecimentos.municipio = m.codigo
            WHERE cnae_principal IN ('{cnaes_sql}')
            {filtro_uf}
            AND situacao_cadastral = '02'
            GROUP BY m.descricao
            ORDER BY "Total" DESC
            LIMIT 10
        """
        # Retorna direto um DataFrame pro gráfico usar
        df = con.execute(query).df()
        con.close()
        return df
    except:
        return None