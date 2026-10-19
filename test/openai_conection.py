"""
Testa a OPENAI_API_KEY do .env (ou passada como argumento).

Uso:
    python test/openai_conection.py
    python test/openai_conection.py sk-...
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, AuthenticationError, DefaultHttpxClient, OpenAI, OpenAIError

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

chave = sys.argv[1] if len(sys.argv) > 1 else os.getenv("OPENAI_API_KEY", "")
modelo = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
proxy = os.getenv("OPENAI_PROXY") or None

if not chave:
    sys.exit("OPENAI_API_KEY vazia: defina no .env ou passe como argumento")

print(f"Chave: {chave[:7]}...{chave[-4:]} | modelo: {modelo} | proxy: {proxy or '-'}")

cliente = OpenAI(
    api_key=chave,
    timeout=30,
    http_client=DefaultHttpxClient(proxy=proxy) if proxy else None,
)

try:
    resposta = cliente.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": "Responda apenas: OK"}],
        max_tokens=5,
    )
except AuthenticationError:
    sys.exit("FALHA: chave inválida ou revogada (401)")
except APIConnectionError as e:
    sys.exit(f"FALHA: sem conexão com a OpenAI (rede/proxy): {e}")
except OpenAIError as e:
    sys.exit(f"FALHA: {type(e).__name__}: {e}")

print(f"SUCESSO: {resposta.choices[0].message.content!r} (tokens: {resposta.usage.total_tokens})")
