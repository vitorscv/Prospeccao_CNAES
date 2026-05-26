"""
Servico de exportacao de leads para Excel.
"""
from __future__ import annotations

import importlib.util
from dataclasses import asdict, is_dataclass
from io import BytesIO
from typing import Any, Dict, List

import pandas as pd


def _excel_engine() -> str:
    if importlib.util.find_spec("xlsxwriter") is not None:
        return "xlsxwriter"
    if importlib.util.find_spec("openpyxl") is not None:
        return "openpyxl"
    raise ModuleNotFoundError("Instale xlsxwriter ou openpyxl para exportar arquivos Excel.")


def _column_width(df: pd.DataFrame, col: str, max_width: int | None = None) -> int:
    if df.empty:
        width = len(str(col)) + 2
    else:
        width = max(df[col].astype(str).map(len).max(), len(str(col))) + 2

    return min(width, max_width) if max_width else width


def _format_xlsxwriter(
    writer: pd.ExcelWriter,
    sheet_name: str,
    df: pd.DataFrame,
    max_width: int | None,
) -> None:
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    text_format = workbook.add_format({"num_format": "@", "align": "left", "valign": "vcenter"})

    for i, col in enumerate(df.columns):
        worksheet.set_column(i, i, _column_width(df, col, max_width), text_format)


def _format_openpyxl(
    writer: pd.ExcelWriter,
    sheet_name: str,
    df: pd.DataFrame,
    max_width: int | None,
) -> None:
    from openpyxl.styles import Alignment
    from openpyxl.utils import get_column_letter

    worksheet = writer.sheets[sheet_name]
    alignment = Alignment(horizontal="left", vertical="center")

    for i, col in enumerate(df.columns, start=1):
        letter = get_column_letter(i)
        worksheet.column_dimensions[letter].width = _column_width(df, col, max_width)
        for cell in worksheet[letter]:
            cell.number_format = "@"
            cell.alignment = alignment


def _write_excel(
    output: BytesIO,
    sheets: Dict[str, pd.DataFrame],
    max_width: int | None = None,
) -> None:
    engine = _excel_engine()

    with pd.ExcelWriter(output, engine=engine) as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=sheet_name)

        for sheet_name, df in sheets.items():
            if engine == "xlsxwriter":
                _format_xlsxwriter(writer, sheet_name, df, max_width)
            else:
                _format_openpyxl(writer, sheet_name, df, max_width)


def _to_dataframe(items: List[Any] | pd.DataFrame) -> pd.DataFrame:
    if isinstance(items, pd.DataFrame):
        return items.copy()

    rows = []
    for item in items:
        if isinstance(item, dict):
            rows.append(item)
        elif is_dataclass(item):
            rows.append(asdict(item))
        else:
            rows.append(getattr(item, "__dict__", {}))

    return pd.DataFrame(rows)


def gerar_excel_de_dtos(lista_dtos: List[Any] | pd.DataFrame) -> bytes:
    """
    Gera Excel a partir de lista de DTOs, dicionarios ou DataFrame.
    """
    output = BytesIO()
    df = _to_dataframe(lista_dtos)

    mapa_colunas = {
        "nome_fantasia": "Nome Fantasia",
        "cnpj": "CNPJ",
        "telefone_principal": "Telefone 1",
        "telefone_secundario": "Telefone 2",
        "email": "E-mail",
        "cidade": "Cidade",
        "uf": "UF",
        "cnae": "CNAE",
    }

    df = df.rename(columns=mapa_colunas)
    _write_excel(output, {"Leads": df})
    return output.getvalue()


