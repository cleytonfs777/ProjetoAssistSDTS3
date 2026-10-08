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
        await self.goto(f"{s.sei_base_url}/")

        # ajuste os seletores conforme seu SEI:
        await self.fill("#txtUsuario", s.sei_usuario)
        await self.fill("#pwdSenha", s.sei_senha)
        if s.sei_orgao:
            await self.page.locator("#selOrgao").select_option(label=s.sei_orgao)
        await self.click("#sbmAcessar")

        # confirma que logou esperando um elemento da home
        await self.page.locator("#txtPesquisaRapida").wait_for(state="visible")

    async def is_logged_in(self) -> bool:
        return await self.page.locator("#txtPesquisaRapida").count() > 0


