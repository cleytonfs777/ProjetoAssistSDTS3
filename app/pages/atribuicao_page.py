import unicodedata

from .base_page import BasePage


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


class AtribuicaoPage(BasePage):
    """
    Tela "Atribuir Processo" (acao=procedimento_atribuicao_cadastrar).
    As opções de #selAtribuicao têm o texto "<CPF com 11 dígitos> - <Nome completo>".
    """

    async def atribuir(self, url: str, cpf: str, nome: str) -> str:
        """Atribui o processo e devolve o texto da opção escolhida."""
        print(f"[DEBUG][atribuicao] Abrindo {url[:90]}...", flush=True)
        await self.page.goto(url, wait_until="load")

        select = self.page.locator("#selAtribuicao")
        opcoes = await select.locator("option").evaluate_all(
            "els => els.map(o => ({valor: o.value, texto: o.textContent.trim()}))"
        )
        escolhida = next((o for o in opcoes if o["texto"].startswith(cpf)), None) or next(
            (o for o in opcoes if _normalizar(o["texto"]).endswith(_normalizar(nome))), None
        )
        if escolhida is None:
            raise RuntimeError(f"{nome} ({cpf}) não está na lista de atribuição desta unidade")

        await select.select_option(value=escolhida["valor"])
        print(f"[DEBUG][atribuicao] Atribuindo para {escolhida['texto']!r}", flush=True)
        await self.enviar_formulario("#sbmSalvar")
        return escolhida["texto"]
