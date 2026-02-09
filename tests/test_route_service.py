"""
Testes para o serviço de rotas.
"""
from src.models.lead import Endereco, LeadScored
from src.services.route_service import planejar_rota


def criar_lead_teste(
    cnpj: str,
    nome: str,
    cidade: str,
    bairro: str = "Centro",
    score: int = 50
) -> LeadScored:
    """Helper para criar lead de teste."""
    endereco = Endereco(
        logradouro="Rua Teste",
        numero="123",
        bairro=bairro,
        cep="12345-678",
        cidade=cidade,
        uf="SP"
    )
    
    return LeadScored(
        cnpj=cnpj,
        cnpj_basico=cnpj[:8],
        nome_fantasia=nome,
        cnae_principal="4711302",
        descricao_cnae="Comércio",
        cidade=cidade,
        uf="SP",
        endereco=endereco,
        telefone_principal="11 98765-4321",
        score=score
    )


def test_planejar_rota_basico():
    """Testa planejamento básico de rota."""
    leads = [
        criar_lead_teste(f"1234567800019{i}", f"Empresa {i}", "São Paulo", score=50 + i)
        for i in range(10)
    ]
    
    rota = planejar_rota(
        leads=leads,
        dias_de_rota=2,
        visitas_por_dia=5,
        cidade_base="São Paulo",
        uf_base="SP"
    )
    
    # Verifica estrutura básica
    assert rota.total_dias == 2
    assert rota.total_visitas == 10
    assert len(rota.dias) == 2
    
    # Verifica que cada dia tem 5 visitas
    assert all(dia.total_visitas == 5 for dia in rota.dias)


def test_planejar_rota_filtra_nao_visitaveis():
    """Testa que rota filtra leads não visitáveis."""
    # Leads com endereço
    leads_com_endereco = [
        criar_lead_teste(f"1234567800019{i}", f"Empresa {i}", "São Paulo")
        for i in range(5)
    ]
    
    # Leads sem endereço (não visitáveis)
    leads_sem_endereco = [
        LeadScored(
            cnpj=f"9876543210019{i}",
            cnpj_basico="98765432",
            nome_fantasia=f"Empresa Sem End {i}",
            cnae_principal="4711302",
            descricao_cnae="Comércio",
            cidade="São Paulo",
            uf="SP",
            score=60
        )
        for i in range(5)
    ]
    
    todos_leads = leads_com_endereco + leads_sem_endereco
    
    rota = planejar_rota(
        leads=todos_leads,
        dias_de_rota=1,
        visitas_por_dia=10,
        cidade_base="São Paulo",
        uf_base="SP"
    )
    
    # Deve ter apenas os 5 visitáveis
    assert rota.total_visitas == 5


def test_planejar_rota_respeita_limite_visitas():
    """Testa que rota respeita limite de visitas por dia."""
    leads = [
        criar_lead_teste(f"1234567800019{i}", f"Empresa {i}", "São Paulo")
        for i in range(20)
    ]
    
    rota = planejar_rota(
        leads=leads,
        dias_de_rota=3,
        visitas_por_dia=5,
        cidade_base="São Paulo",
        uf_base="SP"
    )
    
    # Total deve ser 15 (3 dias * 5 visitas)
    assert rota.total_visitas == 15
    
    # Nenhum dia deve ter mais de 5 visitas
    assert all(dia.total_visitas <= 5 for dia in rota.dias)


def test_planejar_rota_ordena_por_score():
    """Testa que rota prioriza leads com maior score."""
    leads = [
        criar_lead_teste(f"1234567800019{i}", f"Empresa {i}", "São Paulo", score=i * 10)
        for i in range(10)
    ]
    
    rota = planejar_rota(
        leads=leads,
        dias_de_rota=1,
        visitas_por_dia=3,
        cidade_base="São Paulo",
        uf_base="SP"
    )
    
    # Deve ter pego os 3 com maior score
    scores_rota = [stop.lead.score for stop in rota.dias[0].stops]
    
    # Verifica que são os maiores scores
    assert 90 in scores_rota  # score mais alto
    assert 80 in scores_rota
    assert 70 in scores_rota


def test_planejar_rota_vazia_sem_leads():
    """Testa que rota vazia é retornada quando não há leads."""
    rota = planejar_rota(
        leads=[],
        dias_de_rota=5,
        visitas_por_dia=10,
        cidade_base="São Paulo",
        uf_base="SP"
    )
    
    assert rota.total_visitas == 0
    assert rota.total_dias == 0
    assert len(rota.dias) == 0


def test_score_medio_dia():
    """Testa cálculo de score médio do dia."""
    leads = [
        criar_lead_teste(f"1234567800019{i}", f"Empresa {i}", "São Paulo", score=50 + i * 10)
        for i in range(5)
    ]
    
    rota = planejar_rota(
        leads=leads,
        dias_de_rota=1,
        visitas_por_dia=5,
        cidade_base="São Paulo",
        uf_base="SP"
    )
    
    dia = rota.dias[0]
    
    # Score médio deve ser calculado corretamente
    scores = [stop.lead.score for stop in dia.stops]
    score_medio_esperado = sum(scores) / len(scores)
    
    assert abs(dia.score_medio - score_medio_esperado) < 0.01


def test_link_maps_gerado():
    """Testa que link do Google Maps é gerado."""
    leads = [
        criar_lead_teste(f"1234567800019{i}", f"Empresa {i}", "São Paulo")
        for i in range(3)
    ]
    
    rota = planejar_rota(
        leads=leads,
        dias_de_rota=1,
        visitas_por_dia=3,
        cidade_base="São Paulo",
        uf_base="SP"
    )
    
    dia = rota.dias[0]
    
    # Link deve ser gerado
    assert dia.link_maps_rota != ""
    assert "google.com/maps" in dia.link_maps_rota
