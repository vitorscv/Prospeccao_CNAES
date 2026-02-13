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

# FUNÇÃO 5: ANÁLISE DETALHADA DE MERCADO
def analise_detalhada_mercado(lista_cnaes, estado):
    """Retorna múltiplas análises do mercado para insights avançados."""
    con = get_connection()
    if not con: return {}
    
    cnaes_sql = "', '".join(lista_cnaes)
    filtro_uf = "" if estado == "BRASIL" else f"AND uf = '{estado}'"
    
    try:
        # 1. Distribuição por UF
        query_uf = f"""
            SELECT 
                uf AS "UF",
                COUNT(*) AS "Total"
            FROM estabelecimentos
            WHERE cnae_principal IN ('{cnaes_sql}')
            {filtro_uf}
            AND situacao_cadastral = '02'
            GROUP BY uf
            ORDER BY "Total" DESC
        """
        df_uf = con.execute(query_uf).df()
        
        # 2. Distribuição por CNAE (quais atividades têm mais empresas)
        query_cnae = f"""
            SELECT 
                c.descricao AS "Atividade",
                COUNT(*) AS "Total"
            FROM estabelecimentos e
            JOIN cnaes c ON e.cnae_principal = c.codigo
            WHERE e.cnae_principal IN ('{cnaes_sql}')
            {filtro_uf}
            AND e.situacao_cadastral = '02'
            GROUP BY c.descricao
            ORDER BY "Total" DESC
            LIMIT 10
        """
        df_cnae = con.execute(query_cnae).df()
        
        # 3. Empresas com contato (telefone ou email)
        query_contato = f"""
            SELECT 
                COUNT(*) AS total,
                SUM(CASE WHEN (ddd_1 IS NOT NULL AND telefone_1 IS NOT NULL) THEN 1 ELSE 0 END) AS com_telefone,
                SUM(CASE WHEN correio_eletronico IS NOT NULL AND correio_eletronico != '' THEN 1 ELSE 0 END) AS com_email,
                SUM(CASE WHEN (ddd_1 IS NOT NULL AND telefone_1 IS NOT NULL) 
                          AND (correio_eletronico IS NOT NULL AND correio_eletronico != '') THEN 1 ELSE 0 END) AS com_ambos
            FROM estabelecimentos
            WHERE cnae_principal IN ('{cnaes_sql}')
            {filtro_uf}
            AND situacao_cadastral = '02'
        """
        df_contato = con.execute(query_contato).df()
        
        # 4. Top 20 cidades (mais detalhado)
        query_top20 = f"""
            SELECT 
                m.descricao || '-' || e.uf AS "Cidade",
                COUNT(*) AS "Total",
                SUM(CASE WHEN e.ddd_1 IS NOT NULL AND e.telefone_1 IS NOT NULL THEN 1 ELSE 0 END) AS "Com Telefone",
                SUM(CASE WHEN e.correio_eletronico IS NOT NULL AND e.correio_eletronico != '' THEN 1 ELSE 0 END) AS "Com Email"
            FROM estabelecimentos e
            JOIN municipios m ON e.municipio = m.codigo
            WHERE e.cnae_principal IN ('{cnaes_sql}')
            {filtro_uf}
            AND e.situacao_cadastral = '02'
            GROUP BY m.descricao, e.uf
            ORDER BY "Total" DESC
            LIMIT 20
        """
        df_top20 = con.execute(query_top20).df()
        
        # 5. Estatísticas gerais
        query_stats = f"""
            SELECT 
                COUNT(*) AS total_empresas,
                COUNT(DISTINCT uf) AS total_estados,
                COUNT(DISTINCT municipio) AS total_cidades,
                COUNT(DISTINCT cnae_principal) AS total_cnaes
            FROM estabelecimentos
            WHERE cnae_principal IN ('{cnaes_sql}')
            {filtro_uf}
            AND situacao_cadastral = '02'
        """
        df_stats = con.execute(query_stats).df()
        
        con.close()
        
        return {
            'distribuicao_uf': df_uf,
            'distribuicao_cnae': df_cnae,
            'contatos': df_contato,
            'top20_cidades': df_top20,
            'estatisticas': df_stats
        }
    except Exception as e:
        print(f"Erro na análise detalhada: {e}")
        return {}

