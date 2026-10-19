"""
Fluxo completo do ofício de resposta:

  1. login e abertura do processo
  2. leitura de todos os documentos (JSON {nome: conteúdo})
  3. IA (OpenAI) redige os parágrafos a partir do JSON + formulário
  4. parágrafos entram no modelo HTML do ofício
  5. criação do ofício no processo
  6. despacho: marcador com a anotação montada a partir do dadosmil.json
  7. atribuição do processo ao militar escolhido

Cada etapa avisa o progresso por `emitir(evento)`; a rota envia esses eventos à
interface em tempo real. O último evento tem tipo "resultado".
"""
from typing import Callable

from . import autoridades, cache_analise, ia, militares, modelos
from .browser import browser_manager
from .config import get_settings
from .pages.login_page import LoginPage
from .pages.processo_page import ProcessoPage
from .schemas import OficioRespostaRequest

Emitir = Callable[[dict], None]
NOME_OFICIO_PREVIA = "Ofício nº (a gerar)"
# tamanho típico do nome na árvore, ex.: "Ofício 585 (151163165)"
NOME_OFICIO_ESTIMADO = "Ofício 0000 (000000000)"


def status(emitir: Emitir, etapa: str, mensagem: str, progresso: int, tipo: str = "info") -> None:
    print(f"[DEBUG][fluxo] [{progresso}%] {mensagem}", flush=True)
    emitir({"tipo": tipo, "etapa": etapa, "mensagem": mensagem, "progresso": progresso})


def tipo_documento(req: OficioRespostaRequest) -> str:
    return (req.tipo_documento or "").strip() or get_settings().tipo_documento_padrao


def html_documento(
    tipo: str,
    req: OficioRespostaRequest,
    paragrafos: list[str],
    signatario: militares.Militar,
) -> str:
    # Ofício: modelo completo; Despacho/Parecer Técnico: só <p> (modelo próprio no SEI)
    if tipo == "Ofício":
        return modelos.oficio_html(req.assunto, req.referencia, req.destinatario, paragrafos, signatario)
    return modelos.paragrafos_html(paragrafos)


def texto_despacho(req: OficioRespostaRequest, destinatario: militares.Militar, nome_oficio: str) -> str:
    if req.despacho_texto.strip():
        # {oficio} no texto editado vira o nome do documento criado
        return req.despacho_texto.strip().replace("{oficio}", nome_oficio)
    s = get_settings()
    documentos = [d.replace("{oficio}", nome_oficio) for d in req.despacho_documentos if d.strip()]
    if not documentos:
        return ""
    texto = modelos.despacho(
        destinatario, documentos, req.assunto, req.despacho_complemento, s.despacho_assinatura
    )
    if len(texto) > s.despacho_max_caracteres and req.despacho_complemento:
        # sem o complemento, o texto costuma caber no limite do marcador
        texto = modelos.despacho(destinatario, documentos, req.assunto, "", s.despacho_assinatura)
    return texto


