"""
Cadastro de autoridades (autoridades.json) para sugerir o vocativo do destinatário
a partir de quem assina o documento respondido.

Formato:
    {"autoridades": [{"nome": "...", "destinatario": "...", "sexo": "M|F", "PG": "..."}]}
sexo e PG são opcionais (registros sem eles usam só o destinatario, sem prefixo).
"""
import json
import unicodedata
from pathlib import Path

from .config import get_settings

# índice menor = posição mais alta na hierarquia
_HIERARQUIA = {
    "coronel": 1,
    "tenente coronel": 2,
    "major": 3,
    "capitao": 4,
    "1o tenente": 5,
    "1 tenente": 5,
    "2o tenente": 6,
    "2 tenente": 6,
    "subtenente": 7,
    "1o sargento": 8,
    "1 sargento": 8,
    "2o sargento": 9,
    "2 sargento": 9,
    "3o sargento": 10,
    "3 sargento": 10,
    "cabo": 11,
    "soldado": 12,
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.strip().lower()


def _normalizar_posto(texto: str) -> str:
    t = _normalizar(texto)
    t = t.replace("º", "o").replace("°", "o").replace("-", " ")
    t = "".join(c if c.isalnum() or c.isspace() else " " for c in t)
    return " ".join(t.split())


def _posicao_hierarquia(posto: str) -> int | None:
    chave = _normalizar_posto(posto)
    return _HIERARQUIA.get(chave)


def listar() -> list[dict[str, str]]:
    # lido a cada chamada: editar o JSON não exige reiniciar a API
    caminho = Path(get_settings().autoridades_path)
    if not caminho.is_file():
        return []
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    saida = []
    for a in dados.get("autoridades", []):
        nome = str(a.get("nome", "")).strip()
        destinatario = str(a.get("destinatario", "")).strip()
        if not nome or not destinatario:
            continue
        saida.append({
            "nome": nome,
            "destinatario": destinatario,
            "sexo": str(a.get("sexo", "")).strip(),
            "PG": str(a.get("PG", "")).strip(),
        })
    return saida


def resolver_destinatario(signatario: str) -> str | None:
    """Match exato (normalizado); senão inclusão (um contido no outro); senão None.
    Retorno inalterado: apenas a string 'destinatario' do cadastro.
    """
    autoridade = buscar_autoridade(signatario)
    return autoridade["destinatario"] if autoridade else None


def buscar_autoridade(signatario: str) -> dict | None:
    """Compara com 'nome': match exato normalizado; senão inclusão; senão None."""
    alvo = _normalizar(signatario)
    if not alvo:
        return None
    autoridades = listar()
    for item in autoridades:
        if _normalizar(item["nome"]) == alvo:
            return item
    for item in autoridades:
        nome = _normalizar(item["nome"])
        if nome in alvo or alvo in nome:
            return item
    return None


def buscar_autoridade_no_texto(trecho: str) -> dict | None:
    """Fallback: maior 'nome' de autoridade contido no trecho (normalizado)."""
    texto = _normalizar(trecho)
    if not texto:
        return None
    melhor: dict | None = None
    melhor_len = 0
    for item in listar():
        nome = _normalizar(item["nome"])
        if nome and nome in texto and len(nome) > melhor_len:
            melhor = item
            melhor_len = len(nome)
    return melhor


def montar_destinatario(autoridade: dict | None, posto_signatario: str | None) -> str | None:
    """
    "<Tratamento> <PG> BM, <destinatario>" conforme hierarquia e sexo.
    Sem autoridade → None. Sem posto do signatário → None.
    PG/sexo ausentes ou posto desconhecido → só o 'destinatario' (sem prefixo).
    """
    if not autoridade:
        return None
    dest = (autoridade.get("destinatario") or "").strip()
    if not dest:
        return None
    if not (posto_signatario or "").strip():
        return None

    pg = (autoridade.get("PG") or "").strip()
    sexo = (autoridade.get("sexo") or "").strip().upper()
    if not pg or sexo not in ("M", "F"):
        return dest

    pos_aut = _posicao_hierarquia(pg)
    pos_sig = _posicao_hierarquia(posto_signatario)
    if pos_aut is None or pos_sig is None:
        return dest

    if pos_aut <= pos_sig:
        tratamento = "Senhor" if sexo == "M" else "Senhora"
    else:
        tratamento = "Ao" if sexo == "M" else "À"
    return f"{tratamento} {pg} BM, {dest}"
