from .base_page import BasePage
from ..config import get_settings


class ProcessoPage(BasePage):
    """
    Exemplo de automação real: abrir um processo pelo número e ler
    dados. Mostra o padrão de iframes do SEI.
    """

    async def abrir_processo(self, numero: str) -> None:
        # a busca global fica no frame principal (fora dos iframes)
        await self.fill("#txtInfraPesquisar", numero)
        await self.page.keyboard.press("Enter")

    async def listar_documentos(self) -> list[str]:
        """
        A árvore do processo vive no iframe 'ifrArvore'.
        Retorna os títulos dos nós/documentos.
        """
        arvore = self.frame_by_name("ifrArvore")
        nos = arvore.locator("a.infraArvoreNo")
        await nos.first.wait_for(state="visible")
        return [
            (await nos.nth(i).inner_text()).strip()
            for i in range(await nos.count())
        ]
