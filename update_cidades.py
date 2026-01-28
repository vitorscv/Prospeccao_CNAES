import duckdb
import pandas as pd
import os
import zipfile

print("--- 🐼 ATUALIZAÇÃO VIA PANDAS (MODO ULTRA ROBUSTO) ---")

caminho_zip = "dados/MUNICCSV.zip"
pasta_dados = "dados/"

if not os.path.exists(caminho_zip):
    print(f"❌ O arquivo {caminho_zip} não existe!")
    exit()

arquivo_extraido = None
con = None

try:
    # 1. Extração Manual
    print("📦 1. Extraindo ZIP...")
    with zipfile.ZipFile(caminho_zip, 'r') as z:
        nome_arquivo = z.namelist()[0]
        z.extract(nome_arquivo, pasta_dados)
        arquivo_extraido = os.path.join(pasta_dados, nome_arquivo)
    
    # 2. Leitura com Pandas (A mágica acontece aqui)
    print("🐼 2. Pandas lendo e limpando CSV...")
    # on_bad_lines='skip': Pula linhas quebradas
    # dtype=str: Garante que o código '001' não vire '1'
    # encoding='cp1252': O padrão do Windows/Receita
    df = pd.read_csv(
        arquivo_extraido, 
        sep=';', 
        header=None, 
        names=['codigo', 'descricao'],
        dtype=str,
        encoding='cp1252', 
        on_bad_lines='skip' 
    )
    
    print(f"   -> Lidas {len(df)} cidades com sucesso via Pandas.")

    # 3. Inserção no DuckDB
    print("🔌 3. Salvando no Banco de Dados...")
    con = duckdb.connect('hunter_leads.db')
    con.execute("DROP TABLE IF EXISTS municipios")
    
    # O DuckDB aceita DataFrames do Pandas direto!
    con.execute("CREATE TABLE municipios AS SELECT * FROM df")
    
    print("✅ SUCESSO TOTAL! Tabela criada.")
    
    # Teste
    teste = con.execute("SELECT descricao FROM municipios WHERE descricao LIKE '%FEIRA DE SANTANA%'").fetchone()
    print(f"🔎 Teste: {teste[0] if teste else 'Erro no teste'}")

    print("\n🚀 PODE RODAR O SITE: py -m streamlit run app_leads.py")

except Exception as e:
    print(f"❌ ERRO: {e}")

finally:
    if con:
        con.close()
    # Limpa a bagunça
    if arquivo_extraido and os.path.exists(arquivo_extraido):
        try:
            os.remove(arquivo_extraido)
        except:
            pass