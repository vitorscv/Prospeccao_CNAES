"""
Repositório para consultas na tabela de estabelecimentos.
Todas as queries são parametrizadas para evitar SQL injection.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from src.database.connection import get_connection
from src.models.lead import Endereco, Lead


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
    con = get_connection()
    if not con:
        return []
    
    try:
        # Monta placeholders para CNAEs (?, ?, ?)
        placeholders_cnae = ", ".join(["?" for _ in lista_cnaes])
        
        # Inicia lista de parâmetros
        params: List[str | int] = list(lista_cnaes)
        
        # Filtro de UF
        filtro_uf = ""
        if uf and uf != "BRASIL":
            filtro_uf = "AND e.uf = ?"
            params.append(uf)
        
        # Filtro de cidade (precisa buscar código do município)
        filtro_cidade = ""
        if cidade and cidade != "TODAS":
            # Busca código da cidade de forma segura
            codigo_cidade = con.execute(
                "SELECT codigo FROM municipios WHERE descricao = ? LIMIT 1",
                [cidade]
            ).fetchone()
            
            if codigo_cidade:
                filtro_cidade = "AND e.municipio = ?"
                params.append(codigo_cidade[0])
        
        # Filtro de matriz/filial
        filtro_matriz = ""
        if somente_matriz:
            filtro_matriz = "AND e.matriz_filial = ?"
            params.append("1")  # 1 = Matriz
        
        # Query principal
        query = f"""
            SELECT 
                e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv AS cnpj,
                e.cnpj_basico,
                e.nome_fantasia,
                e.razao_social,
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
            FROM estabelecimentos e
            LEFT JOIN municipios m ON e.municipio = m.codigo
            LEFT JOIN cnaes c ON e.cnae_principal = c.codigo
            WHERE e.cnae_principal IN ({placeholders_cnae})
            AND e.situacao_cadastral = '02'
            {filtro_uf}
            {filtro_cidade}
            {filtro_matriz}
            LIMIT ?
        """
        
        params.append(limite)
        
        # Executa query
        rows = con.execute(query, params).fetchall()
        con.close()
        
        # Converte para objetos Lead
        leads: List[Lead] = []
        for row in rows:
            # Monta endereço
            endereco = None
            if row[7]:  # logradouro
                endereco = Endereco(
                    logradouro=row[7] or "",
                    numero=row[8] or "",
                    bairro=row[9] or "",
                    cep=row[10] or "",
                    complemento=row[11] or None,
                    cidade=row[12] or "",
                    uf=row[13] or ""
                )
            
            # Formata telefones
            telefone_principal = None
            if row[14] and row[15]:  # ddd_1 e telefone_1
                telefone_principal = f"{row[14]} {row[15]}"
            
            telefone_secundario = None
            if row[16] and row[17]:  # ddd_2 e telefone_2
                telefone_secundario = f"{row[16]} {row[17]}"
            
            # Converte data de início de atividade
            data_inicio = None
            if row[19]:
                try:
                    # Formato esperado: YYYYMMDD ou YYYY-MM-DD
                    data_str = str(row[19])
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
                        data_inicio = datetime.fromisoformat(str(row[19])).date()
                except (ValueError, TypeError):
                    pass
            
            # Determina matriz/filial
            matriz_filial = "MATRIZ" if row[6] == "1" else "FILIAL"
            
            lead = Lead(
                cnpj=row[0],
                cnpj_basico=row[1],
                nome_fantasia=row[2] or "",
                razao_social=row[3] or None,
                cnae_principal=row[4],
                descricao_cnae=row[5] or "",
                matriz_filial=matriz_filial,
                endereco=endereco,
                cidade=row[12] or "",
                uf=row[13] or "",
                telefone_principal=telefone_principal,
                telefone_secundario=telefone_secundario,
                email=row[18] or None,
                data_inicio_atividade=data_inicio
            )
            
            leads.append(lead)
        
        return leads
        
    except Exception as e:
        if con:
            con.close()
        print(f"Erro ao buscar leads enriquecidos: {e}")
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
