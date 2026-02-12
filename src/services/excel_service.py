"""
Serviço de exportação de leads para Excel.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

import pandas as pd

from src.models.lead import Lead, LeadScored


def gerar_excel_de_dtos(lista_dtos: List[Any]) -> bytes:
    """
    Gera Excel a partir de lista de DTOs (compatibilidade com código legado).
    
    Args:
        lista_dtos: Lista de objetos EmpresaDTO
        
    Returns:
        Bytes do arquivo Excel
    """
    output = BytesIO()
    
    # DTOs vira DataFrame
    # transforma a classe em um dicionário 
    from dataclasses import asdict
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


def gerar_excel_leads_enriquecidos(leads: List[Lead | LeadScored]) -> bytes:
    """
    Gera Excel com leads enriquecidos (novos campos + link Google Maps).
    
    Args:
        leads: Lista de objetos Lead ou LeadScored
        
    Returns:
        Bytes do arquivo Excel
    """
    output = BytesIO()
    
    # Converte leads para dicionários
    dados: List[Dict[str, Any]] = []
    for lead in leads:
        linha: Dict[str, Any] = {
            'Nome Fantasia': lead.nome_fantasia,
            'Razão Social': lead.razao_social or '',
            'CNPJ': lead.cnpj,
            'CNPJ Básico': lead.cnpj_basico,
            'Matriz/Filial': lead.matriz_filial,
            'CNAE': lead.cnae_principal,
            'Descrição CNAE': lead.descricao_cnae,
            'Telefone 1': lead.telefone_principal or '',
            'Telefone 2': lead.telefone_secundario or '',
            'E-mail': lead.email or '',
            'Logradouro': lead.endereco.logradouro if lead.endereco else '',
            'Número': lead.endereco.numero if lead.endereco else '',
            'Complemento': lead.endereco.complemento if lead.endereco else '',
            'Bairro': lead.endereco.bairro if lead.endereco else '',
            'CEP': lead.endereco.cep if lead.endereco else '',
            'Cidade': lead.cidade,
            'UF': lead.uf,
            'Data Início Atividade': lead.data_inicio_atividade.isoformat() if lead.data_inicio_atividade else '',
            'Anos de Atividade': lead.anos_atividade,
            'Link Google Maps': lead.link_maps,
        }
        
      
        if isinstance(lead, LeadScored):
            linha['Score'] = lead.score
            linha['Segmento'] = lead.segmento or ''
            linha['Razões Score'] = ' | '.join(lead.reasons)
        
        dados.append(linha)
    
    df = pd.DataFrame(dados)
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')
        
        workbook = writer.book
        worksheet = writer.sheets['Leads']
        

        formato = workbook.add_format({'num_format': '@', 'align': 'left', 'valign': 'vcenter'})
        
        for i, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).map(len).max(),
                len(col)
            )
            
            width = min(max_len + 2, 50)
            worksheet.set_column(i, i, width, formato)
    
    return output.getvalue()


def gerar_excel_roteiro(
    route_plan: Any,  
    incluir_links: bool = True
) -> bytes:
    """
    Gera Excel com roteiro de visitas.
    
    Args:
        route_plan: Objeto RoutePlan
        incluir_links: Se True, inclui links do Google Maps
        
    Returns:
        Bytes do arquivo Excel
    """
    output = BytesIO()
    
    
    dados: List[Dict[str, Any]] = []
    
    for dia_plan in route_plan.dias:
        for stop in dia_plan.stops:
            lead = stop.lead
            linha: Dict[str, Any] = {
                'Dia': dia_plan.dia,
                'Ordem': stop.ordem,
                'Empresa': lead.nome_fantasia,
                'CNPJ': lead.cnpj,
                'Endereço': lead.endereco.formatado if lead.endereco else '',
                'Cidade': lead.cidade,
                'UF': lead.uf,
                'Telefone': lead.telefone_principal or '',
                'Email': lead.email or '',
                'Score': lead.score if isinstance(lead, LeadScored) else 0,
                'Segmento': lead.segmento if isinstance(lead, LeadScored) else '',
            }
            
            if incluir_links:
                linha['Link Maps'] = lead.link_maps
            
            if stop.observacoes:
                linha['Observações'] = stop.observacoes
            
            dados.append(linha)
    
    df = pd.DataFrame(dados)
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Roteiro')
        
        workbook = writer.book
        worksheet = writer.sheets['Roteiro']
        
        # Formato texto
        formato = workbook.add_format({'num_format': '@', 'align': 'left', 'valign': 'vcenter'})
        
        
        for i, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).map(len).max(),
                len(col)
            )
            width = min(max_len + 2, 50)
            worksheet.set_column(i, i, width, formato)
        
        
        resumo_dados = []
        for dia_plan in route_plan.dias:
            resumo_dados.append({
                'Dia': dia_plan.dia,
                'Total Visitas': dia_plan.total_visitas,
                'Score Médio': f"{dia_plan.score_medio:.1f}",
                'Link Rota Dia': dia_plan.link_maps_rota if incluir_links else ''
            })
        
        df_resumo = pd.DataFrame(resumo_dados)
        df_resumo.to_excel(writer, index=False, sheet_name='Resumo')
        
        worksheet_resumo = writer.sheets['Resumo']
        for i, col in enumerate(df_resumo.columns):
            max_len = max(
                df_resumo[col].astype(str).map(len).max(),
                len(col)
            )
            width = min(max_len + 2, 50)
            worksheet_resumo.set_column(i, i, width, formato)
    
    return output.getvalue()