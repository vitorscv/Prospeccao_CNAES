"""Script de teste para verificar importações."""
from src.ui.icons import Icons
try:
    # Verifica serviços essenciais (omitindo modelos removidos)
    from src.services.scoring_service import calcular_score_lead
    print(f"{Icons.CHECK} Scoring service importado com sucesso")
    
    from src.services.route_service import planejar_rota
    print(f"{Icons.CHECK} Route service importado com sucesso")
    
    from src.database.estabelecimentos_repository import buscar_leads_enriquecidos
    print(f"{Icons.CHECK} Estabelecimentos repository importado com sucesso")
    
    print(f"\n{Icons.CHECK} Importações essenciais funcionaram!")
    
except Exception as e:
    print(f"{Icons.CROSS} Erro: {e}")
    import traceback
    traceback.print_exc()