# FUNÇÃO 6: ANÁLISE DO PIPELINE
def analise_pipeline():
    """Retorna análises detalhadas do pipeline/CRM."""
    from src.database.connection import get_connection
    from src.database.crm_repository import inicializar_crm
    import pandas as pd
    
    # Garante que a tabela CRM existe
    inicializar_crm()
    
    con = get_connection()
    if not con: return {}
    
    try:
        # Verifica se há dados no CRM
        count_check = con.execute("SELECT COUNT(*) as total FROM crm").fetchone()
        if not count_check or count_check[0] == 0:
            con.close()
            return {}
        
        # 1. Distribuição por Status
        # Normaliza status: remove espaços, torna maiúsculo e substitui NULL por 'Sem Status'
        query_status = """
            SELECT 
                UPPER(TRIM(COALESCE(status, 'Sem Status'))) AS "Status",
                COUNT(*) AS "Quantidade",
                SUM(COALESCE(valor,0)) AS "Valor Total"
            FROM crm
            GROUP BY 1
            ORDER BY "Quantidade" DESC
        """
        df_status = con.execute(query_status).df()
        # DEBUG: mostra status brutos retornados pelo banco
        try:
            print("DEBUG - df_status head:")
            print(df_status.head())
        except Exception:
            pass
        
        # 2. Evolução temporal (vendas por mês)
        query_temporal = """
            SELECT 
                strftime('%Y-%m', data_atualizacao) AS "Mês",
                COUNT(*) AS "Leads",
                SUM(CASE WHEN status = 'Vendido' THEN 1 ELSE 0 END) AS "Vendas",
                SUM(CASE WHEN status = 'Vendido' THEN valor ELSE 0 END) AS "Valor Vendido"
            FROM crm
            WHERE data_atualizacao >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', data_atualizacao)
            ORDER BY "Mês" DESC
        """
        # Ajusta temporal para considerar variações no texto do status (case/acentos)
        query_temporal = """
            SELECT 
                strftime('%Y-%m', data_atualizacao) AS "Mês",
                COUNT(*) AS "Leads",
                SUM(CASE WHEN UPPER(status) LIKE '%VENDID%' THEN 1 ELSE 0 END) AS "Vendas",
                SUM(CASE WHEN UPPER(status) LIKE '%VENDID%' THEN valor ELSE 0 END) AS "Valor Vendido"
            FROM crm
            WHERE data_atualizacao >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', data_atualizacao)
            ORDER BY "Mês" DESC
        """
        df_temporal = con.execute(query_temporal).df()
        
        # 3. Top 10 leads por valor
        query_top_valor = """
            SELECT 
                c.cnpj,
                COALESCE(e.nome_fantasia, 'N/A') AS "Empresa",
                c.status,
                c.valor AS "Valor",
                c.data_atualizacao AS "Última Atualização"
            FROM crm c
            LEFT JOIN estabelecimentos e ON c.cnpj = (e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv)
            ORDER BY c.valor DESC
            LIMIT 10
        """
        df_top_valor = con.execute(query_top_valor).df()
        try:
            print("DEBUG - df_top_valor head:")
            print(df_top_valor.head())
        except Exception:
            pass
        
        # 4. Taxa de conversão por fase
        # Conversão por fase usando status normalizado
        query_conversao = """
            SELECT 
                UPPER(TRIM(COALESCE(status, 'Sem Status'))) AS "Fase",
                COUNT(*) AS "Total",
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM crm), 2) AS "Percentual"
            FROM crm
            GROUP BY 1
            ORDER BY "Total" DESC
        """
        df_conversao = con.execute(query_conversao).df()
        try:
            print("DEBUG - df_conversao head:")
            print(df_conversao.head())
        except Exception:
            pass
        
        # 5. Estatísticas gerais do pipeline
        query_stats = """
            SELECT 
                COUNT(*) AS total_leads,
                SUM(CASE WHEN status = 'Vendido' THEN 1 ELSE 0 END) AS vendas,
                SUM(CASE WHEN status = 'Em Negociação' THEN 1 ELSE 0 END) AS em_negociacao,
                SUM(CASE WHEN status = 'Novo' THEN 1 ELSE 0 END) AS novos,
                SUM(valor) AS valor_total,
                SUM(CASE WHEN status = 'Vendido' THEN valor ELSE 0 END) AS valor_vendido,
                AVG(CASE WHEN status = 'Vendido' THEN valor ELSE NULL END) AS ticket_medio
            FROM crm
        """
        # Estatísticas com normalização por LIKE para evitar problemas de acento/case
        query_stats = """
            SELECT 
                COUNT(*) AS total_leads,
                SUM(CASE WHEN UPPER(status) LIKE '%VENDID%' THEN 1 ELSE 0 END) AS vendas,
                SUM(CASE WHEN UPPER(status) LIKE '%NEGOC%' THEN 1 ELSE 0 END) AS em_negociacao,
                SUM(CASE WHEN UPPER(status) LIKE '%NOVO%' THEN 1 ELSE 0 END) AS novos,
                SUM(valor) AS valor_total,
                SUM(CASE WHEN UPPER(status) LIKE '%VENDID%' THEN valor ELSE 0 END) AS valor_vendido,
                AVG(CASE WHEN UPPER(status) LIKE '%VENDID%' THEN valor ELSE NULL END) AS ticket_medio
            FROM crm
        """
        df_stats = con.execute(query_stats).df()
        try:
            print("DEBUG - df_stats head:")
            print(df_stats.head())
        except Exception:
            pass
        
        con.close()
        
        # Garante que todos os DataFrames existem (mesmo que vazios)
        if df_status is None:
            df_status = pd.DataFrame()
        if df_temporal is None:
            df_temporal = pd.DataFrame()
        if df_top_valor is None:
            df_top_valor = pd.DataFrame()
        if df_conversao is None:
            df_conversao = pd.DataFrame()
        if df_stats is None:
            df_stats = pd.DataFrame()
        
        return {
            'distribuicao_status': df_status,
            'evolucao_temporal': df_temporal,
            'top_valor': df_top_valor,
            'taxa_conversao': df_conversao,
            'estatisticas': df_stats
        }
    except Exception as e:
        if con:
            con.close()
        print(f"Erro na análise do pipeline: {e}")
        import traceback
        traceback.print_exc()
        return {}

