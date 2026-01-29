import os
import requests
from datetime import datetime
import pytz 

# --- CONFIGURAÇÕES ---
PASTA_DADOS = "dados/"
BASE_URL = ""    # URL da Receita
WEBHOOK_N8N = "" # Coloque seu Link do n8n aqui

# Lista de arquivos a verificar
arquivos_para_checar = [
    f"Estabelecimentos{i}.zip" for i in range(10) # Gera do 0 ao 9
]
# Se você tiver CNAES, SOCIOS, adicione aqui na lista também
# arquivos_para_checar.append("Cnaes.zip")

def obter_data_servidor(url):
    try:
        response = requests.head(url, timeout=10)
        if response.status_code == 200:
            data_str = response.headers.get('Last-Modified')
            # Converte data do servidor (GMT)
            data_obj = datetime.strptime(data_str, '%a, %d %b %Y %H:%M:%S %Z')
            return data_obj.replace(tzinfo=pytz.UTC)
    except:
        return None
    return None

def obter_data_local(caminho_arquivo):
    if not os.path.exists(caminho_arquivo):
        return None
    timestamp = os.path.getmtime(caminho_arquivo)
    # Converte data local para UTC para comparar igual
    return datetime.fromtimestamp(timestamp, pytz.UTC)

def vigiar_e_disparar():
    precisa_atualizar = False
    motivo = ""

    print(" Iniciando ronda nos arquivos da Receita...")

    for arquivo in arquivos_para_checar:
        url_arquivo = BASE_URL + arquivo
        caminho_local = os.path.join(PASTA_DADOS, arquivo)

        data_server = obter_data_servidor(url_arquivo)
        data_local = obter_data_local(caminho_local)

        if not data_server:
            print(f" Erro ao ler servidor para {arquivo}. Pulando.")
            continue

        if not data_local:
            print(f" Arquivo {arquivo} não existe aqui! ATUALIZAÇÃO NECESSÁRIA.")
            precisa_atualizar = True
            motivo = f"Arquivo faltante: {arquivo}"
            break 

        # Comparação: Se o servidor for mais novo que o local
        if data_server > data_local:
            print(f" Nova versão encontrada para {arquivo}!")
            print(f"    Server: {data_server} | 🏠 PC: {data_local}")
            precisa_atualizar = True
            motivo = f"Desatualizado: {arquivo}"
            break 
        else:
            print(f" {arquivo} está atualizado.")

   
    if precisa_atualizar:
        print(f"\n DISPARANDO N8N! Motivo: {motivo}")
        try:
            # Envia um sinal para o seu n8n começar a baixar
            requests.post(WEBHOOK_N8N, json={"acao": "atualizar", "motivo": motivo})
            print("Sinal enviado com sucesso!")
        except Exception as e:
            print(f"Erro ao chamar n8n: {e}")
    else:
        print("\n Tudo quieto. Nenhuma atualização necessária hoje.")

if __name__ == "__main__":
    vigiar_e_disparar()