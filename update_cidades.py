from __future__ import annotations

import zipfile
from pathlib import Path

import duckdb
import pandas as pd


DB_FILE = Path("hunter_leads.db")
POPULATION_YEAR = 2025
CSV_CANDIDATES = [
    Path("dados/municipios.csv"),
    Path("../dados IBGE/municipios.csv"),
    Path(r"C:\Users\david\Documents\Facul\Analise e Big data\A3\dados IBGE\municipios.csv"),
]
POPULATION_CANDIDATES = [
    Path("dados/br_ibge_populacao_municipio.csv"),
    Path("../dados IBGE/br_ibge_populacao_municipio.csv"),
    Path(r"C:\Users\david\Documents\Facul\Analise e Big data\A3\dados IBGE\br_ibge_populacao_municipio.csv"),
]
ZIP_CANDIDATES = [
    Path("dados/MUNICCSV.zip"),
    Path("dados/Municipios.zip"),
]


def _find_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _normalize_brazil_coordinate(values: pd.Series, lower: float, upper: float) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")

    for _ in range(4):
        outside_bounds = numeric.notna() & ((numeric < lower) | (numeric > upper))
        if not outside_bounds.any():
            break
        numeric.loc[outside_bounds] = numeric.loc[outside_bounds] / 10

    still_invalid = numeric.notna() & ((numeric < lower) | (numeric > upper))
    numeric.loc[still_invalid] = pd.NA
    return numeric


def _read_population_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    required = {"ano", "id_municipio", "populacao"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"CSV de populacao sem colunas obrigatorias: {', '.join(sorted(missing))}")

    df["ano"] = pd.to_numeric(df["ano"], errors="coerce")
    df["populacao"] = pd.to_numeric(df["populacao"], errors="coerce")
    df = df.dropna(subset=["ano", "id_municipio", "populacao"])
    df = df[df["ano"] == POPULATION_YEAR].copy()
    if df.empty:
        raise ValueError(f"CSV de populacao sem registros para o ano {POPULATION_YEAR}")

    df["codigo_ibge"] = df["id_municipio"].astype(str).str.zfill(7)
    df = df.sort_values(["codigo_ibge", "ano"]).drop_duplicates("codigo_ibge", keep="last")
    return df[["codigo_ibge", "ano", "populacao"]]


def _merge_population(municipios: pd.DataFrame) -> tuple[pd.DataFrame, Path | None]:
    population_path = _find_existing(POPULATION_CANDIDATES)
    if not population_path:
        return municipios, None

    populacao = _read_population_csv(population_path)
    municipios = municipios.drop(columns=["populacao", "ano_populacao"], errors="ignore")
    municipios = municipios.merge(populacao, on="codigo_ibge", how="left")
    municipios = municipios.rename(columns={"ano": "ano_populacao"})
    return municipios, population_path


def _read_ibge_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")
    required = {"siafi_id", "nome"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"CSV IBGE sem colunas obrigatorias: {', '.join(sorted(missing))}")

    latitude = _normalize_brazil_coordinate(df.get("latitude"), -35.0, 6.0)
    longitude = _normalize_brazil_coordinate(df.get("longitude"), -75.0, -30.0)
    populacao = pd.to_numeric(df["populacao"], errors="coerce") if "populacao" in df.columns else pd.NA

    result = pd.DataFrame(
        {
            "codigo": df["siafi_id"].str.zfill(4),
            "descricao": df["nome"].str.upper(),
            "codigo_ibge": df.get("codigo_ibge", ""),
            "codigo_uf": df.get("codigo_uf", ""),
            "latitude": latitude,
            "longitude": longitude,
            "populacao": populacao,
            "ano_populacao": pd.NA,
            "capital": pd.to_numeric(df.get("capital"), errors="coerce"),
            "ddd": df.get("ddd", ""),
            "fuso_horario": df.get("fuso_horario", ""),
        }
    )
    return result.dropna(subset=["codigo"]).drop_duplicates(subset=["codigo"])