# FUNÇÃO 7: DADOS PARA DASHBOARD EXECUTIVO
def buscar_dados_dashboard_executivo(lista_estados=None, lista_cidades=None, lista_cnaes=None):
    """
    Busca dados agregados para o dashboard executivo.
    Retorna dados para KPIs, mapa e gráficos.
    """
    con = get_connection()
    if not con: return {}
    
    try:
        # Prepara filtros
        filtro_uf = ""
        if lista_estados and len(lista_estados) > 0 and "BRASIL" not in lista_estados:
            ufs_sql = "', '".join(lista_estados)
            filtro_uf = f"AND uf IN ('{ufs_sql}')"
        
        filtro_cidade = ""
        if lista_cidades and len(lista_cidades) > 0 and "TODAS" not in lista_cidades:
            # Busca códigos das cidades
            cidades_codigos = []
            for cidade in lista_cidades:
                try:
                    cidade_safe = cidade.replace("'", "''")
                    res = con.execute(f"SELECT codigo FROM municipios WHERE descricao = '{cidade_safe}' LIMIT 1").fetchone()
                    if res:
                        cidades_codigos.append(str(res[0]))
                except:
                    pass
            if cidades_codigos:
                codigos_sql = "', '".join(cidades_codigos)
                filtro_cidade = f"AND municipio IN ('{codigos_sql}')"
        
        filtro_cnae = ""
        if lista_cnaes and len(lista_cnaes) > 0:
            cnaes_sql = "', '".join(lista_cnaes)
            filtro_cnae = f"AND cnae_principal IN ('{cnaes_sql}')"
        
        # 1. KPIs: Total de empresas, cidades únicas, setor predominante
        query_kpis = f"""
            SELECT 
                COUNT(*) AS total_empresas,
                COUNT(DISTINCT municipio) AS total_cidades,
                COUNT(DISTINCT uf) AS total_estados,
                COUNT(DISTINCT cnae_principal) AS total_cnaes
            FROM estabelecimentos
            WHERE situacao_cadastral = '02'
            {filtro_uf}
            {filtro_cidade}
            {filtro_cnae}
        """
        df_kpis = con.execute(query_kpis).df()
        
        # Setor predominante (CNAE com mais empresas)
        query_setor = f"""
            SELECT 
                c.descricao AS setor,
                COUNT(*) AS total
            FROM estabelecimentos e
            JOIN cnaes c ON e.cnae_principal = c.codigo
            WHERE e.situacao_cadastral = '02'
            {filtro_uf}
            {filtro_cidade}
            {filtro_cnae}
            GROUP BY c.descricao
            ORDER BY total DESC
            LIMIT 1
        """
        df_setor = con.execute(query_setor).df()
        setor_predominante = df_setor.iloc[0]['setor'] if not df_setor.empty else "N/A"
        
        # 2. Dados para mapa: Empresas por cidade com UF
        query_mapa = f"""
            SELECT 
                m.descricao AS cidade,
                e.uf,
                COUNT(*) AS quantidade,
                COUNT(DISTINCT e.cnae_principal) AS cnaes_diferentes
            FROM estabelecimentos e
            LEFT JOIN municipios m ON e.municipio = m.codigo
            WHERE e.situacao_cadastral = '02'
            {filtro_uf}
            {filtro_cidade}
            {filtro_cnae}
            AND m.descricao IS NOT NULL
            GROUP BY m.descricao, e.uf
            HAVING COUNT(*) >= 5
            ORDER BY quantidade DESC
            LIMIT 500
        """
        df_mapa = con.execute(query_mapa).df()
        
        # 3. Top 10 Cidades
        query_top10 = f"""
            SELECT 
                m.descricao || ' - ' || e.uf AS cidade_uf,
                COUNT(*) AS total
            FROM estabelecimentos e
            LEFT JOIN municipios m ON e.municipio = m.codigo
            WHERE e.situacao_cadastral = '02'
            {filtro_uf}
            {filtro_cidade}
            {filtro_cnae}
            AND m.descricao IS NOT NULL
            GROUP BY m.descricao, e.uf
            ORDER BY total DESC
            LIMIT 10
        """
        df_top10 = con.execute(query_top10).df()
        
        # 4. Distribuição por CNAE/Setor
        query_cnae_dist = f"""
            SELECT 
                c.descricao AS setor,
                COUNT(*) AS total
            FROM estabelecimentos e
            JOIN cnaes c ON e.cnae_principal = c.codigo
            WHERE e.situacao_cadastral = '02'
            {filtro_uf}
            {filtro_cidade}
            {filtro_cnae}
            GROUP BY c.descricao
            ORDER BY total DESC
            LIMIT 15
        """
        df_cnae_dist = con.execute(query_cnae_dist).df()
        
        # 5. Distribuição por Estado
        query_uf_dist = f"""
            SELECT 
                uf,
                COUNT(*) AS total
            FROM estabelecimentos
            WHERE situacao_cadastral = '02'
            {filtro_uf}
            {filtro_cidade}
            {filtro_cnae}
            GROUP BY uf
            ORDER BY total DESC
        """
        df_uf_dist = con.execute(query_uf_dist).df()
        
        con.close()
        
        return {
            'kpis': df_kpis,
            'setor_predominante': setor_predominante,
            'mapa': df_mapa,
            'top10_cidades': df_top10,
            'distribuicao_cnae': df_cnae_dist,
            'distribuicao_uf': df_uf_dist
        }
    except Exception as e:
        if con:
            con.close()
        print(f"Erro ao buscar dados do dashboard: {e}")
        return {}

