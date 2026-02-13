"""Script de teste para verificar importações."""
try:
    # Verifica serviços essenciais (omitindo modelos removidos)
    from src.services.scoring_service import calcular_score_lead
    print("✓ Scoring service importado com sucesso")
    
    from src.services.route_service import planejar_rota
    print("✓ Route service importado com sucesso")
    
    from src.database.estabelecimentos_repository import buscar_leads_enriquecidos
    print("✓ Estabelecimentos repository importado com sucesso")
    
    print("\n✅ Importações essenciais funcionaram!")
    
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
