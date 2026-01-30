# Prospecção de Leads por CNAE

Ferramenta em **Python** para prospecção de empresas brasileiras usando **CNAE, UF e cidade**, a partir de dados públicos da Receita Federal (CNPJ).  
Os dados são armazenados localmente em **DuckDB** e os resultados podem ser exportados em **CSV**.

---

## Funcionalidades

- Filtro por CNAE principal  
- Filtro por UF e município  
- Banco local DuckDB  
- Processamento de arquivos grandes  
- Exportação de leads em CSV  
- Interface web com Streamlit  
- Scripts de diagnóstico e atualização  
- Automação via n8n  

---
2. **Estrutura de pastas:**
```
Prospeccao_CNAES/
├── app_leads.py
├── extrator.py
├── utils_cnae.py
├── setup_banco.py
├── setup_banco_completo.py
├── update_cidades.py
├── diagnostico.py
├── auto_atualizacao_n8n.py
├── requirements.txt
├── base_leads.db
└── dados/
    └── ESTABELE*.zip
```


---

## Requisitos

- Python **3.10+**
- Pip

## Instalação

1. Instale as dependências:
```powershell
py -m pip install --user streamlit duckdb pandas
```

Ou usando o requirements.txt:
```powershell
py -m pip install --user -r requirements.txt
```

## Configuração

1. **Baixe o arquivo de dados da Receita Federal:**
   - Acesse: https://dadosabertos.rfb.gov.br/CNPJ/
   - Baixe o arquivo `ESTABELECIMENTOS*.zip` 
   - Coloque o arquivo na pasta `dados/`


## Execução

Execute o aplicativo:
```powershell
streamlit run extrator.py
```

O aplicativo abrirá no navegador em `http://localhost:8501`


##Setup do Banco de Dados
Setup completo (recomendado):

python setup_banco_completo.py

##Executar a Aplicação

streamlit run app_leads.py

Acesse no navegador:

http://localhost:8501

##Como Usar

Informe os CNAEs (separados por vírgula)
Selecione a UF
(Opcional) Selecione a cidade
Gere os leads
Exporte o CSV

##Diagnóstico (Opcional)

python diagnostico.py

##Observações

Os dados utilizados são públicos (Receita Federal)
Uso indicado para prospecção e análise B2B
Respeite a LGPD ao entrar em contato com empresas







