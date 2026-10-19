#!/usr/bin/env python3
"""Converte um txt de 'Nome e função' em dados/autoridades.json."""
import json
import re
import sys
from pathlib import Path

ENTRADA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("autoridades.txt")
SAIDA = Path("dados/autoridades.json")

# Sobrescreva o sexo de nomes cujo palpite automático erra.
# Chave: primeiro nome (minúsculo). Ex.: {"spinola": "M", "andrea": "F"}
OVERRIDES_SEXO = {}


def extrair_pg_nome(destinatario: str):
    """Retorna (PG, nome). PG = trecho antes do primeiro 'BM'; nome = trecho após 'BM' até a vírgula."""
    antes_virgula = destinatario.split(",", 1)[0]
    m = re.search(r"^(.*?)\bBM\b\s+(.+)$", antes_virgula)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Sem 'BM': sem PG, nome = trecho antes da vírgula
    return "", antes_virgula.strip()


def inferir_sexo(nome: str) -> str:
    """Heurística: primeiro nome terminado em 'a' -> F, senão M. Revise com OVERRIDES_SEXO."""
    primeiro = nome.split()[0].lower() if nome else ""
    if primeiro in OVERRIDES_SEXO:
        return OVERRIDES_SEXO[primeiro]
    return "F" if primeiro.endswith("a") else "M"


def main() -> None:
    if not ENTRADA.exists():
        sys.exit(f"Arquivo de entrada não encontrado: {ENTRADA}")

    autoridades = []
    for linha in ENTRADA.read_text(encoding="utf-8").splitlines():
        destinatario = linha.strip()
        if not destinatario:
            continue
        pg, nome = extrair_pg_nome(destinatario)
        autoridades.append({
            "nome": nome,
            "destinatario": destinatario,
            "sexo": inferir_sexo(nome),
            "PG": pg,
        })

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(
        json.dumps({"autoridades": autoridades}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{len(autoridades)} autoridades gravadas em {SAIDA}")


if __name__ == "__main__":
    main()