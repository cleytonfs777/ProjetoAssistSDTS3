"""
Redação do ofício de resposta pela OpenAI (mesmo prompt do robo_sei/ai_converter.py).

A IA recebe o conteúdo de todos os documentos do processo + as informações do
formulário e devolve uma lista de parágrafos: ['<parágrafo>', '<parágrafo>', ...].
Sem OPENAI_API_KEY os parágrafos são simulados.
"""
import ast
import json

from openai import AsyncOpenAI, DefaultAsyncHttpxClient

from .config import get_settings

PROMPT_OFICIO = """
  Baseado no texto a seguir, crie um texto de ofício de resposta seguindo a seguinte estrutura: Deve ser retornado apenas um texto em formato de lista, conforme o exemplo: '[<resposta>, <resposta>, <resposta>]', Sendo que cada espaço representado como resposta será o respectivo paragrafo de resposta. A seguir um exemplo de oficio utilizado por mim: ['Em atenção ao Despacho de Vossa Senhoria referente ao Ofício nº 43/SEI (106782192), que trata da proposta de alteração do art. 13 da Resolução nº 837/19, com o objetivo de restringir o acesso ao Boletim Interno Reservado (BIR) exclusivamente às Unidades ou Setores com atribuição funcional específica, informo que, conforme levantamento técnico realizado junto à PRODEMGE, o sistema SIGP WEB possui viabilidade técnica para segmentação apenas por COB (Comando Operacional de Bombeiros), embora tal funcionalidade não esteja implementada.','Destaca-se que atualmente o acesso ao BIR já é condicionado à habilitação de um perfil específico de consulta, distinto daquele utilizado para o acesso ao Boletim Interno (BI). Assim, para que um militar possa consultar os BIRs, é necessário que esteja autorizado com o respectivo perfil de acesso. A eventual segmentação por COB, caso venha a ser desenvolvida, permitirá um filtro adicional com base na vinculação do militar ao Comando correspondente, aprimorando a salvaguarda das informações restritas neste nível de articulação.','Contudo, ressalte-se que a eventual retomada de publicações e consultas descentralizadas por COB exigiria a completa desestruturação do modelo atual, com a criação de BIRs individualizados. Tal medida implicaria significativo retrabalho e aumento da complexidade de manutenção, contrariando o esforço institucional empreendido pela Ajudância-Geral na consolidação de um boletim unificado para toda a Corporação.','Diante desse cenário, e considerando a relação entre custo, benefício e a finalidade do pleito, a Subdiretoria de Tecnologia e Sistemas manifesta-se no sentido de que a modificação de sistema proposta não seja implementada. Isso porque o controle de acesso por meio de perfil específico de consulta, aliado à designação criteriosa dos operadores de BIR pelos respectivos comandantes, já poderia constituir barreira adequada à salvaguarda de informações sigilosas.','Ademais, o atual modelo não inviabiliza o acesso eventual a conteúdos de outras unidades, especialmente quando houver demanda funcional legítima, como nas atividades de inteligência. Assim, submete-se à apreciação do EMBM a real necessidade de adoção da segmentação por COB como diretriz futura para proteção do conteúdo restrito dos BIRs no SIGP WEB, considerando-se os limites técnicos e operacionais atualmente existentes. Enfatiza-se, por oportuno, que não há viabilidade técnica, no momento, para segmentações mais granulares em nível de unidade ou seção.','Permanecemos à disposição para quaisquer esclarecimentos adicionais que se fizerem necessários.']. Não se esqueça de retornar apenas a lista em texto, pois irei convertê-la para uma lista de python posteriormente. Segue o texto a ser analisado para a produção do oficio:
  """


def montar_prompt(
    documentos: dict[str, str],
    referencia: str = "",
    assunto: str = "",
    destinatario: str = "",
    complementar: str = "",
) -> str:
    conteudo = _conteudo_processo(documentos, referencia, get_settings().ia_max_caracteres)
    extras = [
        f"Documento a ser respondido: {referencia}" if referencia else "",
        f"Assunto do ofício de resposta: {assunto}" if assunto else "",
        f"Destinatário do ofício de resposta: {destinatario}" if destinatario else "",
        f"Instruções complementares: {complementar}" if complementar else "",
    ]
    extras = "\n".join(e for e in extras if e)
    return PROMPT_OFICIO + conteudo + (f"\n\nInformações complementares:\n{extras}" if extras else "")


