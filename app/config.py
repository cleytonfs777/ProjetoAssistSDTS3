from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sei_base_url: str = "https://www.sei.mg.gov.br"
    sei_usuario: str = ""
    sei_senha: str = ""
    sei_orgao: str = ""

    headless: bool = True
    nav_timeout_ms: int = 30_000
    # pool de contextos: quantos "navegadores lógicos" simultâneos
    pool_size: int = 2
    # anexos do tipo imagem: False = ignorados (fora do JSON); True = lidos via OCR
    ler_imagens: bool = False

    # POST /processos/consultar: cria um documento com o texto da IA ao final da leitura
    # (o fluxo completo de resposta fica em POST /oficios/responder)
    criar_documento: bool = False
    tipo_documento_padrao: str = "Ofício"

    # OpenAI; sem chave o texto é simulado (ver app/ia.py)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 1500
    openai_temperature: float = 0.7
    openai_timeout_s: float = 120
    # proxy corporativo, ex.: http://proxy.prodemge.gov.br:8080
    openai_proxy: str = ""
    # limite de caracteres do conteúdo do processo enviado à IA
    ia_max_caracteres: int = 100_000

    # cadastro dos militares: {"cpf": [nome, nome de guerra, tratamento, despedida,
    #                                   encaminhamento, graduação, função]}
    dadosmil_path: str = "dados/dadosmil.json"
    # vocativos por signatário do documento respondido: {"autoridades":[{"nome","destinatario"}]}
    autoridades_path: str = "dados/autoridades.json"
    # marcadores oferecidos na interface (precisam existir na unidade do SEI)
    etiquetas_path: str = "dados/etiquetas.json"
    # quem assina o texto do despacho (anotação do marcador)
    despacho_assinatura: str = "Cap Cleyton"
    despacho_max_caracteres: int = 250


@lru_cache
def get_settings() -> Settings:
    return Settings()
