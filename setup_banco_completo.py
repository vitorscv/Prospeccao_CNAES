import duckdb
import pandas as pd
import os
import time
import zipfile

print("--- 🛡️ IMPORTAÇÃO BLINDADA (VIA PANDAS CHUNKS) ---")

# 1. Configuração Inicial
db_file = 'hunter_leads.db'
if os.path.exists(db_file):
    print("⚠️  ATENÇÃO: O arquivo hunter_leads.db já existe!")
    print("    Para evitar duplicidade, pare agora e apague o arquivo db.")
    print("    Continuando em 5 segundos...")
    time.sleep(5)

con = duckdb.connect(db_file)

# 2. Definindo as Colunas (Importante para o Pandas não se perder)
colunas_empresas = [
    'cnpj_basico', 'cnpj_ordem', 'cnpj_dv', 'matriz_filial', 'nome_fantasia',
    'situacao_cadastral', 'data_situacao_cadastral', 'motivo_situacao_cadastral',
    'nome_cidade_exterior', 'pais', 'data_inicio_atividade', 'cnae_principal',
    'cnae_secundaria', 'tipo_logradouro', 'logradouro', 'numero', 'complemento',
    'bairro', 'cep', 'uf', 'municipio', 'ddd_1', 'telefone_1', 'ddd_2',
    'telefone_2', 'ddd_fax', 'fax', 'correio_eletronico', 'situacao_especial',
    'data_situacao_especial'
]

# ==============================================================================
# PARTE 1: CNAES (Rápido)
# ==============================================================================
print("\n📚 1. Importando CNAEs...")
try:
    con.execute("DROP TABLE IF EXISTS cnaes")
    # Lê usando Pandas para garantir encoding correto
    with zipfile.ZipFile("dados/CNAECNV.zip") as z:
        with z.open(z.namelist()[0]) as f:
            df_cnae = pd.read_csv(f, sep=';', encoding='latin1', header=None, names=['codigo', 'descricao'], dtype=str)
            con.execute("CREATE TABLE cnaes AS SELECT * FROM df_cnae")
            print(f"   ✅ {len(df_cnae)} CNAEs importados.")
except Exception as e:
    print(f"   ❌ Erro CNAE: {e}")

# ==============================================================================
# PARTE 2: EMPRESAS (0 a 9) - O PESADO
# ==============================================================================
print("\n🏭 2. Importando Empresas (Modo Chunk - Isso é robusto)...")

# Cria a tabela vazia primeiro
con.execute(f"CREATE TABLE IF NOT EXISTS estabelecimentos ({', '.join([f'{c} VARCHAR' for c in colunas_empresas])})")

total_geral = 0
inicio_geral = time.time()

for i in range(10):
    arquivo_zip = f"dados/ESTABELE{i}.zip"
    
    if os.path.exists(arquivo_zip):
        print(f"   📦 Abrindo {arquivo_zip}...", end=" ")
        
        try:
            with zipfile.ZipFile(arquivo_zip) as z:
                # Pega o nome do arquivo CSV dentro do ZIP
                nome_csv = z.namelist()[0]
                
                # Abre o arquivo CSV dentro do ZIP sem extrair pro HD (economiza espaço)
                with z.open(nome_csv) as f:
                    
                    # LER EM PEDAÇOS (CHUNKS) DE 100.000 LINHAS
                    # on_bad_lines='skip': Pula linha com erro em vez de travar
                    chunks = pd.read_csv(
                        f, 
                        sep=';', 
                        encoding='latin1', 
                        header=None, 
                        names=colunas_empresas, 
                        dtype=str, 
                        quotechar='"',
                        chunksize=100000, 
                        on_bad_lines='skip' 
                    )
                    
                    contador_arquivo = 0
                    print(f"\n      ↳ Processando blocos:", end=" ")
                    
                    for chunk in chunks:
                        # Joga o bloco do Pandas para o DuckDB
                        con.execute("INSERT INTO estabelecimentos SELECT * FROM chunk")
                        contador_arquivo += len(chunk)
                        print(".", end="", flush=True) # Barra de progresso visual
                    
                    total_geral += contador_arquivo
                    print(f" OK! (+{contador_arquivo:,} empresas)")

        except Exception as e:
            print(f"\n    Erro crítico no arquivo {i}: {e}")
            
    else:
        print(f"     Arquivo {arquivo_zip} não encontrado.")

# ==============================================================================
# FINALIZAÇÃO
# ==============================================================================
tempo_total = (time.time() - inicio_geral) / 60
print(f"\n FIM! Processamento concluído em {tempo_total:.1f} minutos.")
print(f" Total de empresas importadas: {total_geral:,}")

con.close()