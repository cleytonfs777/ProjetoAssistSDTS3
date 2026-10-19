#!/usr/bin/env python3
"""Em cada lista de dadosmil.json, lê o 6º elemento (posto abreviado, ex.: 'Cel BM')
e insere o posto por extenso (ex.: 'Coronel') como 7º elemento."""
import json
import shutil
import sys
from pathlib import Path

ARQUIVO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dadosmil.json")

POSTOS = {
    "cel bm": "Coronel",
    "ten-cel bm": "Tenente-Coronel",
    "maj bm": "Major",
    "cap bm": "Capitão",
    "ten bm": "Tenente",
    "sgt bm": "Sargento",
    "cb bm": "Cabo",
    "sd bm": "Soldado",
}

IDX_ABREV = 5   # 6º elemento
IDX_NOVO = 6    # 7º elemento (o antigo 7º, a função, passa a ser o 8º)


def normalizar(txt: str) -> str:
    return " ".join(txt.split()).lower()


def main() -> None:
    if not ARQUIVO.exists():
        sys.exit(f"Arquivo não encontrado: {ARQUIVO}")

    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        sys.exit("Esperava um objeto JSON {chave: [lista]} na raiz.")

    shutil.copy(ARQUIVO, ARQUIVO.with_suffix(".bak.json"))  # backup

    alterados, ja_feitos, sem_mapa, curtos = 0, 0, [], []

    for chave, lista in dados.items():
        if not isinstance(lista, list) or len(lista) <= IDX_ABREV:
            curtos.append(chave)
            continue

        extenso = POSTOS.get(normalizar(str(lista[IDX_ABREV])))
        if extenso is None:
            sem_mapa.append((chave, lista[IDX_ABREV]))
            extenso = ""  # mantém a estrutura uniforme

        # idempotência: já existe o posto por extenso na posição 7
        if len(lista) > IDX_NOVO and extenso and lista[IDX_NOVO] == extenso:
            ja_feitos += 1
            continue

        lista.insert(IDX_NOVO, extenso)
        alterados += 1

    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=4), encoding="utf-8")

    print(f"{alterados} registros alterados, {ja_feitos} já estavam prontos.")
    if curtos:
        print(f"Atenção: {len(curtos)} listas com menos de 6 elementos (ignoradas): {curtos}")
    if sem_mapa:
        print(f"Atenção: {len(sem_mapa)} postos sem correspondência (inseriu string vazia):")
        for chave, valor in sem_mapa:
            print(f"  - {chave}: {valor!r}")


if __name__ == "__main__":
    main()