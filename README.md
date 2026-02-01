# Hunter Leads - Enterprise

Ferramenta profissional em **Python** para inteligência de mercado e prospecção B2B usando **CNAE, UF e Cidade**. 
Utiliza **DuckDB** para alta performance em grandes volumes de dados e **Streamlit** para a interface visual.
Os resultados são exportados em **Excel (.xlsx)** formatado e pronto para uso.

## Funcionalidades

- **Arquitetura Modular:** Código organizado em Camadas (Database, Service, DTO).
- **Busca Inteligente:** Filtro de cidades dinâmico (carrega apenas cidades com empresas do estado).
- **Descobridor de CNAE:** Pesquisa por palavras-chave (ex: "Gesso", "TI").
- **Exportação Premium:** Gera planilhas Excel com colunas ajustadas automaticamente.
- **Dashboard de Mercado:** Gráficos de ranking das cidades com mais oportunidades.
- **Segurança de Memória:** Limite automático de registros para proteger o computador.
- **Banco Local:** DuckDB (Zero configuração de servidor).

---
## Estrutura de pastas

```text
HunterLeads/
├── app.py                   <-- Novo arquivo principal
├── hunter_leads.db          <-- Seu banco de dados DuckDB
├── requirements.txt         <-- Dependências (incluindo xlsxwriter)
├── setup_banco_completo.py  <-- Script de criação do banco
├── extrator.py              <-- Script de processamento bruto
├── auto_atualizacao_n8n.py  <-- Automação externa
├── src/                     <-- NOVA ARQUITETURA
│   ├── database/            # Conexão e Queries SQL
│   ├── models/              # DTOs (Definição de dados)
│   └── services/            # Lógica de Excel
└── dados/
    └── .csv ou .zip da Receita
```

## Requisitos

- **Python 3.10+**
- **Pip**
- **Bibliotecas:** streamlit, duckdb, pandas, xlsxwriter

## Instalação

Instale as dependências:

```powershell
pip install -r requirements.txt
```

> **Nota:** Certifique-se de que o xlsxwriter está no arquivo requirements.txt

## Configuração Inicial (Apenas na primeira vez)

### Baixe os dados da Receita Federal:

1. Acesse: https://dadosabertos.rfb.gov.br/CNPJ/
2. Baixe o arquivo `ESTABELECIMENTOS*.zip`
3. Coloque na pasta `dados/`

### Crie o Banco de Dados:

```powershell
python setup_banco_completo.py
```

## Execução

Execute a aplicação (agora pelo app.py):

```powershell
streamlit run app.py
```

O sistema abrirá automaticamente em http://localhost:8501

## Como Usar

1. **Descobrir CNAE:** Use a aba 1 para pesquisar o código da atividade (ex: "Farmácia").
2. **Filtrar:**
   - Selecione o Estado (UF).
   - Selecione a Cidade (a lista carrega apenas cidades daquele estado).
   - Cole os códigos CNAE na barra lateral.
3. **Gerar Leads:** Clique em 🚀 GERAR LISTA para ver a tabela e baixar o Excel formatado.
4. **Analisar Mercado:** Use a aba "Dashboard" para ver gráficos das cidades com mais empresas.

## Diagnóstico e Manutenção

Para testar a conexão com o banco ou limpar tabelas (se necessário):

```powershell
python setup_banco_completo.py
```

> **Nota:** O script setup verifica se o banco existe antes de criar.

## Observações

- **Dados Públicos:** Fonte original "Dados Abertos da Receita Federal".
- **LGPD:** Utilize os dados respeitando as leis de proteção de dados e privacidade.
- **Performance:** O limite de 50.000 linhas existe para evitar travamento do navegador (limitação do frontend, não do banco).