def gerar_excel_leads_enriquecidos(leads: List[Any]) -> bytes:
    """
    Gera Excel com leads enriquecidos.
    """
    output = BytesIO()
    dados: List[Dict[str, Any]] = []

    for lead in leads:
        def attr(obj: Any, name: str, default: Any = "") -> Any:
            if isinstance(obj, dict):
                return obj.get(name, default) or default
            return getattr(obj, name, default) or default

        endereco = attr(lead, "endereco", None)
        row: Dict[str, Any] = {
            "Nome Fantasia": attr(lead, "nome_fantasia"),
            "Razao Social": attr(lead, "razao_social"),
            "CNPJ": attr(lead, "cnpj"),
            "CNPJ Basico": attr(lead, "cnpj_basico"),
            "Matriz/Filial": attr(lead, "matriz_filial"),
            "CNAE": attr(lead, "cnae_principal"),
            "Descricao CNAE": attr(lead, "descricao_cnae"),
            "Telefone 1": attr(lead, "telefone_principal"),
            "Telefone 2": attr(lead, "telefone_secundario"),
            "E-mail": attr(lead, "email"),
            "Logradouro": getattr(endereco, "logradouro", "") if endereco else "",
            "Numero": getattr(endereco, "numero", "") if endereco else "",
            "Complemento": getattr(endereco, "complemento", "") if endereco else "",
            "Bairro": getattr(endereco, "bairro", "") if endereco else "",
            "CEP": getattr(endereco, "cep", "") if endereco else "",
            "Cidade": attr(lead, "cidade"),
            "UF": attr(lead, "uf"),
            "Data Inicio Atividade": (
                attr(lead, "data_inicio_atividade").isoformat()
                if attr(lead, "data_inicio_atividade", None)
                else ""
            ),
            "Anos de Atividade": attr(lead, "anos_atividade"),
            "Link Google Maps": attr(lead, "link_maps"),
        }

        score = attr(lead, "score", None)
        if score is not None:
            row["Score"] = score
            row["Segmento"] = attr(lead, "segmento")
            reasons = attr(lead, "reasons", None)
            if isinstance(reasons, (list, tuple)):
                row["Razoes Score"] = " | ".join(reasons)

        dados.append(row)

    df = pd.DataFrame(dados)
    _write_excel(output, {"Leads": df}, max_width=50)
    return output.getvalue()


def gerar_excel_roteiro(route_plan: Any, incluir_links: bool = True) -> bytes:
    """
    Gera Excel com roteiro de visitas.
    """
    output = BytesIO()
    dados: List[Dict[str, Any]] = []

    for dia_plan in route_plan.dias:
        for stop in dia_plan.stops:
            lead = stop.lead

            def attr(obj: Any, name: str, default: Any = "") -> Any:
                if isinstance(obj, dict):
                    return obj.get(name, default) or default
                return getattr(obj, name, default) or default

            endereco = attr(lead, "endereco", None)
            row: Dict[str, Any] = {
                "Dia": dia_plan.dia,
                "Ordem": stop.ordem,
                "Empresa": attr(lead, "nome_fantasia"),
                "CNPJ": attr(lead, "cnpj"),
                "Endereco": getattr(endereco, "formatado", "") if endereco else "",
                "Cidade": attr(lead, "cidade"),
                "UF": attr(lead, "uf"),
                "Telefone": attr(lead, "telefone_principal"),
                "Email": attr(lead, "email"),
                "Score": attr(lead, "score", 0),
                "Segmento": attr(lead, "segmento", ""),
            }

            if incluir_links:
                row["Link Maps"] = attr(lead, "link_maps")

            if getattr(stop, "observacoes", None):
                row["Observacoes"] = stop.observacoes

            dados.append(row)

    resumo_dados = [
        {
            "Dia": dia_plan.dia,
            "Total Visitas": dia_plan.total_visitas,
            "Score Medio": f"{dia_plan.score_medio:.1f}",
            "Link Rota Dia": dia_plan.link_maps_rota if incluir_links else "",
        }
        for dia_plan in route_plan.dias
    ]

    _write_excel(
        output,
        {
            "Roteiro": pd.DataFrame(dados),
            "Resumo": pd.DataFrame(resumo_dados),
        },
        max_width=50,
    )
    return output.getvalue()
