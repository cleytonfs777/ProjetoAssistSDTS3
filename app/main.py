import asyncio
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from playwright.async_api import TimeoutError as PWTimeout

# Playwright spawns a subprocess; on Windows the default SelectorEventLoop
# (used by uvicorn --reload worker threads) does not support subprocess_exec.
# ProactorEventLoop is required.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from .browser import browser_manager
from .pages.login_page import LoginPage
from .pages.processo_page import ProcessoPage
from .schemas import ProcessoRequest, ProcessoResponse, HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # sobe o Chromium + pool de contextos UMA vez, no start da API
    await browser_manager.startup()
    yield
    await browser_manager.shutdown()


app = FastAPI(title="SEI Automation API", version="0.1.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/processos/consultar", response_model=ProcessoResponse)
async def consultar_processo(req: ProcessoRequest) -> ProcessoResponse:
    """
    Padrão de toda rota: empresta um contexto, abre uma page,
    executa os Page Objects, devolve o contexto ao pool.
    """
    async with browser_manager.context() as ctx:
        page = await ctx.new_page()
        try:
            login = LoginPage(page)
            if not await login.is_logged_in():
                await login.login()

            proc = ProcessoPage(page)
            await proc.abrir_processo(req.numero)
            docs = await proc.listar_documentos()

            return ProcessoResponse(numero=req.numero, documentos=docs)

        except PWTimeout as e:
            raise HTTPException(504, detail=f"Timeout na automação: {e}")
        except Exception as e:
            raise HTTPException(500, detail=f"Falha na automação: {e}")
        finally:
            await page.close()


