# Gerador de Leads Estratégicos

Aplicação Streamlit para gerar listas de prospecção baseadas em CNAE, Estado e Cidade.

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
   - Baixe o arquivo `ESTABELE0.zip` (ou outro arquivo ESTABELE)
   - Coloque o arquivo na pasta `dados/`

2. **Estrutura de pastas:**
```
Prospeccao_CNAES/
├── extrator.py
├── requirements.txt
├── dados/
│   └── ESTABELE0.zip  ← Coloque o arquivo aqui
└── base_leads.db      ← Será criado automaticamente
```

## Execução

Execute o aplicativo:
```powershell
streamlit run extrator.py
```

O aplicativo abrirá no navegador em `http://localhost:8501`

## Uso

1. Informe os CNAEs desejados (separados por vírgula)
2. Selecione o Estado (UF)
3. (Opcional) Informe o código do município
4. Clique em "Gerar Lista de Prospecção"
5. Baixe o resultado em CSV
