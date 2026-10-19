import re

from playwright.async_api import Page, TimeoutError as PWTimeout

from .base_page import BasePage

# Insere o HTML na seção editável do editor (CKEditor 4) usando a API do próprio
# editor, para ele marcar o documento como alterado. O Ofício tem várias seções;
# a editável mais alta é o corpo do texto. Retorna o nome da instância usada.
JS_INSERIR_CONTEUDO = """(html) => {
    if (!window.CKEDITOR) return null;
    const editaveis = Object.values(CKEDITOR.instances).filter(e => !e.readOnly);
    if (!editaveis.length) return null;
    const alvo = editaveis.reduce((a, b) =>
        b.container.$.offsetHeight > a.container.$.offsetHeight ? b : a);
    alvo.setData(html);
    return alvo.name;
}"""


class DocumentoPage(BasePage):
    """
    Cria um documento no SEI (equivalente ao gerador_documento do script Selenium).

    Deve receber uma página auxiliar: ela é navegada para a tela "Gerar Documento"
    (documento_escolher_tipo) e o editor abre numa janela nova (popup).
    """

    async def gerar(self, url_escolher_tipo: str, tipo: str, conteudo_html: str) -> None:
        print(f"[DEBUG][documento] Abrindo 'Gerar Documento' para o tipo {tipo!r}", flush=True)
        await self.goto(url_escolher_tipo)

        # a lista inicial mostra só os tipos mais usados; #ancExibirSeries mostra todos
        await self.click("#ancExibirSeries")
        opcao = self.page.locator("a.ancoraOpcao").filter(
            has_text=re.compile(rf"^\s*{re.escape(tipo)}\s*$")
        )
        try:
            await opcao.first.wait_for(state="visible", timeout=10_000)
        except PWTimeout:
            raise RuntimeError(f"Tipo de documento {tipo!r} não encontrado no SEI") from None

        # com a lista ainda sendo montada, o clique no tipo às vezes não abre o formulário
        publico = self.page.locator("#lblPublico")
        for tentativa in (1, 2):
            if not await publico.count():
                await opcao.first.click()
            try:
                await publico.wait_for(state="visible", timeout=10_000)
                break
            except PWTimeout:
                print(f"[DEBUG][documento] Formulário não abriu (tentativa {tentativa})", flush=True)
                if tentativa == 2:
                    raise RuntimeError("O formulário 'Gerar Documento' não abriu") from None

        print("[DEBUG][documento] Formulário: nível de acesso Público", flush=True)
        await publico.click()

        print("[DEBUG][documento] Salvando o formulário (cria o documento)", flush=True)
        async with self.page.context.expect_page() as popup:
            await self.page.locator("#btnSalvar").first.click()
        editor = await popup.value
        try:
            await self._preencher_editor(editor, conteudo_html)
        finally:
            await editor.close()

    async def _preencher_editor(self, editor: Page, conteudo_html: str) -> None:
        print("[DEBUG][documento] Aguardando o editor carregar", flush=True)
        await editor.wait_for_load_state("load")
        await editor.locator(".cke_contents iframe").first.wait_for()
        await editor.wait_for_function(
            "() => window.CKEDITOR && Object.values(CKEDITOR.instances).every(e => e.status === 'ready')"
        )

        instancia = await editor.evaluate(JS_INSERIR_CONTEUDO, conteudo_html)
        if instancia is None:
            raise RuntimeError("Nenhuma seção editável encontrada no editor do SEI")
        print(f"[DEBUG][documento] Conteúdo inserido na seção {instancia!r}", flush=True)

        await editor.locator("a.cke_button__save").first.click()
        await editor.wait_for_load_state("networkidle")
        print("[DEBUG][documento] Documento salvo", flush=True)
