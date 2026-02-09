"""
Serviço de qualificação e scoring de leads.
"""
from __future__ import annotations

from typing import List

from src.config.scoring_config import (
    DEFAULT_WEIGHTS,
    ScoringWeights,
    get_segmento_by_cnae,
)
from src.models.lead import Lead, LeadScored


def calcular_score_lead(
    lead: Lead,
    weights: ScoringWeights = DEFAULT_WEIGHTS
) -> LeadScored:
    """
    Calcula score de qualificação de um lead.
    
    Args:
        lead: Lead a ser qualificado
        weights: Pesos para cálculo do score
        
    Returns:
        LeadScored com score e razões
    """
    score = 0
    reasons: List[str] = []
    
    # 1. Fit por CNAE/Segmento
    segmento = get_segmento_by_cnae(lead.cnae_principal)
    segmento_nome = None
    
    if segmento:
        segmento_nome = segmento.nome
        if segmento.aderencia == "altamente_aderente":
            score += weights.segmento_altamente_aderente
            reasons.append(f"Segmento altamente aderente: {segmento.nome} (+{weights.segmento_altamente_aderente})")
        else:
            score += weights.segmento_aderente
            reasons.append(f"Segmento aderente: {segmento.nome} (+{weights.segmento_aderente})")
    
    # 2. Visitável (contato/endereço)
    if lead.telefone_principal:
        score += weights.telefone_valido
        reasons.append(f"Telefone principal válido (+{weights.telefone_valido})")
    
    if lead.telefone_secundario:
        score += weights.telefone_secundario
        reasons.append(f"Telefone secundário disponível (+{weights.telefone_secundario})")
    
    if lead.email:
        score += weights.email
        reasons.append(f"Email disponível (+{weights.email})")
    
    if lead.endereco and lead.endereco.completo:
        score += weights.endereco_completo
        reasons.append(f"Endereço completo (+{weights.endereco_completo})")
    
    # 3. Maturidade
    anos = lead.anos_atividade
    if anos >= 8:
        score += weights.anos_8_ou_mais
        reasons.append(f"Empresa com {anos} anos de atividade (+{weights.anos_8_ou_mais})")
    elif anos >= 3:
        score += weights.anos_3_ou_mais
        reasons.append(f"Empresa com {anos} anos de atividade (+{weights.anos_3_ou_mais})")
    
    # 4. Matriz vs Filial
    if lead.matriz_filial == "MATRIZ":
        score += weights.matriz
        reasons.append(f"Matriz da empresa (+{weights.matriz})")
    
    # Cria LeadScored
    # Copia todos os atributos do Lead original
    lead_scored = LeadScored(
        cnpj=lead.cnpj,
        cnpj_basico=lead.cnpj_basico,
        nome_fantasia=lead.nome_fantasia,
        razao_social=lead.razao_social,
        cnae_principal=lead.cnae_principal,
        descricao_cnae=lead.descricao_cnae,
        cnaes_secundarios=lead.cnaes_secundarios,
        matriz_filial=lead.matriz_filial,
        endereco=lead.endereco,
        cidade=lead.cidade,
        uf=lead.uf,
        telefone_principal=lead.telefone_principal,
        telefone_secundario=lead.telefone_secundario,
        email=lead.email,
        data_inicio_atividade=lead.data_inicio_atividade,
        score=score,
        reasons=reasons,
        segmento=segmento_nome
    )
    
    return lead_scored


def qualificar_leads(
    leads: List[Lead],
    weights: ScoringWeights = DEFAULT_WEIGHTS,
    score_minimo: int = 0
) -> List[LeadScored]:
    """
    Qualifica uma lista de leads e filtra por score mínimo.
    
    Args:
        leads: Lista de leads a qualificar
        weights: Pesos para cálculo do score
        score_minimo: Score mínimo para incluir no resultado
        
    Returns:
        Lista de LeadScored ordenada por score (maior primeiro)
    """
    leads_scored = [calcular_score_lead(lead, weights) for lead in leads]
    
    # Filtra por score mínimo
    if score_minimo > 0:
        leads_scored = [ls for ls in leads_scored if ls.score >= score_minimo]
    
    # Ordena por score (maior primeiro)
    leads_scored.sort(key=lambda x: x.score, reverse=True)
    
    return leads_scored


def filtrar_leads_visitaveis(leads: List[LeadScored]) -> List[LeadScored]:
    """
    Filtra apenas leads visitáveis (com endereço completo).
    
    Args:
        leads: Lista de leads scored
        
    Returns:
        Lista filtrada de leads visitáveis
    """
    return [lead for lead in leads if lead.visitavel]


def filtrar_leads_por_segmento(
    leads: List[LeadScored],
    segmentos: List[str]
) -> List[LeadScored]:
    """
    Filtra leads por segmentos.
    
    Args:
        leads: Lista de leads scored
        segmentos: Lista de nomes de segmentos
        
    Returns:
        Lista filtrada de leads
    """
    if not segmentos:
        return leads
    
    return [lead for lead in leads if lead.segmento in segmentos]


def filtrar_leads_com_telefone(leads: List[LeadScored]) -> List[LeadScored]:
    """
    Filtra apenas leads com telefone.
    
    Args:
        leads: Lista de leads scored
        
    Returns:
        Lista filtrada de leads com telefone
    """
    return [lead for lead in leads if lead.telefone_principal]