def _read_receita_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path, "r") as archive:
        with archive.open(archive.namelist()[0]) as file:
            df = pd.read_csv(
                file,
                sep=";",
                header=None,
                names=["codigo", "descricao"],
                dtype=str,
                encoding="latin1",
                on_bad_lines="skip",
            )

    df["codigo"] = df["codigo"].str.zfill(4)
    df["descricao"] = df["descricao"].str.upper()
    df["codigo_ibge"] = ""
    df["codigo_uf"] = ""
    df["latitude"] = pd.NA
    df["longitude"] = pd.NA
    df["populacao"] = pd.NA
    df["ano_populacao"] = pd.NA
    df["capital"] = pd.NA
    df["ddd"] = ""
    df["fuso_horario"] = ""
    return df.dropna(subset=["codigo"]).drop_duplicates(subset=["codigo"])


def load_municipios() -> tuple[pd.DataFrame, Path]:
    csv_path = _find_existing(CSV_CANDIDATES)
    if csv_path:
        return _read_ibge_csv(csv_path), csv_path

    zip_path = _find_existing(ZIP_CANDIDATES)
    if zip_path:
        return _read_receita_zip(zip_path), zip_path

    checked = CSV_CANDIDATES + ZIP_CANDIDATES
    raise FileNotFoundError(
        "Nenhum arquivo de municipios encontrado. Caminhos verificados:\n"
        + "\n".join(f"- {path}" for path in checked)
    )


def main() -> None:
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Banco nao encontrado: {DB_FILE}")

    df_municipios, source = load_municipios()
    df_municipios, population_source = _merge_population(df_municipios)
    df_populacao_2025 = None
    if population_source:
        df_populacao_2025 = _read_population_csv(population_source).rename(
            columns={"codigo_ibge": "id_municipio"}
        )

    con = duckdb.connect(str(DB_FILE))
    try:
        con.execute("CREATE OR REPLACE TABLE municipios AS SELECT * FROM df_municipios")
        con.execute("CREATE INDEX IF NOT EXISTS idx_municipios_codigo ON municipios(codigo)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_municipios_descricao ON municipios(descricao)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_municipios_codigo_ibge ON municipios(codigo_ibge)")

        total_populacao = 0
        if df_populacao_2025 is not None:
            con.execute("CREATE OR REPLACE TABLE populacao_municipios AS SELECT * FROM df_populacao_2025")
            con.execute("CREATE INDEX IF NOT EXISTS idx_populacao_municipios_id ON populacao_municipios(id_municipio)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_populacao_municipios_id_ano ON populacao_municipios(id_municipio, ano)")
            total_populacao = con.execute("SELECT COUNT(*) FROM populacao_municipios").fetchone()[0]

        total = con.execute("SELECT COUNT(*) FROM municipios").fetchone()[0]
        feira = con.execute(
            """
            SELECT codigo, descricao, latitude, longitude, populacao, ano_populacao
            FROM municipios
            WHERE descricao = 'FEIRA DE SANTANA'
            """
        ).fetchone()
        join_teste = con.execute(
            """
            SELECT e.municipio, m.descricao, e.uf, m.latitude, m.longitude, m.populacao, COUNT(*) AS total
            FROM estabelecimentos e
            JOIN municipios m ON e.municipio = m.codigo
            WHERE e.municipio IN ('7107', '6001', '3515', '3849')
            GROUP BY e.municipio, m.descricao, e.uf, m.latitude, m.longitude, m.populacao
            ORDER BY total DESC
            """
        ).fetchall()
    finally:
        con.close()

    print(f"Fonte: {source}")
    if population_source:
        print(f"Fonte populacao: {population_source}")
        print(f"Populacao 2025 importada: {total_populacao}")
    print(f"Municipios importados: {total}")
    print(f"Teste Feira de Santana: {feira}")
    print(f"Teste join CNPJ x municipios: {join_teste}")


if __name__ == "__main__":
    main()
