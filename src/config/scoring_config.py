"""Configuração mínima de segmentos e CNAEs usada pela UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import re


@dataclass
class Segmento:
    nome: str
    cnaes: List[str]
    aderencia: str = "aderente"  # ou "altamente_aderente"


# Mapa mínimo de segmentos usado pela interface.
# Adicione ou ajuste conforme necessário no projeto real.
SEGMENTOS_PANTEX: Dict[str, Segmento] = {
    "industria_alimentos": Segmento(nome="Indústria de Alimentos", cnaes=["4711302"], aderencia="altamente_aderente"),
    "atacado_alimentos": Segmento(nome="Atacado de Alimentos", cnaes=["4729699"]),
    "material_construcao": Segmento(nome="Material de Construção", cnaes=["4123401"]),
    # entradas adicionais de exemplo (vazias) — mantenha para compatibilidade se necessário
    "outros": Segmento(nome="Outros", cnaes=[]),
}


@dataclass
class ScoringWeights:
    segmento_altamente_aderente: int = 30
    segmento_aderente: int = 15
    telefone_valido: int = 10
    telefone_secundario: int = 3
    email: int = 5
    endereco_completo: int = 8
    anos_8_ou_mais: int = 7
    anos_3_ou_mais: int = 3
    matriz: int = 5


DEFAULT_WEIGHTS = ScoringWeights()


def _normalize_cnae(c: str) -> str:
    if not c:
        return ""
    return re.sub(r"[^\d]", "", str(c))


def get_segmento_by_cnae(cnae: Optional[str]) -> Optional[Segmento]:
    """Retorna o Segmento correspondente ao CNAE (normalizando formatos)."""
    if not cnae:
        return None
    c_norm = _normalize_cnae(cnae)
    for seg in SEGMENTOS_PANTEX.values():
        for code in seg.cnaes:
            if _normalize_cnae(code) == c_norm:
                return seg
    return None