async def gerar_paragrafos(prompt: str) -> list[str]:
    s = get_settings()
    if not s.openai_api_key:
        print("[DEBUG][ia] OPENAI_API_KEY vazia: usando parágrafos simulados", flush=True)
        return _paragrafos_simulados()

    print(f"[DEBUG][ia] Enviando {len(prompt)} caractere(s) ao modelo {s.openai_model}", flush=True)
    cliente = AsyncOpenAI(
        api_key=s.openai_api_key,
        timeout=s.openai_timeout_s,
        http_client=DefaultAsyncHttpxClient(proxy=s.openai_proxy) if s.openai_proxy else None,
    )
    async with cliente:
        resposta = await cliente.chat.completions.create(
            model=s.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=s.openai_max_tokens,
            temperature=s.openai_temperature,
        )
    texto = resposta.choices[0].message.content or ""
    paragrafos = converter_lista(texto)
    print(f"[DEBUG][ia] {len(paragrafos)} parágrafo(s) recebido(s)", flush=True)
    if not paragrafos:
        raise RuntimeError("A IA não retornou parágrafos")
    return paragrafos


def converter_lista(texto: str) -> list[str]:
    """Converte "['p1', 'p2']" (resposta da IA) em lista, sem executar código."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`").removeprefix("python").removeprefix("json").strip()
    for converter in (ast.literal_eval, json.loads):
        try:
            valor = converter(texto)
        except (ValueError, SyntaxError, json.JSONDecodeError):
            continue
        if isinstance(valor, (list, tuple)):
            return [str(p).strip() for p in valor if str(p).strip()]
    # último recurso: separa os itens manualmente
    if texto.startswith("[") and texto.endswith("]"):
        texto = texto[1:-1]
    itens = texto.split("',") if "'," in texto else texto.split("\n")
    return [i.strip().strip("'\"").strip() for i in itens if i.strip().strip("'\"").strip()]


def _conteudo_processo(documentos: dict[str, str], referencia: str, limite: int) -> str:
    """Texto dos documentos; acima do limite, prioriza o de referência e os mais recentes."""
    blocos = [f"### {nome}\n{texto}" for nome, texto in documentos.items()]
    if sum(len(b) for b in blocos) <= limite:
        return "\n\n".join(blocos)

    ref = referencia.strip().lower()
    escolhidos: set[int] = set()
    usado = 0
    ordem = [i for i, nome in enumerate(documentos) if ref and ref in nome.lower()]
    ordem += [i for i in reversed(range(len(blocos))) if i not in ordem]
    for i in ordem:
        if usado + len(blocos[i]) > limite:
            continue
        escolhidos.add(i)
        usado += len(blocos[i])
    print(f"[DEBUG][ia] Conteúdo reduzido a {len(escolhidos)}/{len(blocos)} documento(s)", flush=True)
    return "\n\n".join(blocos[i] for i in sorted(escolhidos))


def _paragrafos_simulados() -> list[str]:
    return [
        "Em atenção ao documento em referência, informo que a demanda foi analisada por esta Seção.",
        "Texto gerado por simulação: configure OPENAI_API_KEY no .env para obter a redação da IA.",
        "Permanecemos à disposição para quaisquer esclarecimentos adicionais que se fizerem necessários.",
    ]


# ---------- análise prévia da demanda (etapa opcional; não altera montar_prompt/gerar_paragrafos) ----------

PROMPT_ANALISE = """
Você analisa um processo administrativo do SEI para apoiar a redação de uma resposta.

O conteúdo está dividido em duas seções:
1) DOCUMENTO A SER RESPONDIDO — alvo principal da demanda; a resposta deve atendê-lo.
2) DOCUMENTOS DE CONTEXTO DO PROCESSO — apenas apoio; não são o pedido principal.

Com base nisso, retorne APENAS um JSON (sem markdown) no formato:
{
  "assunto": "assunto conciso do ofício/documento de resposta, baseado principalmente no documento respondido",
  "signatario_documento_respondido": "nome completo de quem assina o documento respondido (se não constar, string vazia)",
  "opcoes": [
    {"id": 1, "titulo": "...", "resumo": "..."},
    {"id": 2, "titulo": "...", "resumo": "..."},
    {"id": 3, "titulo": "...", "resumo": "..."}
  ]
}

