import os

def ler_topo_arquivo(caminho, linhas=3):
    print(f"\n Lendo arquivo: {caminho} ")
    if not os.path.exists(caminho):
        print(" Arquivo não encontrado!")
        return

    try:
        with open(caminho, 'r', encoding='ISO-8859-1') as f:
            for i in range(linhas):
                print(f"Linha {i+1}: {repr(f.readline())}")
    except Exception as e:
        print(f"Erro ao ler: {e}")

# Executa o diagnóstico
print(" INICIANDO DIAGNÓSTICO DOS ARQUIVOS CSV...")
ler_topo_arquivo('dados/estabelecimentos.csv')
ler_topo_arquivo('dados/cnaes.csv')