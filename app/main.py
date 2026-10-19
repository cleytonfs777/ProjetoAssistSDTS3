import asyncio
import json
import sys
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import TimeoutError as PWTimeout

# Playwright spawns a subprocess; on Windows the default SelectorEventLoop
# (used by uvicorn --reload worker threads) does not support subprocess_exec.
# ProactorEventLoop is required.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from . import autoridades, fluxo_analise, fluxo_oficio, ia, militares
from .browser import browser_manager
from .config import get_settings
from .pages.login_page import LoginPage
from .pages.processo_page import ProcessoPage
from .schemas import (
    AnaliseDemandaRequest,
    DocumentoGerado,
    HealthResponse,
    MilitarResponse,
    OficioRespostaRequest,
    ProcessoRequest,
    ProcessoResponse,
)

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # sobe o Chromium + pool de contextos UMA vez, no start da API
    await browser_manager.startup()
    yield
    await browser_manager.shutdown()


app = FastAPI(title="SEI Automation API", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
async def interface() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/configuracao")
async def configuracao() -> dict:
    """Parâmetros que a interface precisa (sem segredos)."""
    s = get_settings()
    return {
        "despacho_assinatura": s.despacho_assinatura,
        "despacho_max_caracteres": s.despacho_max_caracteres,
        "ia_configurada": bool(s.openai_api_key),
        "ia_modelo": s.openai_model,
    }


@app.get("/militares", response_model=list[MilitarResponse])
async def listar_militares() -> list[MilitarResponse]:
    return [MilitarResponse(**m.to_dict()) for m in militares.listar()]


@app.get("/etiquetas", response_model=list[str])
async def listar_etiquetas() -> list[str]:
    return json.loads(Path(get_settings().etiquetas_path).read_text(encoding="utf-8"))


@app.get("/destinatario")
async def recalcular_destinatario(autoridade: str = "", signatario_cpf: str = "") -> dict:
    """Recalcula o vocativo ao trocar o signatário (sem IA e sem SEI)."""
    aut = autoridades.buscar_autoridade(autoridade) if autoridade.strip() else None
    posto = None
    if signatario_cpf.strip():
        try:
            posto = militares.obter(signatario_cpf).posto or None
        except ValueError:
            posto = None
    return {"destinatario": autoridades.montar_destinatario(aut, posto)}


def _ndjson(rodar) -> StreamingResponse:
    """Mesmo envelope NDJSON do fluxo de ofício: eventos de progresso + resultado final."""
    fila: asyncio.Queue[dict | None] = asyncio.Queue()

    async def _tarefa() -> None:
        try:
            await rodar(fila.put_nowait)
        except PWTimeout as e:
            fila.put_nowait({"tipo": "error", "mensagem": f"Tempo esgotado no SEI: {e}".splitlines()[0]})
        except Exception as e:
            print(f"[DEBUG] ERRO {type(e).__name__}: {e}", flush=True)
            fila.put_nowait({"tipo": "error", "mensagem": str(e)})
        finally:
            fila.put_nowait(None)

    async def eventos():
        tarefa = asyncio.create_task(_tarefa())
        try:
            while (evento := await fila.get()) is not None:
                yield json.dumps(evento, ensure_ascii=False) + "\n"
        finally:
            if not tarefa.done():
                tarefa.cancel()

    return StreamingResponse(eventos(), media_type="application/x-ndjson")


@app.post("/oficios/analisar")
async def analisar_demanda(req: AnaliseDemandaRequest) -> StreamingResponse:
    """
    Etapa prévia opcional: lê o processo e sugere assunto, destinatário e 3 opções.
    NDJSON como /oficios/responder. NÃO grava nada no SEI.
    """
    print(f"[DEBUG] Análise de demanda: processo={req.processo!r}", flush=True)

    async def rodar(emitir) -> None:
        await fluxo_analise.executar(req, emitir)

    return _ndjson(rodar)


@app.post("/oficios/responder")
async def responder_oficio(req: OficioRespostaRequest) -> StreamingResponse:
    """
    Fluxo completo (ver app/fluxo_oficio.py). Responde em NDJSON: uma linha JSON por evento,
    {"tipo": "info|success|warning|error", "mensagem", "progresso"} e, ao final,
    {"tipo": "resultado", "dados": {...}}.
    """
    print(f"[DEBUG] Ofício de resposta: processo={req.processo!r} simular={req.simular}", flush=True)

    async def rodar(emitir) -> None:
        await fluxo_oficio.executar(req, emitir)

    return _ndjson(rodar)


@app.post("/processos/consultar", response_model=ProcessoResponse)
async def consultar_processo(req: ProcessoRequest) -> ProcessoResponse:
    """
    Padrão de toda rota: empresta um contexto, abre uma page,
    executa os Page Objects, devolve o contexto ao pool.
    """
    print(f"[DEBUG] Requisição recebida: numero={req.numero!r}", flush=True)
    async with browser_manager.context() as ctx:
        print("[DEBUG] Contexto emprestado do pool", flush=True)
        page = await ctx.new_page()
        print("[DEBUG] Nova página aberta", flush=True)
        try:
            login = LoginPage(page)
            logado = await login.is_logged_in()
            print(f"[DEBUG] Já está logado? {logado} | URL atual: {page.url}", flush=True)
            if not logado:
                print("[DEBUG] Iniciando login...", flush=True)
                await login.login()
                print(f"[DEBUG] Login concluído | URL atual: {page.url}", flush=True)

            proc = ProcessoPage(page)
            print(f"[DEBUG] Abrindo processo {req.numero}...", flush=True)
            await proc.abrir_processo(req.numero)
            print(f"[DEBUG] Processo aberto | URL atual: {page.url}", flush=True)

            print("[DEBUG] Lendo documentos...", flush=True)
            docs = await proc.ler_documentos()
            print(f"[DEBUG] {len(docs)} documento(s) lido(s): {list(docs)}", flush=True)

            gerado = None
            s = get_settings()
            if s.criar_documento:
                tipo = req.tipo_documento or s.tipo_documento_padrao
                paragrafos = await ia.gerar_paragrafos(ia.montar_prompt(docs))
                print(f"[DEBUG] Criando documento {tipo!r} com o texto da IA", flush=True)
                corpo = "".join(f"<p>{escape(p)}</p>" for p in paragrafos)
                nome = await proc.incluir_documento(tipo, corpo)
                gerado = DocumentoGerado(tipo=tipo, nome=nome, conteudo="\n".join(paragrafos))

            return ProcessoResponse(numero=req.numero, documentos=docs, documento_gerado=gerado)

        except PWTimeout as e:
            print(f"[DEBUG] TIMEOUT | URL atual: {page.url}\n{e}", flush=True)
            raise HTTPException(504, detail=f"Timeout na automação: {e}")
        except Exception as e:
            print(f"[DEBUG] ERRO {type(e).__name__} | URL atual: {page.url}\n{e}", flush=True)
            raise HTTPException(500, detail=f"Falha na automação: {e}")
        finally:
            await page.close()
            print("[DEBUG] Página fechada, contexto devolvido ao pool", flush=True)
