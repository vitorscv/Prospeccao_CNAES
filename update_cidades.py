from __future__ import annotations

import zipfile
from pathlib import Path

import duckdb
import pandas as pd


DB_FILE = Path("hunter_leads.db")
POPULATION_YEAR = 2025
CSV_CANDIDATES = [
    Path("dados/municipios.csv"),
    Path("dados IBGE/municipios.csv"),
    Path("../dados IBGE/municipios.csv"),
    Path(r"C:\Users\david\Documents\Facul\Analise e Big data\A3\dados IBGE\municipios.csv"),
]
POPULATION_CANDIDATES = [
    Path("dados/br_ibge_populacao_municipio.csv"),
    Path("dados IBGE/br_ibge_populacao_municipio.csv"),
    Path("../dados IBGE/br_ibge_populacao_municipio.csv"),
    Path(r"C:\Users\david\Documents\Facul\Analise e Big data\A3\dados IBGE\br_ibge_populacao_municipio.csv"),
]
ZIP_CANDIDATES = [
    Path("dados/MUNICCSV.zip"),
    Path("dados/Municipios.zip"),
]

BRAZIL_COORD_BOUNDS = {
    "lat": (-35.0, 6.0),
    "lon": (-75.0, -30.0),
}

UF_COORD_BOUNDS = {
    "11": {"lat": (-13.8, -7.0), "lon": (-66.9, -59.5)},  # RO
    "12": {"lat": (-11.3, -7.0), "lon": (-74.2, -66.4)},  # AC
    "13": {"lat": (-10.0, 2.5), "lon": (-74.0, -56.0)},  # AM
    "14": {"lat": (-1.8, 5.5), "lon": (-65.0, -58.5)},  # RR
    "15": {"lat": (-10.2, 3.2), "lon": (-59.2, -45.3)},  # PA
    "16": {"lat": (-1.5, 4.6), "lon": (-55.0, -49.4)},  # AP
    "17": {"lat": (-13.8, -5.0), "lon": (-51.0, -45.5)},  # TO
    "21": {"lat": (-10.6, -1.0), "lon": (-48.9, -41.7)},  # MA
    "22": {"lat": (-11.0, -2.6), "lon": (-46.6, -40.0)},  # PI
    "23": {"lat": (-8.0, -2.5), "lon": (-41.7, -37.0)},  # CE
    "24": {"lat": (-7.0, -4.8), "lon": (-38.8, -34.8)},  # RN
    "25": {"lat": (-8.5, -6.0), "lon": (-39.0, -34.6)},  # PB
    "26": {"lat": (-9.7, -7.0), "lon": (-41.6, -34.5)},  # PE
    "27": {"lat": (-10.6, -8.8), "lon": (-38.4, -35.1)},  # AL
    "28": {"lat": (-11.7, -9.4), "lon": (-38.4, -36.0)},  # SE
    "29": {"lat": (-18.5, -8.0), "lon": (-47.6, -37.0)},  # BA
    "31": {"lat": (-23.0, -14.0), "lon": (-51.2, -39.8)},  # MG
    "32": {"lat": (-21.5, -17.8), "lon": (-42.0, -39.6)},  # ES
    "33": {"lat": (-23.6, -20.5), "lon": (-45.0, -40.7)},  # RJ
    "35": {"lat": (-25.5, -19.7), "lon": (-53.2, -44.0)},  # SP
    "41": {"lat": (-27.1, -22.3), "lon": (-55.0, -47.5)},  # PR
    "42": {"lat": (-29.5, -25.8), "lon": (-54.1, -48.3)},  # SC
    "43": {"lat": (-34.0, -27.0), "lon": (-57.8, -49.5)},  # RS
    "50": {"lat": (-24.2, -17.0), "lon": (-58.4, -50.8)},  # MS
    "51": {"lat": (-18.5, -7.0), "lon": (-62.0, -50.0)},  # MT
    "52": {"lat": (-19.7, -12.4), "lon": (-53.3, -45.7)},  # GO
    "53": {"lat": (-16.2, -15.4), "lon": (-48.3, -47.2)},  # DF
}

COORD_DIVISORS = (1, 10, 100, 1000, 10000)


def _find_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _normalize_coordinate_by_uf(values: pd.Series, codigo_uf: pd.Series, axis: str) -> pd.Series:
    if values is None:
        return pd.Series(pd.NA, index=codigo_uf.index, dtype="Float64")

    numeric = pd.to_numeric(values, errors="coerce")
    uf_codes = codigo_uf.fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
    result = pd.Series(pd.NA, index=numeric.index, dtype="Float64")

    for idx, raw_value in numeric.items():
        if pd.isna(raw_value):
            continue

        uf_bounds = UF_COORD_BOUNDS.get(uf_codes.loc[idx], {}).get(axis)
        global_bounds = BRAZIL_COORD_BOUNDS[axis]
        selected = None

        if uf_bounds:
            for divisor in COORD_DIVISORS:
                candidate = float(raw_value) / divisor
                if uf_bounds[0] <= candidate <= uf_bounds[1]:
                    selected = candidate
                    break

        if selected is None:
            for divisor in COORD_DIVISORS:
                candidate = float(raw_value) / divisor
                if global_bounds[0] <= candidate <= global_bounds[1]:
                    selected = candidate
                    break

        result.loc[idx] = selected

    return result


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

    latitude = _normalize_coordinate_by_uf(df.get("latitude"), df["codigo_uf"], "lat")
    longitude = _normalize_coordinate_by_uf(df.get("longitude"), df["codigo_uf"], "lon")
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
