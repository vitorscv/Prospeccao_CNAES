"""
Modelos de domínio para planejamento de rotas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.models.lead import LeadScored


@dataclass
class RouteStop:
    """Parada em uma rota (visita a um lead)."""
    
    lead: LeadScored
    ordem: int
    dia: int
    observacoes: Optional[str] = None
    
    @property
    def endereco_formatado(self) -> str:
        """Retorna endereço formatado para exibição."""
        if self.lead.endereco:
            return self.lead.endereco.formatado
        return f"{self.lead.cidade} - {self.lead.uf}"


@dataclass
class RouteDayPlan:
    """Plano de visitas para um dia específico."""
    
    dia: int
    stops: list[RouteStop] = field(default_factory=list)
    cidade_base: str = ""
    
    @property
    def total_visitas(self) -> int:
        """Total de visitas no dia."""
        return len(self.stops)
    
    @property
    def score_medio(self) -> float:
        """Score médio dos leads do dia."""
        if not self.stops:
            return 0.0
        return sum(stop.lead.score for stop in self.stops) / len(self.stops)
    
    @property
    def link_maps_rota(self) -> str:
        """Gera link do Google Maps com waypoints para o dia."""
        if not self.stops:
            return ""
        
        from urllib.parse import quote
        
        
        stops_com_endereco = [s for s in self.stops if s.lead.endereco and s.lead.endereco.completo]
        
        if not stops_com_endereco:
            return ""
        
        
        max_waypoints = 9 
        
        if len(stops_com_endereco) <= max_waypoints + 1:
            
            origin = stops_com_endereco[0].lead.endereco.google_maps_query
            destination = stops_com_endereco[-1].lead.endereco.google_maps_query
            
            waypoints = []
            for stop in stops_com_endereco[1:-1]:
                waypoints.append(stop.lead.endereco.google_maps_query)
            
            url = f"https://www.google.com/maps/dir/?api=1&origin={quote(origin)}&destination={quote(destination)}"
            if waypoints:
                url += f"&waypoints={quote('|'.join(waypoints))}"
            url += "&travelmode=driving"
            
            return url
        else:
            
    
            origin = stops_com_endereco[0].lead.endereco.google_maps_query
            destination = stops_com_endereco[max_waypoints].lead.endereco.google_maps_query
            
            waypoints = []
            for stop in stops_com_endereco[1:max_waypoints]:
                waypoints.append(stop.lead.endereco.google_maps_query)
            
            url = f"https://www.google.com/maps/dir/?api=1&origin={quote(origin)}&destination={quote(destination)}"
            if waypoints:
                url += f"&waypoints={quote('|'.join(waypoints))}"
            url += "&travelmode=driving"
            
            return url + " (AVISO: Rota dividida - mais de 10 paradas)"


@dataclass
class RoutePlan:
    """Plano completo de rota com múltiplos dias."""
    
    dias: list[RouteDayPlan] = field(default_factory=list)
    cidade_base: str = ""
    uf_base: str = ""
    
    @property
    def total_visitas(self) -> int:
        """Total de visitas em todos os dias."""
        return sum(dia.total_visitas for dia in self.dias)
    
    @property
    def total_dias(self) -> int:
        """Total de dias na rota."""
        return len(self.dias)
    
    @property
    def score_medio_geral(self) -> float:
        """Score médio geral de todos os leads."""
        if not self.dias:
            return 0.0
        total_score = sum(dia.score_medio * dia.total_visitas for dia in self.dias)
        total_visitas = self.total_visitas
        return total_score / total_visitas if total_visitas > 0 else 0.0
