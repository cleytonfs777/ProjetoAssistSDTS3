from .base_page import BasePage
from ..config import get_settings


class LoginPage(BasePage):
    """
    SELETORES DE EXEMPLO. Ajuste rodando:
        playwright codegen https://seu-sei.gov.br/sei
    e copiando os locators que ele gerar. Prefira get_by_label /
    get_by_role aos XPaths.
    """

    async def login(self) -> None:
        s = get_settings()
        print(f"[DEBUG][login] Acessando {s.sei_base_url}/", flush=True)
        await self.goto(f"{s.sei_base_url}/")
        print(f"[DEBUG][login] Página carregada | URL: {self.page.url} | título: {await self.page.title()!r}", flush=True)

        # o contexto do pool guarda os cookies: se a sessão ainda vale, o SEI abre direto na home
        tela = self.page.locator("#txtUsuario, #txtPesquisaRapida").first
        await tela.wait_for(state="visible")
        if await self.page.locator("#txtPesquisaRapida").is_visible():
            print("[DEBUG][login] Sessão ainda ativa: login dispensado", flush=True)
            return

        # ajuste os seletores conforme seu SEI:
        print(f"[DEBUG][login] Preenchendo usuário ({s.sei_usuario!r})", flush=True)
        await self.fill("#txtUsuario", s.sei_usuario)
        print("[DEBUG][login] Preenchendo senha", flush=True)
        await self.fill("#pwdSenha", s.sei_senha)
        if s.sei_orgao:
            print(f"[DEBUG][login] Selecionando órgão {s.sei_orgao!r}", flush=True)
            await self.page.locator("#selOrgao").select_option(label=s.sei_orgao)
        print("[DEBUG][login] Clicando em Acessar", flush=True)
        await self.click("#sbmAcessar")

        # confirma que logou esperando um elemento da home
        print("[DEBUG][login] Aguardando #txtPesquisaRapida aparecer", flush=True)
        await self.page.locator("#txtPesquisaRapida").wait_for(state="visible")
        print(f"[DEBUG][login] Home carregada | URL: {self.page.url}", flush=True)

    async def is_logged_in(self) -> bool:
        return await self.page.locator("#txtPesquisaRapida").count() > 0


