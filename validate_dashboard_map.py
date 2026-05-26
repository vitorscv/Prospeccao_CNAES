from src.database.repository import buscar_dados_dashboard_executivo


def bubble_size(value: float, total: int) -> float:
    if total <= 0 or value <= 0:
        return 6
    share = min(value / total, 1) ** 0.5
    return round(min(max(6 + share * 38, 6), 44), 2)


def main() -> None:
    cnaes = ["2392300", "1091102", "4721102", "4330403"]

    for cnae in cnaes:
        dados = buscar_dados_dashboard_executivo(lista_cnaes=[cnae])
        mapa = dados.get("mapa")
        if mapa is None or mapa.empty:
            print(f"{cnae}: sem dados de mapa")
            continue

        total = int(dados["kpis"].iloc[0]["total_empresas"])
        top = mapa.sort_values("quantidade", ascending=False).iloc[0]
        share_top = float(top["quantidade"]) / total * 100 if total else 0
        bubble_top = bubble_size(float(top["quantidade"]), total)

        print(
            f"{cnae}: total={total:,} | cidades_mapa={len(mapa)} | "
            f"min={int(mapa['quantidade'].min()):,} | max={int(mapa['quantidade'].max()):,} | "
            f"top={top['cidade']}-{top['uf']} | share_top={share_top:.2f}% | "
            f"diametro_bolha_top={bubble_top}px"
        )


if __name__ == "__main__":
    main()