async def executar(req: OficioRespostaRequest, emitir: Emitir) -> None:
    s = get_settings()
    gravar = not req.simular
    tipo = tipo_documento(req)
    signatario = militares.obter(req.signatario_cpf)
    destinatario = militares.obter(req.atribuir_cpf)
    resultado: dict = {"processo": req.processo, "simulacao": req.simular, "tipo_documento": tipo}

    # falha antes de gravar qualquer coisa se o despacho não couber no marcador
    estimado = texto_despacho(req, destinatario, NOME_OFICIO_ESTIMADO)
    if req.adicionar_marcador and not estimado:
        raise ValueError("Informe a mensagem do despacho ou ao menos um documento para citar nele")
    if req.adicionar_marcador and len(estimado) > s.despacho_max_caracteres:
        raise ValueError(
            f"Despacho com ~{len(estimado)} caracteres (limite {s.despacho_max_caracteres}). "
            "Encurte o assunto ou edite o texto do despacho."
        )

    # cache da análise (TTL); expirado/ausente = relê o processo como hoje
    docs_cache = None
    if (req.id_analise or "").strip():
        entrada = cache_analise.obter(req.id_analise.strip())
        if entrada is not None:
            docs_cache = entrada.documentos

    async with browser_manager.context() as ctx:
        page = await ctx.new_page()
        try:
            # simulação com cache: dispensa login/abertura; gravação ou falta de cache: SEI como hoje
            if docs_cache is not None and req.simular:
                status(emitir, "login", "Cache da análise válido: login no SEI dispensado", 3, "success")
                status(emitir, "processo", "Cache da análise válido: abertura do processo dispensada", 8, "success")
                proc = None
            else:
                status(emitir, "login", "Acessando o SEI...", 3)
                await LoginPage(page).login()

                status(emitir, "processo", f"Abrindo o processo {req.processo}...", 8)
                proc = ProcessoPage(page)
                await proc.abrir_processo(req.processo)

            if docs_cache is not None:
                documentos = docs_cache
                resultado["documentos"] = list(documentos)
                status(emitir, "leitura", f"{len(documentos)} documento(s) reutilizados do cache da análise", 40, "success")
            else:
                def ao_ler(nome: str, posicao: int, total: int) -> None:
                    status(emitir, "leitura", f"Lendo documento {posicao}/{total}: {nome}", 10 + 30 * posicao // total)

                status(emitir, "leitura", "Lendo os documentos do processo...", 10)
                documentos = await proc.ler_documentos(ao_ler)
                resultado["documentos"] = list(documentos)
                status(emitir, "leitura", f"{len(documentos)} documento(s) lido(s)", 40, "success")

            # destinatário vazio: tenta montar pela autoridade no documento + posto do signatário
            if not req.destinatario.strip():
                trecho = militares.conteudo_documento_respondido(documentos, req.referencia)
                aut = autoridades.buscar_autoridade_no_texto(trecho[-800:] if trecho else "")
                montado = autoridades.montar_destinatario(aut, signatario.posto or None)
                if montado:
                    req = req.model_copy(update={"destinatario": montado})

            status(emitir, "ia", f"Redigindo a resposta com a IA ({s.openai_model})...", 45)
            if req.opcao_escolhida is not None:
                paragrafos = await ia.gerar_paragrafos_da_opcao(
                    documentos,
                    req.opcao_escolhida.model_dump(),
                    tipo_documento=tipo,
                    referencia=req.referencia,
                    assunto=req.assunto,
                    destinatario=req.destinatario,
                    informacoes_adicionais=req.informacoes_adicionais,
                )
            else:
                # chamada direta atual (inalterada)
                prompt = ia.montar_prompt(documentos, req.referencia, req.assunto, req.destinatario, req.complementar)
                paragrafos = await ia.gerar_paragrafos(prompt)
            if not s.openai_api_key:
                status(emitir, "ia", "OPENAI_API_KEY não configurada: texto simulado", 58, "warning")
            status(emitir, "ia", f"IA devolveu {len(paragrafos)} parágrafo(s)", 60, "success")

            html = html_documento(tipo, req, paragrafos, signatario)
            resultado.update(paragrafos=paragrafos, oficio_html=html)

            nome_oficio = f"{tipo} nº (a gerar)" if tipo != "Ofício" else NOME_OFICIO_PREVIA
            if gravar and req.criar_oficio:
                status(emitir, "oficio", f"Criando o {tipo} no processo...", 65)
                nome_oficio = await proc.incluir_documento(tipo, html) or tipo
                status(emitir, "oficio", f"{nome_oficio} criado e salvo", 80, "success")
            resultado["oficio"] = nome_oficio

            despacho = texto_despacho(req, destinatario, nome_oficio)
            resultado["despacho"] = despacho
            if len(despacho) > s.despacho_max_caracteres:
                despacho = despacho[: s.despacho_max_caracteres]
                resultado["despacho"] = despacho
                status(emitir, "despacho", "Despacho cortado no limite de caracteres", 82, "warning")

            if gravar and req.adicionar_marcador:
                status(emitir, "despacho", f"Adicionando marcador '{req.etiqueta}' com o despacho...", 85)
                await proc.adicionar_marcador(req.etiqueta, despacho)
                status(emitir, "despacho", "Despacho registrado no marcador", 90, "success")

            if gravar and req.atribuir:
                status(emitir, "atribuicao", f"Atribuindo o processo a {destinatario.nome_guerra}...", 93)
                resultado["atribuido_a"] = await proc.atribuir(destinatario.cpf, destinatario.nome)
                status(emitir, "atribuicao", f"Processo atribuído a {resultado['atribuido_a']}", 98, "success")

            fim = "Simulação concluída: nada foi gravado no SEI" if req.simular else f"{tipo} de resposta concluído!"
            status(emitir, "fim", fim, 100, "success")
            emitir({"tipo": "resultado", "dados": resultado})
        finally:
            await page.close()
