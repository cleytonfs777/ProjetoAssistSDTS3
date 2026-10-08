import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.sei.mg.gov.br/sip/login.php?sigla_orgao_sistema=GOVMG&sigla_sistema=SEI&infra_url=L3NlaS8=")

    page.get_by_role("textbox", name="Usuário").fill("08761724602")

    page.get_by_role("textbox", name="Senha").fill("")

    page.locator("#selOrgao").select_option("21")
    page.get_by_role("button", name="ACESSAR").click()

    page.get_by_role("textbox", name="Pesquisar...").fill("48767202638")
    page.get_by_role("textbox", name="Pesquisar...").press("Enter")
    page.locator("iframe[name=\"ifrArvore\"]").content_frame.get_by_role("link", name="CBMMG Processo Recompensa").click()
    page.locator("iframe[name=\"ifrConteudoVisualizacao\"]").content_frame.locator("iframe[name=\"ifrVisualizacao\"]").content_frame.get_by_text("No dia 24 de junho de 2026,").click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)