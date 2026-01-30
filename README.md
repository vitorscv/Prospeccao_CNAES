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

## Estrutura do Projeto

├── app_leads.py # Interface Streamlit
├── extrator.py # Extração e tratamento dos dados
├── utils_cnae.py # Funções auxiliares de CNAE
├── setup_banco.py # Setup básico do banco
├── setup_banco_completo.py # Setup completo (CNPJ + cidades)
├── update_cidades.py # Atualização da base de municípios
├── diagnostico.py # Diagnóstico da base de dados
├── auto_atualizacao_n8n.py # Automação com n8n
├── requirements.txt # Dependências
├── base_leads.db # Gerado automaticamente
└── dados/
└── ESTABELE*.zip # Dados da Receita Federal

yaml
Copiar código

---

## Requisitos

- Python **3.10+**
- Pip

Instalação das dependências:

```bash
pip install -r requirements.txt
Dados da Receita Federal
Baixe os arquivos ESTABELE.zip* em:

arduino
Copiar código
https://dadosabertos.rfb.gov.br/CNPJ/
Coloque os arquivos na pasta:

Copiar código
dados/
Setup do Banco de Dados
Setup completo (recomendado):

bash
Copiar código
python setup_banco_completo.py
Executar a Aplicação
bash
Copiar código
streamlit run app_leads.py
Acesse no navegador:

arduino
Copiar código
http://localhost:8501
Como Usar
Informe os CNAEs (separados por vírgula)

Selecione a UF

(Opcional) Selecione a cidade

Gere os leads

Exporte o CSV

Diagnóstico (Opcional)
bash
Copiar código
python diagnostico.py
Observações
Os dados utilizados são públicos (Receita Federal)

Uso indicado para prospecção e análise B2B

Respeite a LGPD ao entrar em contato com empresas

markdown
Copiar código

---

### Extras (opcional, mas deixa **nível profissional** 👇)

Se quiser, recomendo adicionar:
- `.gitignore` (Python padrão)
- `LICENSE`
- badges no topo (Python / Streamlit / DuckDB)