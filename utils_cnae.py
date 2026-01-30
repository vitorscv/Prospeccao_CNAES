import duckdb

def buscar_cnae_por_termo(termo):
    con = duckdb.connect('hunter_leads.db')
    query = f"""
    SELECT codigo, descricao 
    FROM cnaes 
    WHERE descricao ILIKE '%{termo}%'
    ORDER BY descricao ASC
    """
    
    try:
        resultado = con.execute(query).df()
        return resultado
    except Exception as e:
        return f"Erro: Certifique-se de que a tabela 'cnaes' já foi criada. {e}"

