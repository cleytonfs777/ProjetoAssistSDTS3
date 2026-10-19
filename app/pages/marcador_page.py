import re

from .base_page import BasePage


class MarcadorPage(BasePage):
    """
    Tela "Gerenciar Marcadores" do processo (acao=andamento_marcador_gerenciar).

    Sem marcadores, a URL já abre "Adicionar Marcador"; com marcadores, abre a lista
    e é preciso clicar em #btnAdicionar. O marcador é um combo "ddslick":
    #selMarcador .dd-select abre as opções (a.dd-option) e a escolha vai para #hdnIdMarcador.
    """

    async def adicionar(self, url: str, etiqueta: str, texto: str) -> None:
        print(f"[DEBUG][marcador] Abrindo {url[:90]}...", flush=True)
        await self.page.goto(url, wait_until="load")

        if not await self.page.locator("#selMarcador").count():
            print("[DEBUG][marcador] Processo já tem marcadores: clicando em Adicionar", flush=True)
            await self.page.locator("#btnAdicionar").click()
            await self.page.wait_for_load_state("load")

        await self.page.locator("#selMarcador .dd-select").click()
        opcao = self.page.locator("#selMarcador a.dd-option").filter(
            has_text=re.compile(rf"^\s*{re.escape(etiqueta)}\s*$")
        )
        try:
            await opcao.first.wait_for(state="visible", timeout=10_000)
        except Exception:
            raise RuntimeError(f"Marcador {etiqueta!r} não existe nesta unidade do SEI")
        await opcao.first.click()

        await self.page.locator("#txaTexto").fill(texto)
        print(f"[DEBUG][marcador] Salvando marcador {etiqueta!r}", flush=True)
        await self.enviar_formulario("#sbmSalvar")
