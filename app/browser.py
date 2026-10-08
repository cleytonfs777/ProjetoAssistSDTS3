"""
Gerencia um único Browser Playwright (caro de subir) e um pool de
BrowserContexts (baratos, isolados). Cada request pega um contexto
emprestado, usa e devolve. Assim você não sobe/derruba Chromium a
cada chamada de API — que é o que mata a performance.
"""
import asyncio
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

from .config import get_settings


class BrowserManager:
    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._pool: asyncio.Queue[BrowserContext] | None = None

    async def startup(self) -> None:
        s = get_settings()
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=s.headless)
        self._pool = asyncio.Queue(maxsize=s.pool_size)
        for _ in range(s.pool_size):
            ctx = await self._browser.new_context(
                accept_downloads=True,
                viewport={"width": 1366, "height": 768},
            )
            ctx.set_default_timeout(s.nav_timeout_ms)
            await self._pool.put(ctx)

    async def shutdown(self) -> None:
        if self._pool:
            while not self._pool.empty():
                ctx = await self._pool.get()
                await ctx.close()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    @asynccontextmanager
    async def context(self):
        """Empresta um BrowserContext do pool e o devolve ao final."""
        assert self._pool is not None, "BrowserManager não inicializado"
        ctx = await self._pool.get()
        try:
            yield ctx
        finally:
            await self._pool.put(ctx)


browser_manager = BrowserManager()