# FUNÇÃO 8: LISTAR CNAES DISPONÍVEIS
def listar_cnaes_disponiveis(termo_busca=None, limite=100):
    """Lista CNAEs disponíveis para filtro multiselect."""
    con = get_connection()
    if not con: return pd.DataFrame()
    
    try:
        if termo_busca:
            query = f"""
                SELECT codigo, descricao
                FROM cnaes
                WHERE descricao ILIKE '%{termo_busca}%'
                ORDER BY descricao
                LIMIT {limite}
            """
        else:
            query = f"""
                SELECT codigo, descricao
                FROM cnaes
                ORDER BY descricao
                LIMIT {limite}
            """
        df = con.execute(query).df()
        con.close()
        return df
    except:
        if con:
            con.close()
        return pd.DataFrame()


# NOVAS FUNÇÕES SOLICITADAS PELO TAB_ROTA.PY
def listar_cidades_disponiveis():
    """
    Retorna lista ordenada de cidades (descrição) disponíveis no banco.
    """
    con = get_connection()
    if not con:
        return []
    try:
        query = "SELECT DISTINCT descricao FROM municipios ORDER BY descricao"
        rows = con.execute(query).fetchall()
        con.close()
        return [r[0] for r in rows]
    except Exception:
        try:
            con.close()
        except:
            pass
        return []


