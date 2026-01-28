import duckdb
import os

print("---  INICIANDO SETUP ---")

# 1. Limpeza
if os.path.exists("hunter_leads.db"):
    try:
        os.remove("hunter_leads.db")
        print(" ")
    except Exception as e:
        print(f" : {e}")
        exit()

con = duckdb.connect('hunter_leads.db')

# 2. Definição das Colunas
cols_cnae = {'col0': 'VARCHAR', 'col1': 'VARCHAR'}
cols_estab = {f'col{i}': 'VARCHAR' for i in range(30)}

# 3. Importar CNAES
print(" Processando CNAES...")
try:
    con.execute(f"""
        CREATE TABLE cnaes AS 
        SELECT col0 as codigo, col1 as descricao 
        FROM read_csv(
            'dados/cnaes.csv', 
            sep=';', 
            quote='"', 
            header=False,
            encoding='ISO_8859_1',
            auto_detect=False,
            columns={cols_cnae}
        )
    """)
    print(" Tabela CNAES criada!")
except Exception as e:
    print(f" Erro CNAES: {e}")

# 4. Importar Estabelecimentos (Com ignore_errors=true)
print(" Processando Estabelecimentos...")
try:
    con.execute(f"""
        CREATE TABLE estabelecimentos AS 
        SELECT 
            col0 as cnpj_basico,
            col1 as cnpj_ordem,
            col2 as cnpj_dv,
            col3 as identificador_matriz_filial,
            col4 as nome_fantasia,
            col5 as situacao_cadastral,
            col6 as data_situacao_cadastral,
            col7 as motivo_situacao_cadastral,
            col8 as nome_cidade_exterior,
            col9 as pais,
            col10 as data_inicio_atividade,
            col11 as cnae_principal,
            col12 as cnae_secundario,
            col13 as tipo_logradouro,
            col14 as logradouro,
            col15 as numero,
            col16 as complemento,
            col17 as bairro,
            col18 as cep,
            col19 as uf,
            col20 as municipio,
            col21 as ddd_1,
            col22 as telefone_1,
            col23 as ddd_2,
            col24 as telefone_2,
            col25 as ddd_fax,
            col26 as fax,
            col27 as correio_eletronico,
            col28 as situacao_especial,
            col29 as data_situacao_especial
        FROM read_csv(
            'dados/estabelecimentos.csv', 
            sep=';', 
            quote='"', 
            header=False, 
            encoding='ISO_8859_1',
            auto_detect=False,
            ignore_errors=true,
            columns={cols_estab}
        )
    """)
    print(" Tabela Estabelecimentos criada (linhas ruins foram puladas)!")

except Exception as e:
    print(f" Erro Estabelecimentos: {e}")

# 5. Conferência
print("\n Conferência Final:")
try:
    # Mostra um CNAE para garantir
    cnae = con.execute("SELECT * FROM cnaes LIMIT 1").fetchone()
    print(f" Exemplo CNAE: {cnae}")
    
    # Conta quantos CNPJs entraram
    qtd = con.execute("SELECT COUNT(*) FROM estabelecimentos").fetchone()[0]
    print(f" Total de Empresas Importadas: {qtd}")
except:
    print(" Erro na conferência (mas se as tabelas foram criadas, tá valendo).")

con.close()
print("\n Pode rodar o 'streamlit run app_leads.py'.")