import asyncio
import html
import re
from typing import Callable
from urllib.parse import urljoin

from playwright.async_api import Frame, Page, TimeoutError as PWTimeout

from .atribuicao_page import AtribuicaoPage
from .base_page import BasePage
from .documento_page import DocumentoPage
from .marcador_page import MarcadorPage
from ..config import get_settings
from ..extratores import extrair_texto_anexo, tipo_anexo

# objArvore é o objeto JavaScript que o SEI usa para montar a árvore do processo
# (dentro do iframe ifrArvore). Cada nó traz o tipo, o rótulo e, em `src`,
# o endereço direto do conteúdo do documento.
JS_NOS_ARVORE = """() => (window.objArvore?.nodes || []).map(n => ({
    id: n.id || '',
    tipo: n.tipo || '',
    label: n.label || '',
    src: n.src || '',
    acoes: n.acoes || '',
}))"""


class ProcessoPage(BasePage):
    """
    Abre um processo pelo número e lê o conteúdo de cada documento.

    Em vez de clicar em cada nó da árvore, lê os nós de objArvore.nodes:
        tipo  = "PROCESSO" (raiz), "DOCUMENTO", pastas...
        label = nome exibido na árvore
        src   = controlador.php?acao=documento_visualizar...      -> documento HTML
                controlador.php?acao=documento_download_anexo...  -> anexo (PDF, imagem...)
    """

    async def abrir_processo(self, numero: str) -> None:
        # a busca global fica no frame principal (fora dos iframes)
        pesquisa = self.page.locator("#txtPesquisaRapida")
        arvore = self.page.locator('iframe[name="ifrArvore"]')
        # a home pode ainda estar inicializando e ignorar o primeiro Enter
        for tentativa in (1, 2):
            print(f"[DEBUG][processo] Pesquisando {numero!r} (tentativa {tentativa})", flush=True)
            await pesquisa.fill(numero)
            await pesquisa.press("Enter")
            try:
                await arvore.wait_for(state="attached", timeout=15_000)
                break
            except PWTimeout:
                if tentativa == 2:
                    raise
                await self.page.wait_for_load_state("load")
        print(f"[DEBUG][processo] Página do processo carregada | URL: {self.page.url}", flush=True)

    async def ler_documentos(
        self, ao_ler: Callable[[str, int, int], None] | None = None
    ) -> dict[str, str]:
        """
        Retorna {nome do documento: conteúdo em texto}.
        `ao_ler(nome, posição, total)` é chamado antes de cada documento (progresso).
        """
        arvore = await self._frame_arvore()
        nos = await arvore.evaluate(JS_NOS_ARVORE)
        print(f"[DEBUG][processo] {len(nos)} nó(s) na árvore", flush=True)
        legiveis = [n for n in nos if n["tipo"] == "DOCUMENTO" and n["src"]]

        documentos: dict[str, str] = {}
        # página auxiliar para abrir documentos HTML sem mexer na página do processo
        aux = await self.page.context.new_page()
        try:
            for posicao, no in enumerate(legiveis, 1):
                nome, src = no["label"].strip(), no["src"]
                print(f"[DEBUG][processo] Documento {nome!r}", flush=True)
                if ao_ler:
                    ao_ler(nome, posicao, len(legiveis))

                url = urljoin(arvore.url, src)
                if "documento_download_anexo" in src:
                    conteudo = await self._ler_anexo(url)
                else:
                    conteudo = await self._ler_html(aux, url)
                if conteudo is None:
                    continue

                chave = nome
                n = 2
                while chave in documentos:
                    chave = f"{nome} ({n})"
                    n += 1
                documentos[chave] = conteudo
                print(f"[DEBUG][processo]   -> {len(conteudo)} caractere(s) lidos", flush=True)
        finally:
            await aux.close()

        return documentos

    async def incluir_documento(self, tipo: str, conteudo_html: str) -> str | None:
        """
        Cria um documento do `tipo` no processo aberto, com `conteudo_html` no corpo.
        Retorna o nome do documento criado, como aparece na árvore (None se não identificado).
        """
        arvore = await self._frame_arvore()
        nos = await arvore.evaluate(JS_NOS_ARVORE)
        ids_antes = {n["id"] for n in nos}
        url = self._url_acao(arvore.url, nos, "documento_escolher_tipo", "Incluir Documento")

        aux = await self.page.context.new_page()
        try:
            await DocumentoPage(aux).gerar(url, tipo, conteudo_html)
        finally:
            await aux.close()

        # recarrega a tela do processo para a árvore mostrar o documento novo
        await self.page.reload(wait_until="domcontentloaded")
        arvore = await self._frame_arvore()
        novos = [n for n in await arvore.evaluate(JS_NOS_ARVORE) if n["id"] not in ids_antes]
        nome = novos[-1]["label"].strip() if novos else None
        print(f"[DEBUG][processo] Documento criado na árvore: {nome!r}", flush=True)
        return nome

    async def adicionar_marcador(self, etiqueta: str, texto: str) -> None:
        arvore = await self._frame_arvore()
        nos = await arvore.evaluate(JS_NOS_ARVORE)
        url = self._url_acao(arvore.url, nos, "andamento_marcador_gerenciar", "Gerenciar Marcadores")
        aux = await self.page.context.new_page()
        try:
            await MarcadorPage(aux).adicionar(url, etiqueta, texto)
        finally:
            await aux.close()

    async def atribuir(self, cpf: str, nome: str) -> str:
        arvore = await self._frame_arvore()
        nos = await arvore.evaluate(JS_NOS_ARVORE)
        url = self._url_acao(arvore.url, nos, "procedimento_atribuicao_cadastrar", "Atribuir Processo")
        aux = await self.page.context.new_page()
        try:
            return await AtribuicaoPage(aux).atribuir(url, cpf, nome)
        finally:
            await aux.close()

    @staticmethod
    def _url_acao(base: str, nos: list[dict], acao: str, descricao: str) -> str:
        # as ações do processo vêm prontas (com infra_hash) no HTML de ações do nó raiz
        acoes = next((n["acoes"] for n in nos if n["tipo"] == "PROCESSO"), "")
        achado = re.search(rf'href="([^"]*acao={acao}[^"]*)"', acoes)
        if not achado:
            raise RuntimeError(f"Ação '{descricao}' indisponível neste processo")
        return urljoin(base, html.unescape(achado.group(1)))

    async def _frame_arvore(self) -> Frame:
        iframe = await self.page.locator('iframe[name="ifrArvore"]').element_handle()
        arvore = await iframe.content_frame()
        if arvore is None:
            raise RuntimeError("Frame 'ifrArvore' sem conteúdo")
        # os nós só existem em objArvore depois que a árvore é desenhada
        await arvore.locator("a.infraArvoreNo").first.wait_for(state="attached")
        return arvore

    async def _ler_html(self, aux: Page, url: str) -> str:
        print("[DEBUG][processo]   -> documento HTML", flush=True)
        await aux.goto(url, wait_until="domcontentloaded")
        return (await aux.locator("body").inner_text()).strip()

    async def _ler_anexo(self, url: str) -> str | None:
        # context.request compartilha os cookies do navegador (sessão logada)
        resposta = await self.page.context.request.get(url)
        content_type = resposta.headers.get("content-type", "")
        print(f"[DEBUG][processo]   -> anexo {content_type!r} (HTTP {resposta.status})", flush=True)
        if not resposta.ok:
            return f"[falha ao baixar anexo: HTTP {resposta.status}]"

        conteudo = await resposta.body()
        if tipo_anexo(conteudo, content_type) == "imagem" and not get_settings().ler_imagens:
            print("[DEBUG][processo]   -> imagem ignorada (LER_IMAGENS=false)", flush=True)
            return None
        return await asyncio.to_thread(extrair_texto_anexo, conteudo, content_type)
