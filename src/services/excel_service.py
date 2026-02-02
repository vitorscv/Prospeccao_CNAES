from io import BytesIO
import pandas as pd
from dataclasses import asdict

def gerar_excel_de_dtos(lista_dtos):
    output = BytesIO()
    
    # DTOs vira DataFrame
    # transforma a classe em um dicionário 
    dados = [asdict(e) for e in lista_dtos]
    df = pd.DataFrame(dados)
    
    # Fortama planilha
    mapa_colunas = {
        'nome_fantasia': 'Nome Fantasia', 
        'cnpj': 'CNPJ',
        'telefone_principal': 'Telefone 1',
        'telefone_secundario': 'Telefone 2',
        'email': 'E-mail',
        'cidade': 'Cidade',
        'uf': 'UF',
        'cnae': 'CNAE'
    }
    
    df = df.rename(columns=mapa_colunas)

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')
        
        
        workbook = writer.book
        worksheet = writer.sheets['Leads']
        formato = workbook.add_format({'num_format': '@', 'align': 'left', 'valign': 'vcenter'})
        
        for i, col in enumerate(df.columns):
            tam = max(df[col].astype(str).map(len).max(), len(col))
            worksheet.set_column(i, i, tam + 2, formato)
            
    return output.getvalue()