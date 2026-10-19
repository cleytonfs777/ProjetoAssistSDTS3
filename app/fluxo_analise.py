"""
Etapa prévia opcional: lê o processo, analisa a demanda com a IA e sugere
assunto / signatário / destinatário / 3 opções. NÃO grava nada no SEI.
"""
from typing import Callable

from . import autoridades, cache_analise, ia, militares
from .browser import browser_manager
from .pages.login_page import LoginPage
from .pages.processo_page import ProcessoPage
from .schemas import AnaliseDemandaRequest

Emitir = Callable[[dict], None]


def status(emitir: Emitir, etapa: str, mensagem: str, progresso: int, tipo: str = "info") -> None:
    print(f"[DEBUG][analise] [{progresso}%] {mensagem}", flush=True)
    emitir({"tipo": tipo, "etapa": etapa, "mensagem": mensagem, "progresso": progresso})


def _posto_do_cpf(cpf: str) -> str | None:
    if not (cpf or "").strip():
        return None
    try:
        posto = militares.obter(cpf).posto
    except ValueError:
        return None
    return posto or None


async def executar(req: AnaliseDemandaRequest, emitir: Emitir) -> None:
    async with browser_manager.context() as ctx:
        page = await ctx.new_page()
        try:
            status(emitir, "login", "Acessando o SEI...", 5)
            await LoginPage(page).login()

            status(emitir, "processo", f"Abrindo o processo {req.processo}...", 15)
            proc = ProcessoPage(page)
            await proc.abrir_processo(req.processo)

            def ao_ler(nome: str, posicao: int, total: int) -> None:
                status(emitir, "leitura", f"Lendo documento {posicao}/{total}: {nome}", 20 + 40 * posicao // total)

            status(emitir, "leitura", "Lendo os documentos do processo...", 20)
            documentos = await proc.ler_documentos(ao_ler)
            status(emitir, "leitura", f"{len(documentos)} documento(s) lido(s)", 65, "success")

            status(emitir, "ia", "Analisando a demanda com a IA...", 70)
            analise = await ia.analisar_demanda(documentos, req.referencia, req.complementar)
            status(emitir, "ia", "Análise concluída", 90, "success")

            id_analise = cache_analise.guardar(documentos, req.processo, req.referencia)
            conteudo_ref = militares.conteudo_documento_respondido(documentos, req.referencia)

            signatario_cpf_sugerido = militares.sugerir_signatario_cpf(conteudo_ref)
            cpf_posto = (req.signatario_cpf or "").strip() or signatario_cpf_sugerido
            posto = _posto_do_cpf(cpf_posto)

            nome_ia = (analise.get("signatario_documento_respondido") or "").strip()
            autoridade = autoridades.buscar_autoridade(nome_ia) if nome_ia else None
            if autoridade is None and conteudo_ref:
                autoridade = autoridades.buscar_autoridade_no_texto(conteudo_ref[-800:])

            destinatario_sugerido = autoridades.montar_destinatario(autoridade, posto)

            resultado = {
                "id_analise": id_analise,
                "processo": req.processo,
                "referencia": req.referencia,
                "assunto": analise["assunto"],
                "signatario_documento_respondido": analise["signatario_documento_respondido"],
                "signatario_cpf_sugerido": signatario_cpf_sugerido,
                "autoridade": autoridade,
                "destinatario_sugerido": destinatario_sugerido,
                "opcoes": analise["opcoes"],
                "documentos": list(documentos),
            }
            status(emitir, "fim", "Análise concluída: nada foi gravado no SEI", 100, "success")
            emitir({"tipo": "resultado", "dados": resultado})
        finally:
            await page.close()
