#!/usr/bin/env python3
"""Remove, em cada 'destinatario' de dados/autoridades.json, tudo até a primeira vírgula."""
import json
import sys
from pathlib import Path

ARQUIVO = Path("dados/autoridades.json")


def main() -> None:
    if not ARQUIVO.exists():
        sys.exit(f"Arquivo não encontrado: {ARQUIVO}")

    dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))

    alterados = 0
    sem_virgula = []

    for aut in dados.get("autoridades", []):
        destinatario = aut.get("destinatario", "")
        if "," not in destinatario:
            sem_virgula.append(aut.get("nome", destinatario))
            continue  # nada a remover; mantém como está
        novo = destinatario.split(",", 1)[1].strip()
        if novo != destinatario:
            aut["destinatario"] = novo
            alterados += 1

    ARQUIVO.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"{alterados} destinatários atualizados em {ARQUIVO}")
    if sem_virgula:
        print(f"Atenção: {len(sem_virgula)} sem vírgula (mantidos sem alteração):")
        for nome in sem_virgula:
            print(f"  - {nome}")


if __name__ == "__main__":
    main()