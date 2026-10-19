"""
Cadastro dos militares (dadosmil.json), usado para o signatário do ofício,
o texto do despacho e a atribuição do processo.

Formato (índices a partir de 0):
    [0] nome, [1] nome de guerra, [2] tratamento, [3] despedida, [4] encaminhamento,
    [5] sigla (ex.: "Cel BM"), [6] posto/graduação (ex.: "Coronel"), [7] função.
Registros com 7 elementos (sem [6] posto): função fica no antigo índice 6; posto = "".
"""
import json
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import get_settings


@dataclass(frozen=True)
class Militar:
    cpf: str
    nome: str
    nome_guerra: str
    tratamento: str  # "Sr.", "Sra." ou vazio
    despedida: str  # "Resp," / "Att,"
    encaminhamento: str  # "Encaminho a V.Sa. para análise e despacho"
    graduacao: str  # sigla, índice [5]
    posto: str = ""  # posto por extenso, índice [6]; vazio se ausente
    funcao: str = ""  # índice [7] (ou [6] no formato antigo de 7 itens)

    def to_dict(self) -> dict:
        return asdict(self)


def normalizar_cpf(cpf: str) -> str:
    # o SEI exibe o CPF com 11 dígitos; o JSON às vezes perde o zero à esquerda
    return "".join(c for c in cpf if c.isdigit()).zfill(11)


def _normalizar_frase(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.strip().lower().split())


def _campos_militar(campos: list) -> tuple[str, str, str, str, str, str, str, str]:
    """Devolve (nome, guerra, tratamento, despedida, encaminhamento, graduacao, posto, funcao).
    Índices 0-based: [5]=sigla, [6]=posto, [7]=função. Com 7 itens: [6]=função e posto="".
    """
    c = [str(x).strip() for x in campos]
    if len(c) >= 8:
        return c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7]
    c = c + [""] * (7 - len(c))
    return c[0], c[1], c[2], c[3], c[4], c[5], "", c[6]


def listar() -> list[Militar]:
    # lido a cada chamada: editar o JSON não exige reiniciar a API
    caminho = Path(get_settings().dadosmil_path)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    militares = []
    for cpf, campos in dados.items():
        militares.append(Militar(normalizar_cpf(cpf), *_campos_militar(campos)))
    return sorted(militares, key=lambda m: m.nome_guerra)


def obter(cpf: str) -> Militar:
    alvo = normalizar_cpf(cpf)
    for militar in listar():
        if militar.cpf == alvo:
            return militar
    raise ValueError(f"CPF {cpf} não encontrado em {get_settings().dadosmil_path}")


def sugerir_signatario_cpf(conteudo_documento: str) -> str | None:
    """
    CPF do militar cuja função [7] aparece na íntegra no documento respondido.
    1 match → CPF; 0 → None; vários → o de função mais longa se uma contém a outra; senão None.
    """
    texto = _normalizar_frase(conteudo_documento)
    if not texto:
        return None
    candidatos: list[tuple[Militar, str]] = []
    for m in listar():
        if not m.funcao.strip():
            continue
        frase = _normalizar_frase(m.funcao)
        if frase and frase in texto:
            candidatos.append((m, frase))
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0][0].cpf
    # preferir a função mais longa quando uma contém a outra
    maximais = [
        (m, f) for m, f in candidatos
        if not any(f != g and f in g for _, g in candidatos)
    ]
    if len(maximais) == 1:
        return maximais[0][0].cpf
    return None


def conteudo_documento_respondido(documentos: dict[str, str], referencia: str) -> str:
    """Concatena o(s) documento(s) cujo nome corresponde à referência."""
    ref = referencia.strip().lower()
    if not ref:
        return ""
    partes = [texto for nome, texto in documentos.items() if ref in nome.lower()]
    return "\n".join(partes)
