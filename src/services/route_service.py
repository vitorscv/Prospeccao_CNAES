"""
Serviço de planejamento de rotas para representantes.
"""
from __future__ import annotations

from typing import List

from src.models.lead import LeadScored
from src.models.route import RouteDayPlan, RoutePlan, RouteStop


def planejar_rota(
    leads: List[LeadScored],
    dias_de_rota: int,
    visitas_por_dia: int,
    cidade_base: str = "",
    uf_base: str = ""
) -> RoutePlan:
    """
    Planeja rota de visitas distribuindo leads por dias.
    
    Heurística:
    1. Agrupa leads por cidade/bairro/CEP
    2. Ordena por score (maior primeiro)
    3. Distribui em dias respeitando visitas_por_dia
    4. Garante que sempre há um lead visitável por trecho
    
    Args:
        leads: Lista de leads qualificados e ordenados por score
        dias_de_rota: Número de dias da rota
        visitas_por_dia: Número de visitas por dia
        cidade_base: Cidade base do representante
        uf_base: UF base do representante
        
    Returns:
        RoutePlan com distribuição de visitas por dia
    """
    
    leads_visitaveis = [lead for lead in leads if lead.visitavel]
    
    if not leads_visitaveis:
        
        return RoutePlan(dias=[], cidade_base=cidade_base, uf_base=uf_base)
    
   
    grupos_localizacao = _agrupar_por_localizacao(leads_visitaveis)
    
    
    grupos_ordenados = _ordenar_grupos_por_prioridade(grupos_localizacao)
    
    
    dias: List[RouteDayPlan] = []
    lead_index = 0
    
    for dia_num in range(1, dias_de_rota + 1):
        stops: List[RouteStop] = []
        
        
        for ordem in range(1, visitas_por_dia + 1):
            if lead_index >= len(grupos_ordenados):
                break
            
            lead = grupos_ordenados[lead_index]
            stop = RouteStop(
                lead=lead,
                ordem=ordem,
                dia=dia_num
            )
            stops.append(stop)
            lead_index += 1
        
        if stops:
            dia_plan = RouteDayPlan(
                dia=dia_num,
                stops=stops,
                cidade_base=cidade_base
            )
            dias.append(dia_plan)
    
    return RoutePlan(
        dias=dias,
        cidade_base=cidade_base,
        uf_base=uf_base
    )


def _agrupar_por_localizacao(leads: List[LeadScored]) -> dict[str, List[LeadScored]]:
    """
    Agrupa leads por localização (cidade + bairro).
    
    Args:
        leads: Lista de leads
        
    Returns:
        Dicionário com chave = localização, valor = lista de leads
    """
    grupos: dict[str, List[LeadScored]] = {}
    
    for lead in leads:
        # Cria chave de localização
        if lead.endereco:
            chave = f"{lead.cidade}|{lead.endereco.bairro}|{lead.endereco.cep[:5]}"
        else:
            chave = f"{lead.cidade}||"
        
        if chave not in grupos:
            grupos[chave] = []
        grupos[chave].append(lead)
    
    return grupos


def _ordenar_grupos_por_prioridade(
    grupos: dict[str, List[LeadScored]]
) -> List[LeadScored]:
    """
    Ordena grupos por prioridade e retorna lista flat de leads.
    
    Critérios:
    1. Score médio do grupo (maior primeiro)
    2. Quantidade de leads no grupo (maior primeiro)
    
    Args:
        grupos: Dicionário de grupos por localização
        
    Returns:
        Lista flat de leads ordenados
    """
   
    grupos_com_prioridade: List[tuple[float, int, List[LeadScored]]] = []
    
    for leads_grupo in grupos.values():
        score_medio = sum(lead.score for lead in leads_grupo) / len(leads_grupo)
        quantidade = len(leads_grupo)
        grupos_com_prioridade.append((score_medio, quantidade, leads_grupo))
    
    
    grupos_com_prioridade.sort(key=lambda x: (x[0], x[1]), reverse=True)
    
    
    leads_ordenados: List[LeadScored] = []
    for _, _, leads_grupo in grupos_com_prioridade:
        
        leads_grupo_sorted = sorted(leads_grupo, key=lambda x: x.score, reverse=True)
        leads_ordenados.extend(leads_grupo_sorted)
    
    return leads_ordenados


def otimizar_rota_por_proximidade(
    dia_plan: RouteDayPlan
) -> RouteDayPlan:
    """
    Otimiza ordem de visitas em um dia por proximidade geográfica.
    
    Heurística simples: agrupa por CEP e ordena.
    Para otimização real, seria necessário usar API de rotas (Google Maps, etc.)
    
    Args:
        dia_plan: Plano do dia a otimizar
        
    Returns:
        RouteDayPlan otimizado
    """
    if len(dia_plan.stops) <= 1:
        return dia_plan
    
   
    stops_ordenados = sorted(
        dia_plan.stops,
        key=lambda s: s.lead.endereco.cep if s.lead.endereco else ""
    )
    

    for i, stop in enumerate(stops_ordenados, start=1):
        stop.ordem = i
    
    return RouteDayPlan(
        dia=dia_plan.dia,
        stops=stops_ordenados,
        cidade_base=dia_plan.cidade_base
    )
