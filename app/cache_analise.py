"""Cache em memória dos documentos lidos na análise prévia (1 worker = memória local)."""
import time
import uuid
from dataclasses import dataclass

TTL_S = 30 * 60


@dataclass
class EntradaAnalise:
    documentos: dict[str, str]
    processo: str
    referencia: str
    expira_em: float


_cache: dict[str, EntradaAnalise] = {}


def guardar(documentos: dict[str, str], processo: str, referencia: str) -> str:
    _expurgar()
    id_analise = uuid.uuid4().hex
    _cache[id_analise] = EntradaAnalise(
        documentos=documentos,
        processo=processo,
        referencia=referencia,
        expira_em=time.monotonic() + TTL_S,
    )
    return id_analise


def obter(id_analise: str) -> EntradaAnalise | None:
    _expurgar()
    return _cache.get(id_analise)


def _expurgar() -> None:
    agora = time.monotonic()
    for chave in [k for k, v in _cache.items() if v.expira_em <= agora]:
        del _cache[chave]
