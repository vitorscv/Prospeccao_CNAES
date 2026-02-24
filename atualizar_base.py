import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urljoin

import requests

BASE_INDEX = "https://dadosabertos.rfb.gov.br/CNPJ/"
PASTA_DADOS = Path("dados")
ARQUIVOS_NECESSARIOS = ["CNAECNV.zip"] + [f"ESTABELE{i}.zip" for i in range(10)]


def _listar_links_html(url: str) -> list[str]:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    html = resp.text
    # pega hrefs simples
    return re.findall(r'href="([^"]+)"', html, flags=re.IGNORECASE)


def descobrir_pasta_mais_recente() -> str:
    links = _listar_links_html(BASE_INDEX)

    # Ex.: 2025-12/, 2026-01/, etc.
    pastas = []
    for link in links:
        m = re.match(r"(\d{4}-\d{2})/?$", link.strip("/"))
        if m:
            pastas.append(m.group(1))

    if not pastas:
        raise RuntimeError("Não encontrei pastas de período no índice da Receita.")

    pastas.sort()
    return pastas[-1]  # mais recente


def baixar_arquivo(url: str, destino: Path, sobrescrever: bool = True) -> None:
    if destino.exists() and not sobrescrever:
        return

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(destino, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def atualizar_zips_receita() -> dict:
    PASTA_DADOS.mkdir(exist_ok=True)

    periodo = descobrir_pasta_mais_recente()
    base_mes = urljoin(BASE_INDEX, f"{periodo}/")

    # cria backup simples da pasta dados (opcional, mas útil)
    backup_dir = Path("dados_backup")
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(exist_ok=True)

    baixados = []
    falhas = []

    for nome in ARQUIVOS_NECESSARIOS:
        url = urljoin(base_mes, nome)
        destino = PASTA_DADOS / nome

        try:
            # backup do arquivo anterior
            if destino.exists():
                shutil.copy2(destino, backup_dir / nome)

            baixar_arquivo(url, destino, sobrescrever=True)
            baixados.append(nome)
        except Exception as e:
            falhas.append((nome, str(e)))

    return {
        "periodo": periodo,
        "base_mes": base_mes,
        "baixados": baixados,
        "falhas": falhas,
    }


def recriar_banco() -> tuple[bool, str]:
    """
    Executa seu script atual de montagem do banco.
    """
    try:
        proc = subprocess.run(
            ["python", "setup_banco_completo.py"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return False, proc.stderr or proc.stdout
        return True, proc.stdout
    except Exception as e:
        return False, str(e)


def atualizar_base_completa() -> dict:
    etapa1 = atualizar_zips_receita()

    if etapa1["falhas"]:
        return {
            "ok": False,
            "etapa": "download",
            "detalhes": etapa1,
            "log": "Falha no download de um ou mais arquivos.",
        }

    ok_db, log_db = recriar_banco()
    return {
        "ok": ok_db,
        "etapa": "banco" if ok_db else "rebuild_banco",
        "detalhes": etapa1,
        "log": log_db,
    }
