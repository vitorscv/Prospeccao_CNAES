"""
Repositório para consultas na tabela de estabelecimentos.
Todas as queries são parametrizadas para evitar SQL injection.
"""
from __future__ import annotations

import os
from datetime import date
from time import perf_counter
from typing import List, Optional

from src.database.connection import get_connection
from src.models.lead import Endereco, Lead

# Flag de debug controlada por env var (DEBUG_ROTA=1 para ativar)
DEBUG_ROTA = os.getenv("DEBUG_ROTA", "0") == "1"


def buscar_leads_enriquecidos(
    lista_cnaes: List[str],
    uf: Optional[str] = None,
    cidade: Optional[str] = None,
    somente_matriz: bool = False,
    limite: int = 50000
) -> List[Lead]:
    """
    Busca leads enriquecidos com todos os dados necessários.
    
    Args:
        lista_cnaes: Lista de códigos CNAE
        uf: UF para filtrar (None = todas)
        cidade: Nome da cidade para filtrar (None = todas)
        somente_matriz: Se True, retorna apenas matrizes
        limite: Limite de resultados
        
    Returns:
        Lista de objetos Lead enriquecidos
    """
    t0 = perf_counter()
    con = get_connection()
    if not con:
        return []
    
    try:
        t_conn = perf_counter() - t0
        
        # Debug: contagens progressivas para diagnóstico
        if DEBUG_ROTA:
            count_total = con.execute("SELECT COUNT(*) FROM estabelecimentos").fetchone()[0]
            print(f"[DEBUG_ROTA] Total em estabelecimentos: {count_total}")
            
            if uf and uf != "BRASIL":
                count_uf = con.execute("SELECT COUNT(*) FROM estabelecimentos WHERE uf = ?", [uf]).fetchone()[0]
                print(f"[DEBUG_ROTA] Total filtrado por UF={uf}: {count_uf}")
                
                count_uf_sit = con.execute(
                    "SELECT COUNT(*) FROM estabelecimentos WHERE uf = ? AND situacao_cadastral = '02'", 
                    [uf]
                ).fetchone()[0]
                print(f"[DEBUG_ROTA] Total filtrado por UF={uf} + situacao='02': {count_uf_sit}")
        
        # Monta placeholders para CNAEs (?, ?, ?)
        placeholders_cnae = ", ".join(["?" for _ in lista_cnaes])
        
        # Normaliza CNAEs: remove pontos e hífens para matching consistente
        # (ex: "4711-3/02" -> "4711302", "47.11-3/02" -> "4711302")
        lista_cnaes_normalizada = [c.replace(".", "").replace("-", "").replace("/", "") for c in lista_cnaes]
        
        # Inicia lista de parâmetros com CNAEs normalizados
        params: List[str | int] = list(lista_cnaes_normalizada)
        
        # Comprimento padrão para códigos IBGE de municípios (7 dígitos)
        MUNICIPIO_CODE_LENGTH = 7
        
        # Filtro de UF
        filtro_uf = ""
        if uf and uf != "BRASIL":
            filtro_uf = "AND e.uf = ?"
            params.append(uf)
        
        # Filtro de cidade (precisa buscar código do município)
        filtro_cidade = ""
        if cidade and cidade != "TODAS":
            # Busca código da cidade de forma segura (normaliza comparação)
            codigo_cidade = con.execute(
                "SELECT codigo FROM municipios WHERE TRIM(UPPER(descricao)) = TRIM(UPPER(?)) LIMIT 1",
                [cidade]
            ).fetchone()
            
            if codigo_cidade:
                # Normaliza código do município para string com zeros à esquerda se necessário
                codigo_str = str(codigo_cidade[0]).strip()
                codigo_normalizado = codigo_str.zfill(MUNICIPIO_CODE_LENGTH)  # Normaliza parâmetro uma vez
                # Usa coluna normalizada da CTE (municipio_norm) para melhor performance
                filtro_cidade = f"AND e.municipio_norm = ?"
                params.append(codigo_normalizado)
                
                if DEBUG_ROTA:
                    # Debug: distribuição de comprimentos
                    len_dist = con.execute(
                        "SELECT LENGTH(CAST(municipio AS VARCHAR)) as len, COUNT(*) as cnt FROM estabelecimentos WHERE uf = ? GROUP BY len ORDER BY len",
                        [uf]
                    ).fetchall()
                    len_dict = {row[0]: row[1] for row in len_dist[:10]}  # primeiros 10 comprimentos
                    print(f"[DEBUG_ROTA] Distribuição LENGTH(municipio) para UF={uf}: {len_dict}")
                    
                    count_municipio = con.execute(
                        f"SELECT COUNT(*) FROM estabelecimentos e JOIN municipios m ON LPAD(TRIM(CAST(e.municipio AS VARCHAR)), {MUNICIPIO_CODE_LENGTH}, '0') = LPAD(TRIM(CAST(m.codigo AS VARCHAR)), {MUNICIPIO_CODE_LENGTH}, '0') WHERE e.uf = ? AND LPAD(TRIM(CAST(m.codigo AS VARCHAR)), {MUNICIPIO_CODE_LENGTH}, '0') = LPAD(TRIM(CAST(? AS VARCHAR)), {MUNICIPIO_CODE_LENGTH}, '0')",
                        [uf, codigo_str]
                    ).fetchone()[0]
                    print(f"[DEBUG_ROTA] Total no JOIN municipios para cidade={cidade} (cod={codigo_str}): {count_municipio}")
        
        # Filtro de matriz/filial
        filtro_matriz = ""
        if somente_matriz:
            filtro_matriz = "AND e.matriz_filial = ?"
            params.append("1")  # 1 = Matriz
        
        # Debug: contagem antes da query principal
        if DEBUG_ROTA:
            # Contagem com filtros aplicados (sem JOINs complexos)
            debug_query = f"""
                SELECT COUNT(*) FROM estabelecimentos e
                WHERE REPLACE(REPLACE(REPLACE(e.cnae_principal, '.', ''), '-', ''), '/', '') IN ({placeholders_cnae})
                AND e.situacao_cadastral = '02'
                {filtro_uf}
                {filtro_cidade}
                {filtro_matriz}
            """
            debug_params = params[:-1] if limite in params else params  # remove limite se existir
            try:
                count_final = con.execute(debug_query, debug_params).fetchone()[0]
                print(f"[DEBUG_ROTA] Total com todos os filtros (antes JOINs): {count_final}")
                print(f"[DEBUG_ROTA] CNAEs normalizados: {lista_cnaes_normalizada[:3]}... (total={len(lista_cnaes_normalizada)})")
            except Exception as debug_e:
                print(f"[DEBUG_ROTA] Erro na contagem debug: {debug_e}")
        
        # Query principal otimizada: usa CTE para normalizar uma vez (evita recalcular REPLACE/LPAD por linha)
        # Normaliza CNAE e município na CTE para melhor performance
        t_query_start = perf_counter()
        query = f"""
            WITH estabelecimentos_norm AS (
                SELECT 
                    e.*,
                    REPLACE(REPLACE(REPLACE(e.cnae_principal, '.', ''), '-', ''), '/', '') AS cnae_norm,
                    LPAD(TRIM(CAST(e.municipio AS VARCHAR)), {MUNICIPIO_CODE_LENGTH}, '0') AS municipio_norm
                FROM estabelecimentos e
                WHERE e.situacao_cadastral = '02'
                {filtro_uf}
                {filtro_matriz}
            )
            SELECT 
                e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv AS cnpj,
                e.cnpj_basico,
                e.nome_fantasia,
                e.cnae_principal,
                c.descricao AS descricao_cnae,
                e.matriz_filial,
                e.logradouro,
                e.numero,
                e.bairro,
                e.cep,
                e.complemento,
                m.descricao AS cidade,
                e.uf,
                e.ddd_1,
                e.telefone_1,
                e.ddd_2,
                e.telefone_2,
                e.correio_eletronico AS email,
                e.data_inicio_atividade
            FROM estabelecimentos_norm e
            LEFT JOIN municipios m ON e.municipio_norm = LPAD(TRIM(CAST(m.codigo AS VARCHAR)), {MUNICIPIO_CODE_LENGTH}, '0')
            LEFT JOIN cnaes c ON e.cnae_norm = REPLACE(REPLACE(REPLACE(c.codigo, '.', ''), '-', ''), '/', '')
            WHERE e.cnae_norm IN ({placeholders_cnae})
            {filtro_cidade}
            LIMIT ?
        """
        
        params.append(limite)
        
        # Executa query
        rows = con.execute(query, params).fetchall()
        t_query = perf_counter() - t_query_start
        
        if DEBUG_ROTA:
            print(f"[DEBUG_ROTA] Query retornou {len(rows)} linhas em {t_query:.2f}s (conn: {t_conn:.3f}s)")
        
        con.close()
        
        # Converte para objetos Lead
        leads: List[Lead] = []
        for row in rows:
            # Monta endereço (índices ajustados após remover possível coluna inexistente)
            endereco = None
            if row[6]:  # logradouro
                endereco = Endereco(
                    logradouro=row[6] or "",
                    numero=row[7] or "",
                    bairro=row[8] or "",
                    cep=row[9] or "",
                    complemento=row[10] or None,
                    cidade=row[11] or "",
                    uf=row[12] or ""
                )
            
            # Formata telefones
            telefone_principal = None
            if row[13] and row[14]:  # ddd_1 e telefone_1
                telefone_principal = f"{row[13]} {row[14]}"
            
            telefone_secundario = None
            if row[15] and row[16]:  # ddd_2 e telefone_2
                telefone_secundario = f"{row[15]} {row[16]}"
            
            # Converte data de início de atividade
            data_inicio = None
            if row[18]:
                try:
                    # Formato esperado: YYYYMMDD ou YYYY-MM-DD
                    data_str = str(row[18])
                    if len(data_str) == 8:
                        # YYYYMMDD
                        data_inicio = date(
                            int(data_str[0:4]),
                            int(data_str[4:6]),
                            int(data_str[6:8])
                        )
                    else:
                        # Tenta parse direto
                        from datetime import datetime
                        data_inicio = datetime.fromisoformat(str(row[18])).date()
                except (ValueError, TypeError):
                    pass
            
            # Determina matriz/filial
            matriz_filial = "MATRIZ" if row[5] == "1" else "FILIAL"
            
            lead = Lead(
                cnpj=row[0],
                cnpj_basico=row[1],
                nome_fantasia=row[2] or "",
                razao_social=None,  # coluna não disponível no schema; mantém compatibilidade
                cnae_principal=row[3],
                descricao_cnae=row[4] or "",
                matriz_filial=matriz_filial,
                endereco=endereco,
                cidade=row[11] or "",
                uf=row[12] or "",
                telefone_principal=telefone_principal,
                telefone_secundario=telefone_secundario,
                email=row[17] or None,
                data_inicio_atividade=data_inicio
            )
            
            leads.append(lead)
        
        t_map = perf_counter() - t_map_start
        t_total = perf_counter() - t0
        
        if DEBUG_ROTA:
            print(f"[DEBUG_ROTA] Mapeamento: {t_map:.2f}s | Total: {t_total:.2f}s | Leads: {len(leads)}")
        
        return leads
        
    except Exception as e:
        if con:
            con.close()
        # Mensagem de erro mais informativa para debugging sem vazar dados sensíveis
        print(f"Erro ao buscar leads enriquecidos: {e} -- params_len={len(params) if 'params' in locals() else 'n/a'}")
        import traceback
        traceback.print_exc()
        return []


