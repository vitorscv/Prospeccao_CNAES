from src.database.connection import get_connection
import streamlit as st
import pandas as pd

def inicializar_crm():
    """Cria a tabela CRM e índices para performance."""
    con = get_connection()
    if not con: return
    try:
        
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
        
       
        try:
            con.execute("CREATE INDEX IF NOT EXISTS idx_crm_data_atualizacao ON crm(data_atualizacao DESC)")
        except:
            pass  
        
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
       
        dados = [(l['cnpj'], 'Novo', '', 0.0) for l in lista_leads]
        
       
        con.executemany("""
            INSERT OR IGNORE INTO crm (cnpj, status, anotacao, valor) 
            VALUES (?, ?, ?, ?)
        """, dados)
        
        con.close()
        
       
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
       
        campos_permitidos = ['status', 'valor', 'anotacao']
        if campo not in campos_permitidos:
            return False
        
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
        
        
        _buscar_pipeline_interno.clear()
        
        return True
    except Exception as e:
        if con:
            con.execute("ROLLBACK")
            con.close()
        print(f"Erro ao atualizar em lote: {e}")
        return False

@st.cache_data(ttl=300, show_spinner=False)  
def _buscar_pipeline_interno():
    """
    Função interna com cache do Streamlit.
    Cache de 5 minutos para evitar queries repetidas.
    OTIMIZADO: Query mais rápida, apenas colunas necessárias.
    """
    inicializar_crm() 

    con = get_connection()
    if not con: return pd.DataFrame()
    
    try:
        
        
        query_crm = """
            SELECT 
                cnpj,
                status,
                valor,
                anotacao,
                data_atualizacao
            FROM crm
            ORDER BY data_atualizacao DESC
            LIMIT 10000
        """
        
        df_crm = con.execute(query_crm).df()
        
        if df_crm.empty:
            con.close()
            return pd.DataFrame()
        
        
        
        if len(df_crm) > 0:
            
            query_estab = """
                SELECT 
                    (e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv) AS cnpj,
                    e.nome_fantasia,
                    e.ddd_1,
                    e.telefone_1,
                    e.correio_eletronico AS email,
                    e.uf,
                    e.municipio
                FROM estabelecimentos e
                INNER JOIN (
                    SELECT cnpj FROM crm ORDER BY data_atualizacao DESC LIMIT 10000
                ) c ON (e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv) = c.cnpj
            """
            
            try:
                df_estab = con.execute(query_estab).df()
            except Exception as e:
                
                print(f"Erro ao buscar estabelecimentos: {e}")
                df_estab = pd.DataFrame()
        else:
            df_estab = pd.DataFrame()
        
        
        df_municipios = pd.DataFrame()
        try:
            if not df_estab.empty and 'municipio' in df_estab.columns:
                municipios_codigos = df_estab['municipio'].dropna().unique().tolist()
                if municipios_codigos:
                    query_mun = f"""
                        SELECT codigo, descricao
                        FROM municipios
                        WHERE codigo IN ({','.join([f"'{m}'" for m in municipios_codigos[:500]])})
                    """
                    try:
                        df_municipios = con.execute(query_mun).df()
                    except:
                        pass
        except:
            pass
        
        con.close()
        
        
        df = df_crm.copy()
        
        if not df_estab.empty:
            df = df.merge(df_estab, on='cnpj', how='left')
            
            
            df['telefone'] = df.apply(
                lambda row: f"{row['ddd_1']} {row['telefone_1']}" 
                if pd.notna(row.get('ddd_1')) and pd.notna(row.get('telefone_1')) 
                else '', axis=1
            )
            
            
            if not df_municipios.empty and 'municipio' in df.columns:
                df = df.merge(df_municipios, left_on='municipio', right_on='codigo', how='left')
                df['local'] = df.apply(
                    lambda row: f"{row['descricao']}-{row['uf']}" 
                    if pd.notna(row.get('descricao')) and pd.notna(row.get('uf'))
                    else (row['uf'] if pd.notna(row.get('uf')) else 'N/A'), axis=1
                )
            else:
                df['local'] = df['uf'].fillna('N/A')
        else:
            
            df['nome_fantasia'] = 'N/A'
            df['telefone'] = ''
            df['email'] = ''
            df['local'] = 'N/A'
        
        
        colunas_esperadas = ['cnpj', 'nome_fantasia', 'status', 'valor', 'anotacao', 'telefone', 'email', 'local']
        for col in colunas_esperadas:
            if col not in df.columns:
                df[col] = ''
        
        
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0.0)
        df['status'] = df['status'].fillna('Novo')
        df['anotacao'] = df['anotacao'].fillna('')
        
        return df[colunas_esperadas]  
        
    except Exception as e:
        
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
        
        
        _buscar_pipeline_interno.clear()
        
        return True
    except Exception as e:
        if con:
            con.execute("ROLLBACK")
            con.close()
        print(f"Erro ao excluir em lote: {e}")
        return False