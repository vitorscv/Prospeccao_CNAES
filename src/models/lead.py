"""
Modelos de domínio para leads enriquecidos e qualificados.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Endereco:
    """Endereço completo de um estabelecimento."""
    
    logradouro: str
    numero: str
    bairro: str
    cep: str
    complemento: Optional[str] = None
    cidade: str = ""
    uf: str = ""
    
    @property
    def completo(self) -> bool:
        """Verifica se o endereço está completo (logradouro, número e CEP)."""
        return bool(self.logradouro and self.numero and self.cep)
    
    @property
    def formatado(self) -> str:
        """Retorna endereço formatado para exibição."""
        partes = [self.logradouro]
        if self.numero:
            partes.append(f"nº {self.numero}")
        if self.complemento:
            partes.append(self.complemento)
        if self.bairro:
            partes.append(f"- {self.bairro}")
        if self.cep:
            partes.append(f"- CEP {self.cep}")
        return " ".join(partes)
    
    @property
    def google_maps_query(self) -> str:
        """Retorna query formatada para Google Maps."""
        partes = []
        if self.logradouro:
            partes.append(self.logradouro)
        if self.numero:
            partes.append(self.numero)
        if self.bairro:
            partes.append(self.bairro)
        if self.cidade:
            partes.append(self.cidade)
        if self.uf:
            partes.append(self.uf)
        if self.cep:
            partes.append(self.cep)
        return ", ".join(partes)


@dataclass
class Lead:
    """Lead enriquecido com todos os dados necessários para prospecção."""
    
    # Identificação
    cnpj: str
    cnpj_basico: str
    nome_fantasia: str
    cnae_principal: str
    descricao_cnae: str
    
    # Campos com valores padrão 
    razao_social: Optional[str] = None
    cnaes_secundarios: list[str] = field(default_factory=list)
    matriz_filial: str = "FILIAL"  # "MATRIZ" ou "FILIAL"
    
    # Localização
    endereco: Optional[Endereco] = None
    cidade: str = ""
    uf: str = ""
    
    # Contato
    telefone_principal: Optional[str] = None
    telefone_secundario: Optional[str] = None
    email: Optional[str] = None
    
    # Maturidade
    data_inicio_atividade: Optional[date] = None
    
    @property
    def visitavel(self) -> bool:
        """Lead é visitável se tem endereço completo."""
        return self.endereco is not None and self.endereco.completo
    
    @property
    def contatavel(self) -> bool:
        """Lead é contatável se tem telefone ou email."""
        return bool(self.telefone_principal or self.email)
    
    @property
    def anos_atividade(self) -> int:
        """Retorna anos de atividade da empresa."""
        if not self.data_inicio_atividade:
            return 0
        from datetime import date
        hoje = date.today()
        return hoje.year - self.data_inicio_atividade.year
    
    @property
    def link_maps(self) -> str:
        """Gera link do Google Maps para o endereço."""
        if not self.endereco:
            return ""
        from urllib.parse import quote
        query = self.endereco.google_maps_query
        return f"https://www.google.com/maps/search/?api=1&query={quote(query)}"


@dataclass
class LeadScored(Lead):
    """Lead com score de qualificação e segmento."""
    
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    segmento: Optional[str] = None
    
    @property
    def qualificado(self) -> bool:
        """Lead é qualificado se tem score >= 50."""
        return self.score >= 50
