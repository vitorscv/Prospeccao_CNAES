"""
Configuração centralizada para o sistema de scoring de leads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class ScoringWeights:
    """Pesos para cálculo de score (0-100)."""
    
    # Fit por CNAE/Segmento
    segmento_altamente_aderente: int = 30
    segmento_aderente: int = 15
    
    # Visitável (contato/endereço)
    telefone_valido: int = 20
    telefone_secundario: int = 5
    email: int = 5
    endereco_completo: int = 20
    
    # Maturidade
    anos_3_ou_mais: int = 5
    anos_8_ou_mais: int = 10
    
    # Matriz vs Filial
    matriz: int = 5


@dataclass(frozen=True)
class SegmentoPreset:
    """Preset de segmento com CNAEs associados."""
    
    nome: str
    descricao: str
    cnaes: List[str]
    aderencia: str = "aderente"  # "altamente_aderente" ou "aderente"


# Configuração padrão de pesos
DEFAULT_WEIGHTS = ScoringWeights()


# Presets de segmentos para Pantex (exemplo - ajustar conforme necessidade real)
SEGMENTOS_PANTEX: Dict[str, SegmentoPreset] = {
    "supermercados": SegmentoPreset(
        nome="Supermercados e Hipermercados",
        descricao="Varejo alimentício de grande porte",
        cnaes=["4711301", "4711302", "4712100"],
        aderencia="altamente_aderente"
    ),
    "minimercados": SegmentoPreset(
        nome="Minimercados e Mercearias",
        descricao="Varejo alimentício de pequeno e médio porte",
        cnaes=["4712100", "4729699"],
        aderencia="aderente"
    ),
    "padarias": SegmentoPreset(
        nome="Padarias e Confeitarias",
        descricao="Comércio de pães, bolos e similares",
        cnaes=["4721102", "1091101", "1091102"],
        aderencia="altamente_aderente"
    ),
    "restaurantes": SegmentoPreset(
        nome="Restaurantes e Lanchonetes",
        descricao="Serviços de alimentação",
        cnaes=["5611201", "5611203", "5611204", "5611205"],
        aderencia="aderente"
    ),
    "hoteis": SegmentoPreset(
        nome="Hotéis e Pousadas",
        descricao="Serviços de hospedagem",
        cnaes=["5510801", "5510802", "5590601", "5590602"],
        aderencia="aderente"
    ),
    "industria_alimentos": SegmentoPreset(
        nome="Indústria de Alimentos",
        descricao="Fabricação de produtos alimentícios",
        cnaes=["1091101", "1091102", "1092900", "1093701"],
        aderencia="altamente_aderente"
    ),
    "atacado_alimentos": SegmentoPreset(
        nome="Atacado de Alimentos",
        descricao="Comércio atacadista de produtos alimentícios",
        cnaes=["4631100", "4632001", "4633801", "4635401"],
        aderencia="aderente"
    ),
    "farmacia": SegmentoPreset(
        nome="Farmácias e Drogarias",
        descricao="Comércio varejista de medicamentos",
        cnaes=["4771701", "4771702", "4771703"],
        aderencia="aderente"
    ),
    "construcao": SegmentoPreset(
        nome="Construção Civil",
        descricao="Empresas de construção e obras",
        cnaes=["4120400", "4211101", "4212000", "4213800"],
        aderencia="aderente"
    ),
    "material_construcao": SegmentoPreset(
        nome="Material de Construção",
        descricao="Comércio de materiais de construção",
        cnaes=["4744001", "4744002", "4744003", "4744004"],
        aderencia="altamente_aderente"
    ),
}


def get_segmento_by_cnae(cnae: str) -> SegmentoPreset | None:
    """
    Retorna o segmento associado a um CNAE.
    
    Args:
        cnae: Código CNAE a buscar
        
    Returns:
        SegmentoPreset se encontrado, None caso contrário
    """
    for segmento in SEGMENTOS_PANTEX.values():
        if cnae in segmento.cnaes:
            return segmento
    return None


def listar_todos_cnaes_por_segmento() -> Dict[str, List[str]]:
    """
    Retorna dicionário com todos os CNAEs agrupados por segmento.
    
    Returns:
        Dict com chave = nome do segmento, valor = lista de CNAEs
    """
    return {
        segmento.nome: segmento.cnaes
        for segmento in SEGMENTOS_PANTEX.values()
    }
