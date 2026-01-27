import duckdb
import os
import zipfile

DB_NAME = 'hunter_leads.db'
PASTA_DADOS = 'dados'

# Definição exata das 30 colunas (c0 a c29)
colunas_estabele = {f'c{i}': 'VARCHAR' for i in range(30)}
colunas_cnae = {'codigo': 'VARCHAR', 'descricao': 'VARCHAR'}

def extrair_se_necessario(nome_zip, nome_csv):
    caminho_csv = os.path.join(PASTA_DADOS, nome_csv)
    if os.path.exists(caminho_csv):
        print(f" {nome_csv} já existe. Pulando extração.")
        return True
    
    caminho_zip = os.path.join(PASTA_DADOS, nome_zip)
    if not os.path.exists(caminho_zip):
        print(f" {nome_zip} não encontrado.")
        return False

    print(f" Extraindo {nome_zip}...")
    try:
        with zipfile.ZipFile(caminho_zip, 'r') as z:
            nome_original = z.namelist()[0]
            z.extract(nome_original, PASTA_DADOS)
            os.rename(os.path.join(PASTA_DADOS, nome_original), caminho_csv)
            print(f" Extraído: {nome_csv}")
            return True
    except Exception as e:
        print(f" Erro na extração: {e}")
        return False

def criar_banco():
    print("--- INICIANDO SETUP (MODO AUTO_DETECT=FALSE) ---")
    
    tem_estabele = extrair_se_necessario('ESTABELE0.zip', 'estabelecimentos.csv')
    tem_cnae = extrair_se_necessario('CNAECNV.zip', 'cnaes.csv')

    con = duckdb.connect(DB_NAME)

    # 1. Carregar Estabelecimentos
    if tem_estabele:
        print(" Importando estabelecimentos.csv...")
        try:
            # O SEGREDO ESTÁ AQUI: auto_detect=False
            con.execute(f"""
                CREATE OR REPLACE TABLE estabelecimentos AS 
                SELECT 
                    c0 || c1 || c2 as cnpj,
                    c4 as nome_fantasia,
                    c11 as cnae_principal,
                    c19 as uf,
                    c20 as municipio,
                    '(' || c21 || ') ' || c22 as telefone,
                    c27 as email
                FROM read_csv(
                    'dados/estabelecimentos.csv', 
                    delim=';', 
                    header=False, 
                    columns={colunas_estabele}, 
                    encoding='ISO8859_1', 
                    quote='"',
                    escape='"',
                    auto_detect=False,
                    null_padding=True
                )
            """)
            print(" Tabela 'estabelecimentos' criada com sucesso!")
        except Exception as e:
            print(f" Erro Estabelecimentos: {e}")

    # 2. Carregar CNAEs
    if tem_cnae:
        print(" Importando cnaes.csv...")
        try:
            con.execute(f"""
                CREATE OR REPLACE TABLE cnaes AS 
                SELECT codigo, descricao 
                FROM read_csv(
                    'dados/cnaes.csv', 
                    delim=';', 
                    header=False, 
                    columns={colunas_cnae}, 
                    encoding='ISO8859_1', 
                    quote='"',
                    escape='"',
                    auto_detect=False,
                    null_padding=True
                )
            """)
            print(" Tabela 'cnaes' criada com sucesso!")
        except Exception as e:
            print(f" Erro CNAEs: {e}")

    con.close()
    print("\n FIM! Agora TEM que ir.")

if __name__ == "__main__":
    criar_banco()