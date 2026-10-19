"""Testes das funções puras de autoridades (sem SEI / OpenAI)."""
from app.autoridades import (
    buscar_autoridade,
    buscar_autoridade_no_texto,
    montar_destinatario,
    resolver_destinatario,
)

AUTORIDADES = [
    {
        "nome": "José da Silva",
        "destinatario": "Chefe de Seção",
        "sexo": "M",
        "PG": "Coronel",
    },
    {
        "nome": "Maria Souza",
        "destinatario": "Comandante do 2º BBM",
        "sexo": "F",
        "PG": "Tenente-Coronel",
    },
    {
        "nome": "Sem Metadados",
        "destinatario": "Só o vocativo antigo",
        "sexo": "",
        "PG": "",
    },
]


def _patch(monkeypatch):
    monkeypatch.setattr("app.autoridades.listar", lambda: AUTORIDADES)


# ---------- resolver_destinatario (retrocompat) ----------

def test_resolver_match_exato(monkeypatch):
    _patch(monkeypatch)
    assert resolver_destinatario("José da Silva") == "Chefe de Seção"


def test_resolver_acento_e_caixa(monkeypatch):
    _patch(monkeypatch)
    assert resolver_destinatario("JOSE DA SILVA") == "Chefe de Seção"
    assert resolver_destinatario("maria souza") == "Comandante do 2º BBM"


def test_resolver_sem_match(monkeypatch):
    _patch(monkeypatch)
    assert resolver_destinatario("Fulano Inexistente") is None
    assert resolver_destinatario("") is None


# ---------- buscar_autoridade ----------

def test_buscar_exato(monkeypatch):
    _patch(monkeypatch)
    aut = buscar_autoridade("José da Silva")
    assert aut["PG"] == "Coronel" and aut["sexo"] == "M"


def test_buscar_acento_caixa(monkeypatch):
    _patch(monkeypatch)
    assert buscar_autoridade("JOSE DA SILVA")["nome"] == "José da Silva"


def test_buscar_inclusao(monkeypatch):
    _patch(monkeypatch)
    assert buscar_autoridade("CEL BM JOSÉ DA SILVA")["nome"] == "José da Silva"


def test_buscar_sem_match(monkeypatch):
    _patch(monkeypatch)
    assert buscar_autoridade("Ninguém") is None


def test_buscar_fallback_trecho_final(monkeypatch):
    _patch(monkeypatch)
    trecho = "..." * 50 + " Assinado por MARIA SOUZA em Belo Horizonte."
    aut = buscar_autoridade_no_texto(trecho)
    assert aut is not None and aut["nome"] == "Maria Souza"


# ---------- montar_destinatario ----------

def test_montar_igual_senhor(monkeypatch):
    _patch(monkeypatch)
    aut = buscar_autoridade("José da Silva")
    assert montar_destinatario(aut, "Coronel") == "Senhor Coronel BM, Chefe de Seção"


def test_montar_superior_senhora(monkeypatch):
    _patch(monkeypatch)
    # autoridade Coronel (1) vs signatário Major (3) → autoridade superior → Senhora/Senhor
    aut = {"nome": "X", "destinatario": "Chefe", "sexo": "F", "PG": "Coronel"}
    assert montar_destinatario(aut, "Major") == "Senhora Coronel BM, Chefe"


def test_montar_inferior_ao(monkeypatch):
    # autoridade Tenente-Coronel M vs signatário Coronel → Ao
    aut = {"nome": "X", "destinatario": "Comandante do 2º BBM", "sexo": "M", "PG": "Tenente-Coronel"}
    assert montar_destinatario(aut, "Coronel") == "Ao Tenente-Coronel BM, Comandante do 2º BBM"


def test_montar_inferior_a(monkeypatch):
    aut = {"nome": "Y", "destinatario": "Comandante do 5º BBM", "sexo": "F", "PG": "Major"}
    assert montar_destinatario(aut, "Coronel") == "À Major BM, Comandante do 5º BBM"


def test_montar_pg_variacao(monkeypatch):
    aut = {"nome": "Z", "destinatario": "Cmdt", "sexo": "M", "PG": "Tenente Coronel"}
    # PG com espaço; posto do signatário com hífen e caixa
    assert montar_destinatario(aut, "CORONEL") == "Ao Tenente Coronel BM, Cmdt"


def test_montar_posto_desconhecido_sem_prefixo(monkeypatch):
    aut = {"nome": "Z", "destinatario": "Vocativo", "sexo": "M", "PG": "Patente Inventada"}
    assert montar_destinatario(aut, "Coronel") == "Vocativo"


def test_montar_sem_signatario(monkeypatch):
    aut = buscar_autoridade("José da Silva")
    assert montar_destinatario(aut, None) is None
    assert montar_destinatario(aut, "") is None
    assert montar_destinatario(None, "Coronel") is None


def test_montar_sem_pg_sexo_usa_destinatario(monkeypatch):
    _patch(monkeypatch)
    aut = buscar_autoridade("Sem Metadados")
    assert montar_destinatario(aut, "Coronel") == "Só o vocativo antigo"
