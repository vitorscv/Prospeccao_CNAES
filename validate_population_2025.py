from __future__ import annotations

import duckdb


def main() -> None:
    con = duckdb.connect("hunter_leads.db", read_only=True)
    try:
        resumo = con.execute(
            """
            SELECT
                COUNT(*) AS municipios,
                COUNT(populacao) AS municipios_com_populacao,
                MIN(ano_populacao) AS menor_ano,
                MAX(ano_populacao) AS maior_ano
            FROM municipios
            """
        ).fetchone()

        sem_populacao = con.execute(
            """
            SELECT codigo, descricao, codigo_ibge
            FROM municipios
            WHERE populacao IS NULL
            ORDER BY descricao
            """
        ).fetchall()

        exemplo_relativo = con.execute(
            """
            SELECT
                m.descricao,
                e.uf,
                COUNT(*) AS empresas,
                m.populacao,
                ROUND(COUNT(*) * 10000.0 / m.populacao, 2) AS empresas_por_10k
            FROM estabelecimentos e
            JOIN municipios m ON e.municipio = m.codigo
            WHERE e.situacao_cadastral = '02'
              AND e.cnae_principal = '4711302'
              AND m.populacao IS NOT NULL
            GROUP BY m.descricao, e.uf, m.populacao
            ORDER BY empresas DESC
            LIMIT 5
            """
        ).fetchall()

        tabelas = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        populacao_2025 = None
        join_populacao_2025 = None
        if "populacao_municipios" in tabelas:
            populacao_2025 = con.execute(
                """
                SELECT
                    COUNT(*) AS linhas,
                    COUNT(DISTINCT id_municipio) AS municipios,
                    MIN(ano) AS menor_ano,
                    MAX(ano) AS maior_ano,
                    COUNT(populacao) AS com_populacao
                FROM populacao_municipios
                """
            ).fetchone()
            join_populacao_2025 = con.execute(
                """
                SELECT
                    COUNT(*) AS municipios,
                    COUNT(p.populacao) AS municipios_com_populacao_2025
                FROM municipios m
                LEFT JOIN populacao_municipios p
                  ON LPAD(CAST(m.codigo_ibge AS VARCHAR), 7, '0') = LPAD(CAST(p.id_municipio AS VARCHAR), 7, '0')
                 AND TRY_CAST(p.ano AS INTEGER) = 2025
                """
            ).fetchone()
    finally:
        con.close()

    print("Resumo municipios:", resumo)
    print("Municipios sem populacao:", sem_populacao)
    print("Resumo populacao_municipios:", populacao_2025)
    print("Join municipios x populacao_municipios 2025:", join_populacao_2025)
    print("Exemplo relativo CNAE 4711302:", exemplo_relativo)


if __name__ == "__main__":
    main()