def buscar_leads_por_cidade_e_cnae(cidades: list, cnaes: list):
    """
    Busca leads filtrando por lista de cidades (descrições) e lista de CNAE (descrições).
    Retorna um pandas.DataFrame pronto para exibição.
    Se `cnaes` for vazio, busca todos os CNAEs nas cidades fornecidas.
    """
    con = get_connection()
    if not con:
        return pd.DataFrame()

    try:
        # Filtra cidades: primeiro busca os códigos das cidades na tabela municipios
        cidades_safe = [c.replace("'", "''") for c in cidades]
        codigos = []
        for cid in cidades_safe:
            try:
                res = con.execute(f"SELECT codigo FROM municipios WHERE descricao = '{cid}' LIMIT 1").fetchone()
                if res:
                    codigos.append(str(res[0]))
            except:
                pass

        if not codigos:
            con.close()
            return pd.DataFrame()

        codigos_sql = "', '".join(codigos)

        filtro_cnae = ""
        if cnaes and len(cnaes) > 0:
            # Assume que cnaes vem como descrições; buscamos os códigos correspondentes
            cnaes_safe = [c.replace("'", "''") for c in cnaes]
            cnaes_descr_sql = "', '".join(cnaes_safe)
            filtro_cnae = f"AND c.descricao IN ('{cnaes_descr_sql}')"

        query = f"""
            SELECT 
                e.nome_fantasia AS nome_fantasia,
                e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv AS cnpj,
                e.logradouro AS logradouro,
                e.numero AS numero,
                COALESCE(m.descricao, '') AS municipio,
                e.uf AS uf,
                COALESCE(c.descricao, '') AS cnae
            FROM estabelecimentos e
            LEFT JOIN municipios m ON e.municipio = m.codigo
            LEFT JOIN cnaes c ON e.cnae_principal = c.codigo
            WHERE e.situacao_cadastral = '02'
            AND e.municipio IN ('{codigos_sql}')
            {filtro_cnae}
            LIMIT 50000
        """
        df = con.execute(query).df()
        con.close()
        return df
    except Exception:
        try:
            con.close()
        except:
            pass
        return pd.DataFrame()