As 3 opções devem ser abordagens REALMENTE distintas de atender a demanda (caminhos decisórios/técnicos diferentes), não meras variações de redação do mesmo conteúdo.
"""


def _separar_por_referencia(
    documentos: dict[str, str], referencia: str
) -> tuple[dict[str, str], dict[str, str]]:
    ref = referencia.strip().lower()
    alvo: dict[str, str] = {}
    contexto: dict[str, str] = {}
    for nome, texto in documentos.items():
        if ref and ref in nome.lower():
            alvo[nome] = texto
        else:
            contexto[nome] = texto
    return alvo, contexto


def montar_prompt_analise(
    documentos: dict[str, str],
    referencia: str = "",
    complementar: str = "",
) -> str:
    """Prompt da análise prévia: documento respondido em destaque + contexto do processo."""
    limite = get_settings().ia_max_caracteres
    alvo, contexto = _separar_por_referencia(documentos, referencia)
    # mesma priorização de _conteudo_processo: referência primeiro, depois os mais recentes
    secao_alvo = _conteudo_processo(alvo, referencia, limite) if alvo else "(nenhum documento correspondente à referência)"
    restante = max(0, limite - len(secao_alvo))
    secao_contexto = _conteudo_processo(contexto, "", restante) if contexto and restante else "(sem documentos de contexto no limite)"
    extras = []
    if referencia:
        extras.append(f"Referência informada: {referencia}")
    if complementar:
        extras.append(f"Instruções complementares: {complementar}")
    bloco_extras = ("\n\nInformações complementares:\n" + "\n".join(extras)) if extras else ""
    return (
        PROMPT_ANALISE
        + "\n\n### DOCUMENTO A SER RESPONDIDO\n"
        + secao_alvo
        + "\n\n### DOCUMENTOS DE CONTEXTO DO PROCESSO\n"
        + secao_contexto
        + bloco_extras
    )


async def analisar_demanda(
    documentos: dict[str, str],
    referencia: str = "",
    complementar: str = "",
) -> dict:
    """
    Chama a IA e devolve dict validado:
    {assunto, signatario_documento_respondido, opcoes:[{id,titulo,resumo}, ...]}.
    Sem OPENAI_API_KEY: dados simulados. 1 retry se a validação Pydantic falhar.
    """
    from .schemas import AnaliseIAResponse

    s = get_settings()
    if not s.openai_api_key:
        print("[DEBUG][ia] OPENAI_API_KEY vazia: usando análise simulada", flush=True)
        return _analise_simulada().model_dump()

    prompt = montar_prompt_analise(documentos, referencia, complementar)
    print(f"[DEBUG][ia] Análise: enviando {len(prompt)} caractere(s) ao modelo {s.openai_model}", flush=True)
    cliente = AsyncOpenAI(
        api_key=s.openai_api_key,
        timeout=s.openai_timeout_s,
        http_client=DefaultAsyncHttpxClient(proxy=s.openai_proxy) if s.openai_proxy else None,
    )
    ultimo_erro: Exception | None = None
    async with cliente:
        for tentativa in range(2):
            try:
                resposta = await cliente.chat.completions.create(
                    model=s.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=s.openai_max_tokens,
                    temperature=s.openai_temperature,
                    response_format={"type": "json_object"},
                )
                texto = (resposta.choices[0].message.content or "").strip()
                if texto.startswith("```"):
                    texto = texto.strip("`").removeprefix("json").strip()
                dados = AnaliseIAResponse.model_validate(json.loads(texto))
                print(f"[DEBUG][ia] Análise ok ({len(dados.opcoes)} opções)", flush=True)
                return dados.model_dump()
            except Exception as e:
                ultimo_erro = e
                print(f"[DEBUG][ia] Análise tentativa {tentativa + 1} falhou: {type(e).__name__}", flush=True)
    raise RuntimeError(f"A IA não retornou uma análise válida: {ultimo_erro}")


def _analise_simulada():
    from .schemas import AnaliseIAResponse, OpcaoAnalise

    return AnaliseIAResponse(
        assunto="Resposta quanto a esclarecimentos adicionais (simulado)",
        signatario_documento_respondido="Nome Simulado do Signatário",
        opcoes=[
            OpcaoAnalise(
                id=1,
                titulo="Deferimento integral",
                resumo="Atender plenamente o pedido do documento respondido, fundamentando a viabilidade.",
            ),
            OpcaoAnalise(
                id=2,
                titulo="Deferimento parcial com condicionantes",
                resumo="Aceitar parte da demanda e indicar limites técnicos ou prazos para o restante.",
            ),
            OpcaoAnalise(
                id=3,
                titulo="Indeferimento motivado",
                resumo="Negar o pleito com base em restrições normativas ou operacionais, oferecendo alternativas.",
            ),
        ],
    )


# ---------- redação a partir da opção escolhida (etapa 2; não altera montar_prompt/gerar_paragrafos) ----------

_ORIENTACOES_TIPO = {
    "Ofício": (
        "Redija um OFÍCIO formal em parágrafos: tom protocolar, referência ao documento respondido, "
        "fundamentação e fecho adequado (sem incluir 'Respeitosamente,' nem o signatário — o modelo HTML cuida disso)."
    ),
    "Despacho": (
        "Redija um DESPACHO em parágrafos objetivos: decisão/encaminhamento claro, fundamentação breve, "
        "sem cabeçalho de ofício nem 'Respeitosamente,' (o SEI já traz o modelo do Despacho)."
    ),
    "Parecer Técnico": (
        "Redija um PARECER TÉCNICO em parágrafos: análise técnica, conclusão fundamentada e eventual "
        "recomendação, sem cabeçalho de ofício nem 'Respeitosamente,' (o SEI já traz o modelo)."
    ),
}


def montar_prompt_da_opcao(
    documentos: dict[str, str],
    opcao: dict,
    *,
    tipo_documento: str = "Ofício",
    referencia: str = "",
    assunto: str = "",
    destinatario: str = "",
    informacoes_adicionais: str = "",
) -> str:
    """Prompt que obriga a redação a seguir exatamente a opção escolhida na análise."""
    limite = get_settings().ia_max_caracteres
    alvo, contexto = _separar_por_referencia(documentos, referencia)
    secao_alvo = (
        _conteudo_processo(alvo, referencia, limite) if alvo else "(nenhum documento correspondente à referência)"
    )
    restante = max(0, limite - len(secao_alvo))
    secao_contexto = (
        _conteudo_processo(contexto, "", restante) if contexto and restante else "(sem documentos de contexto no limite)"
    )
    orientacao = _ORIENTACOES_TIPO.get(tipo_documento, _ORIENTACOES_TIPO["Ofício"])
    extras = [
        f"Tipo de documento a redigir: {tipo_documento}",
        f"Documento a ser respondido: {referencia}" if referencia else "",
        f"Assunto: {assunto}" if assunto else "",
        f"Destinatário (vocativo): {destinatario}" if destinatario else "",
        f"Opção escolhida (id={opcao.get('id')}): {opcao.get('titulo', '')}",
        f"Resumo da opção (seguir EXATAMENTE esta abordagem): {opcao.get('resumo', '')}",
        f"Informações adicionais / ajustes do usuário: {informacoes_adicionais}" if informacoes_adicionais else "",
    ]
    extras = "\n".join(e for e in extras if e)
    return (
        "Com base no conteúdo abaixo, redija a resposta seguindo EXATAMENTE a opção escolhida "
        "(abordagem decisória/técnica indicada), incorporando as informações adicionais quando houver. "
        "O DOCUMENTO A SER RESPONDIDO é o alvo; os DOCUMENTOS DE CONTEXTO são apenas apoio.\n"
        f"{orientacao}\n"
        "Deve ser retornado apenas um texto em formato de lista Python, conforme o exemplo: "
        "'[<parágrafo>, <parágrafo>, <parágrafo>]'. Não use markdown. "
        "Retorne apenas a lista em texto.\n\n"
        f"### DOCUMENTO A SER RESPONDIDO\n{secao_alvo}\n\n"
        f"### DOCUMENTOS DE CONTEXTO DO PROCESSO\n{secao_contexto}\n\n"
        f"Informações da redação:\n{extras}"
    )


async def gerar_paragrafos_da_opcao(
    documentos: dict[str, str],
    opcao: dict,
    *,
    tipo_documento: str = "Ofício",
    referencia: str = "",
    assunto: str = "",
    destinatario: str = "",
    informacoes_adicionais: str = "",
) -> list[str]:
    """Gera parágrafos alinhados à opção; reutiliza gerar_paragrafos (parser e simulação iguais)."""
    prompt = montar_prompt_da_opcao(
        documentos,
        opcao,
        tipo_documento=tipo_documento,
        referencia=referencia,
        assunto=assunto,
        destinatario=destinatario,
        informacoes_adicionais=informacoes_adicionais,
    )
    return await gerar_paragrafos(prompt)
