from src.database.connection import get_connection
import streamlit as st
import pandas as pd


# =====================================================
# INICIALIZAÇÃO DO CRM
# =====================================================
def inicializar_crm():
    """Cria a tabela CRM e índices para performance."""
    con = get_connection()
    if not con:
        return

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

        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_crm_data_atualizacao 
            ON crm(data_atualizacao DESC)
        """)

    finally:
        con.close()


# =====================================================
# INSERÇÃO
# =====================================================
def adicionar_lista_ao_crm(lista_leads):
    """Salva apenas o CNPJ no CRM."""
    inicializar_crm()
    con = get_connection()
    if not con:
        return False

    try:
        dados = [(l['cnpj'],) for l in lista_leads]

        con.executemany("""
            INSERT OR IGNORE INTO crm (cnpj)
            VALUES (?)
        """, dados)

        _buscar_pipeline_interno.clear()
        return True

    except Exception as e:
        st.error(f"Erro ao importar: {e}")
        return False

    finally:
        con.close()


# =====================================================
# ATUALIZAÇÃO
# =====================================================
def atualizar_lead_crm(cnpj, campo, valor):
    campos_permitidos = ['status', 'valor', 'anotacao']
    if campo not in campos_permitidos:
        return False

    con = get_connection()
    if not con:
        return False

    try:
        con.execute(
            f"""
            UPDATE crm 
            SET {campo} = ?, data_atualizacao = CURRENT_TIMESTAMP 
            WHERE cnpj = ?
            """,
            [valor, cnpj]
        )

        _buscar_pipeline_interno.clear()
        return True

    finally:
        con.close()


# =====================================================
# PIPELINE (CACHEADO)
# =====================================================
@st.cache_data(ttl=300, show_spinner=False)
def _buscar_pipeline_interno():
    """Busca o pipeline de leads."""
    inicializar_crm()
    con = get_connection()
    if not con:
        return pd.DataFrame()

    try:
        # 1️⃣ Busca só o CRM (rápido)
        df_crm = con.execute("""
            SELECT
                cnpj,
                status,
                valor,
                anotacao
            FROM crm
            ORDER BY data_atualizacao DESC
            LIMIT 5000
        """).df()

        if df_crm.empty:
            return pd.DataFrame()

        # 2️⃣ Busca dados complementares
        df_estab = con.execute("""
            SELECT
                (cnpj_basico || cnpj_ordem || cnpj_dv) AS cnpj,
                nome_fantasia,
                ddd_1,
                telefone_1,
                correio_eletronico AS email,
                uf
            FROM estabelecimentos
            WHERE (cnpj_basico || cnpj_ordem || cnpj_dv) IN (
                SELECT cnpj FROM crm LIMIT 5000
            )
        """).df()

        # 3️⃣ Merge em memória (mais rápido)
        df = df_crm.merge(df_estab, on='cnpj', how='left')

        # 4️⃣ Campos derivados
        df['telefone'] = df.apply(
            lambda r: f"{r['ddd_1']} {r['telefone_1']}"
            if pd.notna(r['ddd_1']) and pd.notna(r['telefone_1'])
            else '',
            axis=1
        )

        df['nome_fantasia'] = df['nome_fantasia'].fillna('N/A')
        df['email'] = df['email'].fillna('')
        df['valor'] = pd.to_numeric(df['valor']).fillna(0.0)
        df['status'] = df['status'].fillna('Novo')
        df['anotacao'] = df['anotacao'].fillna('')

        return df[
            ['cnpj', 'nome_fantasia', 'status', 'valor', 'anotacao', 'telefone', 'email', 'uf']
        ]

    except Exception as e:
        print(f"Erro no pipeline: {e}")
        return pd.DataFrame()

    finally:
        con.close()


def buscar_meu_pipeline():
    """Wrapper público do pipeline."""
    return _buscar_pipeline_interno()


# =====================================================
# EXCLUSÃO
# =====================================================
def excluir_do_crm(cnpj):
    con = get_connection()
    if not con:
        return False

    try:
        con.execute("DELETE FROM crm WHERE cnpj = ?", [cnpj])
        _buscar_pipeline_interno.clear()
        return True

    finally:
        con.close()
# =====================================================
# ATUALIZAÇÃO EM LOTE
# =====================================================
def atualizar_leads_em_lote(updates):
    """
    Atualiza vários leads de uma vez.
    updates = [(cnpj, status, valor, anotacao), ...]
    """
    if not updates:
        return True

    con = get_connection()
    if not con:
        return False

    try:
        con.execute("BEGIN TRANSACTION")

        for cnpj, status, valor, anotacao in updates:
            con.execute("""
                UPDATE crm
                SET
                    status = ?,
                    valor = ?,
                    anotacao = ?,
                    data_atualizacao = CURRENT_TIMESTAMP
                WHERE cnpj = ?
            """, [status, valor, anotacao, cnpj])

        con.execute("COMMIT")
        _buscar_pipeline_interno.clear()
        return True

    except Exception as e:
        con.execute("ROLLBACK")
        print(f"Erro ao atualizar em lote: {e}")
        return False

    finally:
        con.close()


# =====================================================
# EXCLUSÃO EM LOTE
# =====================================================
def excluir_leads_em_lote(cnpjs):
    """
    Remove vários leads de uma vez.
    """
    if not cnpjs:
        return True

    con = get_connection()
    if not con:
        return False

    try:
        con.execute("BEGIN TRANSACTION")

        for cnpj in cnpjs:
            con.execute("DELETE FROM crm WHERE cnpj = ?", [cnpj])

        con.execute("COMMIT")
        _buscar_pipeline_interno.clear()
        return True

    except Exception as e:
        con.execute("ROLLBACK")
        print(f"Erro ao excluir em lote: {e}")
        return False

    finally:
        con.close()
