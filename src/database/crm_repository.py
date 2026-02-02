from src.database.connection import get_connection
import streamlit as st
import pandas as pd

def inicializar_crm():
    """Cria a tabela CRM e índices para performance."""
    con = get_connection()
    if not con: return
    try:
        # Tabela simples: CNPJ é a chave.
        con.execute("""
            CREATE TABLE IF NOT EXISTS crm (
                cnpj TEXT PRIMARY KEY,
                status TEXT DEFAULT 'Novo',
                anotacao TEXT,
                valor DECIMAL(10,2) DEFAULT 0.0,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Cria índices para acelerar as queries (se não existirem)
        try:
            con.execute("CREATE INDEX IF NOT EXISTS idx_crm_data_atualizacao ON crm(data_atualizacao DESC)")
        except:
            pass  # Índice pode já existir
        
        con.close()
    except Exception as e:
        if con:
            con.close()
        print(f"Erro ao inicializar CRM: {e}")

def adicionar_lista_ao_crm(lista_leads):
    """
    Recebe uma lista de dicionários (leads) e salva apenas o CNPJ na tabela CRM.
    Usa 'INSERT OR IGNORE' para não duplicar se você selecionar o mesmo cara duas vezes.
    OTIMIZADO: Limpa cache após adicionar.
    """
    con = get_connection()
    if not con: return False
    
    inicializar_crm()
    try:
        # Prepara os dados: só precisamos do CNPJ para "reservar" o lead
        dados = [(l['cnpj'], 'Novo', '', 0.0) for l in lista_leads]
        
        # Inserção em massa super rápida
        con.executemany("""
            INSERT OR IGNORE INTO crm (cnpj, status, anotacao, valor) 
            VALUES (?, ?, ?, ?)
        """, dados)
        
        con.close()
        
        # Limpa cache do Streamlit para forçar atualização
        _buscar_pipeline_interno.clear()
        
        return True
    except Exception as e:
        st.error(f"Erro ao importar: {e}")
        return False

def atualizar_lead_crm(cnpj, campo, valor):
    """Atualiza um campo específico (ex: mudar só o status)."""
    con = get_connection()
    if not con: return False
    try:
        # Validação de campo para prevenir SQL injection
        campos_permitidos = ['status', 'valor', 'anotacao']
        if campo not in campos_permitidos:
            return False
        
        # Query dinâmica segura
        query = f"UPDATE crm SET {campo} = ?, data_atualizacao = CURRENT_TIMESTAMP WHERE cnpj = ?"
        con.execute(query, [valor, cnpj])
        con.close()
        return True
    except Exception as e:
        if con:
            con.close()
        print(f"Erro ao atualizar {campo}: {e}")
        return False

def atualizar_leads_em_lote(updates):
    """
    Atualiza múltiplos leads de uma vez (muito mais rápido).
    Recebe lista de tuplas: [(cnpj, status, valor, anotacao), ...]
    OTIMIZADO: Limpa cache após atualização.
    """
    con = get_connection()
    if not con: return False
    
    try:
        con.execute("BEGIN TRANSACTION")
        
        for cnpj, status, valor, anotacao in updates:
            con.execute("""
                UPDATE crm 
                SET status = ?, valor = ?, anotacao = ?, data_atualizacao = CURRENT_TIMESTAMP 
                WHERE cnpj = ?
            """, [status, valor, anotacao, cnpj])
        
        con.execute("COMMIT")
        con.close()
        
        # Limpa cache do Streamlit para forçar atualização
        _buscar_pipeline_interno.clear()
        
        return True
    except Exception as e:
        if con:
            con.execute("ROLLBACK")
            con.close()
        print(f"Erro ao atualizar em lote: {e}")
        return False

@st.cache_data(ttl=300, show_spinner=False)  # Cache por 5 minutos
def _buscar_pipeline_interno():
    """
    Função interna com cache do Streamlit.
    Cache de 5 minutos para evitar queries repetidas.
    """
    inicializar_crm() 

    con = get_connection()
    if not con: return pd.DataFrame()
    
    try:
        # Verifica se a tabela municipios existe
        tabela_municipios_existe = False
        try:
            con.execute("SELECT 1 FROM municipios LIMIT 1")
            tabela_municipios_existe = True
        except:
            pass
        
        # Query otimizada: primeiro busca do CRM, depois faz JOINs menores
        if tabela_municipios_existe:
            query = """
                SELECT 
                    c.cnpj,
                    COALESCE(e.nome_fantasia, 'N/A') AS nome_fantasia,
                    c.status,
                    COALESCE(c.valor, 0.0) AS valor,
                    COALESCE(c.anotacao, '') AS anotacao,
                    CASE 
                        WHEN e.ddd_1 IS NOT NULL AND e.telefone_1 IS NOT NULL 
                        THEN e.ddd_1 || ' ' || e.telefone_1 
                        ELSE '' 
                    END AS telefone,
                    COALESCE(e.correio_eletronico, '') AS email,
                    CASE 
                        WHEN m.descricao IS NOT NULL AND e.uf IS NOT NULL
                        THEN m.descricao || '-' || e.uf 
                        WHEN e.uf IS NOT NULL
                        THEN e.uf
                        ELSE 'N/A'
                    END AS local
                FROM crm c
                LEFT JOIN estabelecimentos e ON c.cnpj = (e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv)
                LEFT JOIN municipios m ON e.municipio = m.codigo
                ORDER BY c.data_atualizacao DESC
                LIMIT 10000
            """
        else:
            # Query sem JOIN com municipios (mais rápida)
            query = """
                SELECT 
                    c.cnpj,
                    COALESCE(e.nome_fantasia, 'N/A') AS nome_fantasia,
                    c.status,
                    COALESCE(c.valor, 0.0) AS valor,
                    COALESCE(c.anotacao, '') AS anotacao,
                    CASE 
                        WHEN e.ddd_1 IS NOT NULL AND e.telefone_1 IS NOT NULL 
                        THEN e.ddd_1 || ' ' || e.telefone_1 
                        ELSE '' 
                    END AS telefone,
                    COALESCE(e.correio_eletronico, '') AS email,
                    COALESCE(e.uf, 'N/A') AS local
                FROM crm c
                LEFT JOIN estabelecimentos e ON c.cnpj = (e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv)
                ORDER BY c.data_atualizacao DESC
                LIMIT 10000
            """
        
        df = con.execute(query).df()
        con.close()
        
        # Garante que as colunas existem mesmo se o JOIN falhar
        colunas_esperadas = ['cnpj', 'nome_fantasia', 'status', 'valor', 'anotacao', 'telefone', 'email', 'local']
        for col in colunas_esperadas:
            if col not in df.columns:
                df[col] = ''
        
        return df
    except Exception as e:
        # Se der erro, retorna DataFrame vazio para não quebrar a tela
        if con:
            con.close()
        print(f"Erro ao buscar pipeline: {e}")
        return pd.DataFrame()

def buscar_meu_pipeline():
    """
    Busca TODOS os leads que estão no CRM.
    OTIMIZADO: Usa cache interno + session_state para máxima performance.
    """
    return _buscar_pipeline_interno()
def excluir_do_crm(cnpj):
    """Remove um lead da tabela CRM pelo CNPJ."""
    con = get_connection()
    if not con: return False
    
    try:
        # Deleta a linha onde o CNPJ bate
        con.execute("DELETE FROM crm WHERE cnpj = ?", [cnpj])
        con.close()
        return True
    except Exception as e:
        if con:
            con.close()
        print(f"Erro ao excluir: {e}")
        return False

def excluir_leads_em_lote(cnpjs):
    """
    Remove múltiplos leads de uma vez (mais rápido).
    OTIMIZADO: Limpa cache após exclusão.
    """
    if not cnpjs:
        return True
        
    con = get_connection()
    if not con: return False
    
    try:
        con.execute("BEGIN TRANSACTION")
        for cnpj in cnpjs:
            con.execute("DELETE FROM crm WHERE cnpj = ?", [cnpj])
        con.execute("COMMIT")
        con.close()
        
        # Limpa cache do Streamlit para forçar atualização
        _buscar_pipeline_interno.clear()
        
        return True
    except Exception as e:
        if con:
            con.execute("ROLLBACK")
            con.close()
        print(f"Erro ao excluir em lote: {e}")
        return False