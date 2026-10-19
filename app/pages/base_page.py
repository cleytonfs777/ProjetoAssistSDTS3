from playwright.async_api import Page, Frame, FrameLocator


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

    def iframe(self, name: str) -> FrameLocator:
        # ao contrário de frame_by_name, espera o iframe existir (auto-wait)
        return self.page.locator(f'iframe[name="{name}"]').content_frame

    async def enviar_formulario(self, botao: str) -> None:
        """
        Clica no botão de salvar de um formulário do SEI e falha se o SEI recusar:
        o SEI avisa erros de validação com alert() e erros do servidor em #divInfraExcecao.
        """
        alertas: list[str] = []

        async def ao_alerta(dialog) -> None:
            alertas.append(dialog.message)
            await dialog.accept()

        self.page.on("dialog", ao_alerta)
        try:
            await self.page.locator(botao).first.click()
            await self.page.wait_for_load_state("load")
            await self.page.wait_for_timeout(500)
        finally:
            self.page.remove_listener("dialog", ao_alerta)

        excecao = self.page.locator("#divInfraExcecao")
        if await excecao.count() and await excecao.first.is_visible():
            alertas.append((await excecao.first.inner_text()).strip())
        if alertas:
            raise RuntimeError("SEI recusou a operação: " + " | ".join(alertas))

    def frame_by_name(self, name: str) -> Frame:
        frame = self.page.frame(name=name)
        if frame is None:
            raise RuntimeError(f"Frame '{name}' não encontrado")
        return frame
