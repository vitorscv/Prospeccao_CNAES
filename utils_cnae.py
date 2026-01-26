import duckdb

def buscar_cnae_por_termo(termo):
    """
    Essa função será o coração do seu formulário. 
    Ela busca no banco de dados todas as atividades que contém a palavra digitada.
    """
    con = duckdb.connect('hunter_leads.db')
    
    # Usamos ILIKE para ignorar maiúsculas/minúsculas e % para buscar em qualquer parte do texto
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

# Exemplo de uso para testar depois:
# print(buscar_cnae_por_termo('Gesso'))