from playwright.async_api import Page, Frame


class BasePage:
    """
    Base para os Page Objects. Concentra os helpers que você repetiria
    em toda automação: clique com auto-wait, preenchimento, e o
    tratamento de iframe — que o SEI usa MUITO (a árvore, o conteúdo
    do processo e a barra de ações vivem em frames diferentes).
    """

    def __init__(self, page: Page) -> None:
        self.page = page

    async def goto(self, url: str) -> None:
        await self.page.goto(url, wait_until="domcontentloaded")

    async def click(self, selector: str) -> None:
        # locator já faz auto-wait: espera visível, estável e habilitado
        await self.page.locator(selector).click()

    async def fill(self, selector: str, value: str) -> None:
        await self.page.locator(selector).fill(value)

    async def text(self, selector: str) -> str:
        return (await self.page.locator(selector).inner_text()).strip()

    def frame_by_name(self, name: str) -> Frame:
        frame = self.page.frame(name=name)
        if frame is None:
            raise RuntimeError(f"Frame '{name}' não encontrado")
        return frame
