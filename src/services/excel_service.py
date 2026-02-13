"""
Serviço de exportação de leads para Excel.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

import pandas as pd
from typing import Any


def gerar_excel_de_dtos(lista_dtos: List[Any] | pd.DataFrame) -> bytes:
    """
    Gera Excel a partir de lista de DTOs (compatibilidade com código legado).
    
    Args:
        lista_dtos: Lista de objetos EmpresaDTO
        
    Returns:
        Bytes do arquivo Excel
    """
    output = BytesIO()
    
    # Aceita: pandas.DataFrame, lista de dicionários, lista de dataclasses/objetos
    if isinstance(lista_dtos, pd.DataFrame):
        df = lista_dtos.copy()
    else:
        # transforma a classe/obj em um dicionário quando possível
        dados = []
        for e in lista_dtos:
            if isinstance(e, dict):
                dados.append(e)
            else:
                try:
                    # dataclass -> asdict
                    from dataclasses import asdict, is_dataclass
                    if is_dataclass(e):
                        dados.append(asdict(e))
                    else:
                        # objeto genérico: tenta usar __dict__
                        dados.append(getattr(e, "__dict__", {}))
                except Exception:
                    # fallback: str representation
                    dados.append({})
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


def gerar_excel_leads_enriquecidos(leads: List[Any]) -> bytes:
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
        # suporta dicts ou objetos com atributos
        def attr(o, name, default=''):
            if isinstance(o, dict):
                return o.get(name, default) or default
            return getattr(o, name, default) or default

        endereco = attr(lead, 'endereco', None)
        linha: Dict[str, Any] = {
            'Nome Fantasia': attr(lead, 'nome_fantasia'),
            'Razão Social': attr(lead, 'razao_social'),
            'CNPJ': attr(lead, 'cnpj'),
            'CNPJ Básico': attr(lead, 'cnpj_basico'),
            'Matriz/Filial': attr(lead, 'matriz_filial'),
            'CNAE': attr(lead, 'cnae_principal'),
            'Descrição CNAE': attr(lead, 'descricao_cnae'),
            'Telefone 1': attr(lead, 'telefone_principal'),
            'Telefone 2': attr(lead, 'telefone_secundario'),
            'E-mail': attr(lead, 'email'),
            'Logradouro': getattr(endereco, 'logradouro', '') if endereco else '',
            'Número': getattr(endereco, 'numero', '') if endereco else '',
            'Complemento': getattr(endereco, 'complemento', '') if endereco else '',
            'Bairro': getattr(endereco, 'bairro', '') if endereco else '',
            'CEP': getattr(endereco, 'cep', '') if endereco else '',
            'Cidade': attr(lead, 'cidade'),
            'UF': attr(lead, 'uf'),
            'Data Início Atividade': getattr(attr(lead, 'data_inicio_atividade', None), 'isoformat', lambda: '')() if attr(lead, 'data_inicio_atividade', None) else '',
            'Anos de Atividade': attr(lead, 'anos_atividade'),
            'Link Google Maps': attr(lead, 'link_maps'),
        }

        # Se for dict com score ou objeto com score, adiciona
        score = attr(lead, 'score', None)
        if score is not None:
            linha['Score'] = score
            linha['Segmento'] = attr(lead, 'segmento')
            reasons = attr(lead, 'reasons', None)
            if isinstance(reasons, (list, tuple)):
                linha['Razões Score'] = ' | '.join(reasons)

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
            # helper to get attr or dict key
            def a(o, name, default=''):
                if isinstance(o, dict):
                    return o.get(name, default) or default
                return getattr(o, name, default) or default

            linha: Dict[str, Any] = {
                'Dia': dia_plan.dia,
                'Ordem': stop.ordem,
                'Empresa': a(lead, 'nome_fantasia'),
                'CNPJ': a(lead, 'cnpj'),
                'Endereço': getattr(a(lead, 'endereco', None), 'formatado', '') if a(lead, 'endereco', None) else '',
                'Cidade': a(lead, 'cidade'),
                'UF': a(lead, 'uf'),
                'Telefone': a(lead, 'telefone_principal'),
                'Email': a(lead, 'email'),
                'Score': a(lead, 'score', 0),
                'Segmento': a(lead, 'segmento', ''),
            }
            
            if incluir_links:
                linha['Link Maps'] = a(lead, 'link_maps')
            
            if getattr(stop, 'observacoes', None):
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