def dedupe_leads_por_cnpj_basico(leads: List[Lead]) -> List[Lead]:
    """
    Remove duplicatas por CNPJ básico, mantendo a melhor opção.
    
    Critérios de prioridade:
    1. Matriz (se houver)
    2. Lead com endereço completo
    3. Lead com telefone
    4. Lead com email
    5. Primeiro encontrado
    
    Args:
        leads: Lista de leads a dedupe
        
    Returns:
        Lista de leads sem duplicatas
    """
    # Agrupa por CNPJ básico
    grupos: dict[str, List[Lead]] = {}
    for lead in leads:
        if lead.cnpj_basico not in grupos:
            grupos[lead.cnpj_basico] = []
        grupos[lead.cnpj_basico].append(lead)
    
    # Para cada grupo, escolhe o melhor
    leads_deduped: List[Lead] = []
    for cnpj_basico, grupo in grupos.items():
        if len(grupo) == 1:
            leads_deduped.append(grupo[0])
            continue
        
        # Ordena por prioridade
        def score_lead(lead: Lead) -> tuple:
            return (
                1 if lead.matriz_filial == "MATRIZ" else 0,
                1 if lead.visitavel else 0,
                1 if lead.telefone_principal else 0,
                1 if lead.email else 0
            )
        
        grupo_ordenado = sorted(grupo, key=score_lead, reverse=True)
        leads_deduped.append(grupo_ordenado[0])
    
    return leads_deduped


