"""Testes da sugestão de signatário por função [7]."""
from app.militares import Militar, sugerir_signatario_cpf


def _mil(cpf, funcao, nome="N"):
    return Militar(
        cpf=cpf,
        nome=nome,
        nome_guerra="G",
        tratamento="",
        despedida="Att,",
        encaminhamento="Encaminho",
        graduacao="Maj BM",
        funcao=funcao,
        posto="Major",
    )


def test_um_match(monkeypatch):
    lista = [
        _mil("11111111111", "Chefe da SDTS-3"),
        _mil("22222222222", "Chefe do NTS"),
    ]
    monkeypatch.setattr("app.militares.listar", lambda: lista)
    doc = "Documento ... Chefe da SDTS-3 ... fim."
    assert sugerir_signatario_cpf(doc) == "11111111111"


def test_zero_match(monkeypatch):
    lista = [_mil("11111111111", "Chefe da SDTS-3")]
    monkeypatch.setattr("app.militares.listar", lambda: lista)
    assert sugerir_signatario_cpf("Nada relacionado aqui") is None


def test_varios_sem_sugestao(monkeypatch):
    lista = [
        _mil("11111111111", "Chefe da SDTS-3"),
        _mil("22222222222", "Chefe do NTS"),
    ]
    monkeypatch.setattr("app.militares.listar", lambda: lista)
    doc = "Assinam Chefe da SDTS-3 e também Chefe do NTS neste expediente."
    assert sugerir_signatario_cpf(doc) is None


def test_varios_prefere_mais_longo(monkeypatch):
    lista = [
        _mil("11111111111", "Chefe"),
        _mil("22222222222", "Chefe da SDTS-3"),
    ]
    monkeypatch.setattr("app.militares.listar", lambda: lista)
    doc = "Encaminhado ao Chefe da SDTS-3 para providências."
    assert sugerir_signatario_cpf(doc) == "22222222222"


def test_funcao_vazia_ignorada(monkeypatch):
    lista = [
        _mil("11111111111", ""),
        _mil("22222222222", "   "),
        _mil("33333333333", "Diretora de Logística e Finanças"),
    ]
    monkeypatch.setattr("app.militares.listar", lambda: lista)
    doc = "Diretora de Logística e Finanças"
    assert sugerir_signatario_cpf(doc) == "33333333333"


def test_acento_e_caixa(monkeypatch):
    lista = [_mil("11111111111", "Diretora de Logística e Finanças")]
    monkeypatch.setattr("app.militares.listar", lambda: lista)
    doc = "DIRETORA DE LOGISTICA E FINANCAS"
    assert sugerir_signatario_cpf(doc) == "11111111111"
