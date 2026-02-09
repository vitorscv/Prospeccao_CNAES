"""
Testes para o serviço de scoring.
"""
from datetime import date

import pytest

from src.config.scoring_config import DEFAULT_WEIGHTS, ScoringWeights
from src.models.lead import Endereco, Lead
from src.services.scoring_service import calcular_score_lead, qualificar_leads


def test_score_lead_completo():
    """Testa score de um lead completo com todos os dados."""
    endereco = Endereco(
        logradouro="Rua Teste",
        numero="123",
        bairro="Centro",
        cep="12345-678",
        cidade="São Paulo",
        uf="SP"
    )
    
    lead = Lead(
        cnpj="12345678000190",
        cnpj_basico="12345678",
        nome_fantasia="Empresa Teste",
        cnae_principal="4711302",
        descricao_cnae="Comércio varejista de mercadorias",
        matriz_filial="MATRIZ",
        endereco=endereco,
        cidade="São Paulo",
        uf="SP",
        telefone_principal="11 98765-4321",
        telefone_secundario="11 3333-4444",
        email="contato@teste.com",
        data_inicio_atividade=date(2010, 1, 1)
    )
    
    lead_scored = calcular_score_lead(lead)
    
    # Verifica que o score foi calculado
    assert lead_scored.score > 0
    
    # Verifica que tem razões
    assert len(lead_scored.reasons) > 0
    
    # Verifica campos copiados
    assert lead_scored.cnpj == lead.cnpj
    assert lead_scored.nome_fantasia == lead.nome_fantasia


def test_score_lead_sem_contato():
    """Testa score de um lead sem contato."""
    lead = Lead(
        cnpj="12345678000190",
        cnpj_basico="12345678",
        nome_fantasia="Empresa Teste",
        cnae_principal="4711302",
        descricao_cnae="Comércio varejista",
        matriz_filial="FILIAL",
        cidade="São Paulo",
        uf="SP"
    )
    
    lead_scored = calcular_score_lead(lead)
    
    # Score deve ser baixo (sem telefone, email, endereço)
    assert lead_scored.score < 50


def test_score_lead_com_telefone_aumenta():
    """Testa que telefone aumenta o score."""
    lead_sem_tel = Lead(
        cnpj="12345678000190",
        cnpj_basico="12345678",
        nome_fantasia="Empresa Teste",
        cnae_principal="4711302",
        descricao_cnae="Comércio",
        cidade="São Paulo",
        uf="SP"
    )
    
    lead_com_tel = Lead(
        cnpj="12345678000190",
        cnpj_basico="12345678",
        nome_fantasia="Empresa Teste",
        cnae_principal="4711302",
        descricao_cnae="Comércio",
        cidade="São Paulo",
        uf="SP",
        telefone_principal="11 98765-4321"
    )
    
    score_sem = calcular_score_lead(lead_sem_tel).score
    score_com = calcular_score_lead(lead_com_tel).score
    
    assert score_com > score_sem
    assert score_com - score_sem == DEFAULT_WEIGHTS.telefone_valido


def test_score_lead_com_endereco_completo():
    """Testa que endereço completo aumenta o score."""
    endereco = Endereco(
        logradouro="Rua Teste",
        numero="123",
        bairro="Centro",
        cep="12345-678",
        cidade="São Paulo",
        uf="SP"
    )
    
    lead = Lead(
        cnpj="12345678000190",
        cnpj_basico="12345678",
        nome_fantasia="Empresa Teste",
        cnae_principal="4711302",
        descricao_cnae="Comércio",
        cidade="São Paulo",
        uf="SP",
        endereco=endereco
    )
    
    lead_scored = calcular_score_lead(lead)
    
    # Deve ter pontos de endereço completo
    assert any("Endereço completo" in r for r in lead_scored.reasons)


def test_qualificar_leads_filtra_por_score_minimo():
    """Testa que qualificar_leads filtra por score mínimo."""
    leads = [
        Lead(
            cnpj=f"1234567800019{i}",
            cnpj_basico="12345678",
            nome_fantasia=f"Empresa {i}",
            cnae_principal="4711302",
            descricao_cnae="Comércio",
            cidade="São Paulo",
            uf="SP",
            telefone_principal="11 98765-4321" if i % 2 == 0 else None
        )
        for i in range(10)
    ]
    
    # Qualifica com score mínimo 15
    leads_qualificados = qualificar_leads(leads, score_minimo=15)
    
    # Deve ter filtrado alguns
    assert len(leads_qualificados) < len(leads)
    
    # Todos devem ter score >= 15
    assert all(lead.score >= 15 for lead in leads_qualificados)


def test_qualificar_leads_ordena_por_score():
    """Testa que qualificar_leads ordena por score decrescente."""
    leads = [
        Lead(
            cnpj=f"1234567800019{i}",
            cnpj_basico="12345678",
            nome_fantasia=f"Empresa {i}",
            cnae_principal="4711302",
            descricao_cnae="Comércio",
            cidade="São Paulo",
            uf="SP",
            telefone_principal="11 98765-4321" if i % 2 == 0 else None,
            email=f"empresa{i}@teste.com" if i % 3 == 0 else None
        )
        for i in range(10)
    ]
    
    leads_qualificados = qualificar_leads(leads, score_minimo=0)
    
    # Verifica que está ordenado (decrescente)
    scores = [lead.score for lead in leads_qualificados]
    assert scores == sorted(scores, reverse=True)


def test_pesos_customizados():
    """Testa que pesos customizados afetam o score."""
    lead = Lead(
        cnpj="12345678000190",
        cnpj_basico="12345678",
        nome_fantasia="Empresa Teste",
        cnae_principal="4711302",
        descricao_cnae="Comércio",
        cidade="São Paulo",
        uf="SP",
        telefone_principal="11 98765-4321"
    )
    
    # Score com pesos padrão
    score_padrao = calcular_score_lead(lead, DEFAULT_WEIGHTS).score
    
    # Score com pesos customizados (telefone vale mais)
    pesos_custom = ScoringWeights(telefone_valido=50)
    score_custom = calcular_score_lead(lead, pesos_custom).score
    
    assert score_custom > score_padrao