def buscar_cnae_por_texto_seguro(termo: str, limite: int = 15) -> List[tuple[str, str]]:
    """
    Busca CNAEs por texto de forma segura (parametrizada).
    
    Args:
        termo: Termo de busca
        limite: Limite de resultados
        
    Returns:
        Lista de tuplas (codigo, descricao)
    """
    con = get_connection()
    if not con:
        return []
    
    try:
        # Query parametrizada com LIKE
        query = """
            SELECT codigo, descricao 
            FROM cnaes 
            WHERE descricao LIKE ? 
            LIMIT ?
        """
        
        # Adiciona % para busca parcial
        termo_like = f"%{termo}%"
        
        rows = con.execute(query, [termo_like, limite]).fetchall()
        con.close()
        
        return [(row[0], row[1]) for row in rows]
        
    except Exception as e:
        if con:
            con.close()
        print(f"Erro ao buscar CNAE: {e}")
        return []


def listar_cidades_por_uf_seguro(uf: str) -> List[str]:
    """
    Lista cidades de uma UF de forma segura.
    
    Args:
        uf: Sigla da UF
        
    Returns:
        Lista de nomes de cidades
    """
    con = get_connection()
    if not con:
        return []
    
    try:
        if uf == "TODAS" or uf == "BRASIL":
            query = "SELECT DISTINCT descricao FROM municipios ORDER BY descricao"
            params: List[str] = []
        else:
            query = """
                SELECT DISTINCT m.descricao 
                FROM estabelecimentos e
                JOIN municipios m ON e.municipio = m.codigo
                WHERE e.uf = ?
                ORDER BY m.descricao
            """
            params = [uf]
        
        rows = con.execute(query, params).fetchall()
        con.close()
        
        return [row[0] for row in rows]
        
    except Exception as e:
        if con:
            con.close()
        print(f"Erro ao listar cidades: {e}")
        return []
