"""Modelos de texto: corpo HTML do ofício e texto do despacho (anotação do marcador)."""
import re
from html import escape, unescape

from .militares import Militar

_TAG_HTML = re.compile(r"<[^>]+>")
_SPLIT_P = re.compile(r"</p\s*>", re.I)
_OPEN_P = re.compile(r"<p[^>]*>", re.I)


def _texto_paragrafo(paragrafo: str) -> str:
    """Remove tags HTML que a IA às vezes devolve dentro do parágrafo."""
    texto = unescape((paragrafo or "").strip())
    texto = _TAG_HTML.sub("", texto)
    return " ".join(texto.split())


def _normalizar_paragrafos(paragrafos: list[str]) -> list[str]:
    """Separa blocos '<p>..</p>, <p>..</p>' e remove tags residualmente."""
    saida: list[str] = []
    for bruto in paragrafos:
        if not bruto or not str(bruto).strip():
            continue
        partes = _SPLIT_P.split(str(bruto)) if _SPLIT_P.search(str(bruto)) else [str(bruto)]
        for parte in partes:
            texto = _texto_paragrafo(_OPEN_P.sub("", parte).strip(" ,;"))
            if texto:
                saida.append(texto)
    return saida


def oficio_html(
    assunto: str,
    referencia: str,
    destinatario: str,
    paragrafos: list[str],
    signatario: Militar,
) -> str:
    """Corpo do ofício no padrão de estilos do editor do SEI MG."""
    corpo = "".join(
        f'<p class="Texto_Justificado_Recuo_Primeira_Linha">{escape(p)}</p>'
        for p in _normalizar_paragrafos(paragrafos)
    )
    linha_referencia = (
        f'<p class="Texto_Alinhado_Esquerda"><strong>Referência: {escape(referencia)}</strong></p>'
        if referencia
        else ""
    )
    vazio = '<p class="Texto_Justificado_Recuo_Primeira_Linha">&nbsp;</p>'
    return (
        f'<p class="Texto_Alinhado_Esquerda"><strong>Assunto: {escape(assunto)}</strong></p>'
        f"{linha_referencia}{vazio}"
        f'<p class="Texto_Justificado_Recuo_Primeira_Linha"><strong>{escape(destinatario)},</strong></p>'
        f"{vazio}{corpo}{vazio}"
        '<p class="Texto_Justificado_Recuo_Primeira_Linha">Respeitosamente,</p>'
        '<p style="margin:0 0 11px 0">&nbsp;</p>'
        f'<p class="Nome_Signatário">{escape(signatario.nome.upper())}, {escape(signatario.graduacao.upper())}</p>'
        f'<p class="Nome_Signatário">{escape(signatario.funcao.upper())}</p>'
    )


def paragrafos_html(paragrafos: list[str]) -> str:
    """Corpo em <p> simples (Despacho / Parecer Técnico: o SEI já traz o modelo)."""
    return "".join(f"<p>{escape(p)}</p>" for p in _normalizar_paragrafos(paragrafos))


def juntar_itens(itens: list[str]) -> str:
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def despacho(
    destinatario: Militar,
    documentos: list[str],
    assunto: str,
    complemento: str,
    assinatura: str,
) -> str:
    """
    Ex.: "Sr. Maj Rocha. Encaminho a V.Sa. para análise e despacho o Ofício 585 (151163165),
          que trata de <assunto>. <complemento>. Resp, Cap Cleyton."
    """
    inicio = f"{destinatario.tratamento} {destinatario.nome_guerra}".strip()
    verbo = "trata" if len(documentos) == 1 else "tratam"
    complemento = complemento.strip().rstrip(".")
    assunto = assunto.strip().rstrip(".")
    # "Resposta sobre..." -> "resposta sobre..."; siglas ("BIR ...") ficam como estão
    if assunto[:2].istitle():
        assunto = assunto[0].lower() + assunto[1:]
    texto = (
        f"{inicio}. {destinatario.encaminhamento} {juntar_itens(documentos)}, "
        f"que {verbo} de {assunto}. "
    )
    if complemento:
        texto += f"{complemento}. "
    return texto + f"{destinatario.despedida} {assinatura}."
