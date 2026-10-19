from pydantic import BaseModel, Field, model_validator


class ProcessoRequest(BaseModel):
    numero: str = Field(..., examples=["1400.01.0048767/2026-38"])
    # tipo do documento a criar; vazio = TIPO_DOCUMENTO_PADRAO
    tipo_documento: str | None = Field(None, examples=["Ofício"])


class DocumentoGerado(BaseModel):
    tipo: str
    # nome do documento na árvore do SEI, ex.: "Ofício 77 (132999999)"
    nome: str | None
    conteudo: str


class ProcessoResponse(BaseModel):
    numero: str
    # {nome do documento na árvore: conteúdo em texto}
    documentos: dict[str, str]
    documento_gerado: DocumentoGerado | None = None


class HealthResponse(BaseModel):
    status: str


class MilitarResponse(BaseModel):
    cpf: str
    nome: str
    nome_guerra: str
    tratamento: str
    despedida: str
    encaminhamento: str
    graduacao: str
    posto: str = ""
    funcao: str = ""


class OpcaoAnalise(BaseModel):
    id: int
    titulo: str
    resumo: str


class AnaliseIAResponse(BaseModel):
    """JSON devolvido pela IA na análise prévia da demanda."""
    assunto: str
    signatario_documento_respondido: str = ""
    opcoes: list[OpcaoAnalise]

    @model_validator(mode="after")
    def _tres_opcoes(self):
        if len(self.opcoes) != 3:
            raise ValueError("A análise deve conter exatamente 3 opções")
        if {o.id for o in self.opcoes} != {1, 2, 3}:
            raise ValueError("As opções devem ter ids 1, 2 e 3")
        return self


class AnaliseDemandaRequest(BaseModel):
    processo: str = Field(..., examples=["1400.01.0008514/2026-81"])
    # documento alvo da resposta, ex.: "Ofício 388 (126102548)"
    referencia: str = Field(..., min_length=1)
    complementar: str = ""
    # se o usuário já escolheu signatário, usa o posto dele para montar o destinatário
    signatario_cpf: str = ""


class OficioRespostaRequest(BaseModel):
    processo: str = Field(..., examples=["1400.01.0008514/2026-81"])
    # documento que está sendo respondido, ex.: "Ofício 388 (126102548)"
    referencia: str = ""
    assunto: str = Field(..., min_length=3)
    # vocativo; vazio = montado automaticamente se houver autoridade + posto do signatário
    destinatario: str = ""

    # instruções extras para a IA
    complementar: str = ""
    signatario_cpf: str
    # tipo criado no SEI; vazio/None = TIPO_DOCUMENTO_PADRAO (Ofício)
    tipo_documento: str | None = None

    # despacho = anotação do marcador; atribuição = militar que recebe o processo
    atribuir_cpf: str
    etiqueta: str = "Aguardando Despacho do Major"
    despacho_complemento: str = ""
    # documentos citados no despacho, com artigo: ["o {oficio}", "a Nota Técnica nº 5"]
    # "{oficio}" vira o nome do ofício criado
    despacho_documentos: list[str] = Field(default_factory=lambda: ["o {oficio}"])
    # texto pronto do despacho; vazio = montado a partir do cadastro do militar
    despacho_texto: str = ""

    # True = lê o processo e gera os textos, mas não grava nada no SEI
    simular: bool = False
    criar_oficio: bool = True
    adicionar_marcador: bool = True
    atribuir: bool = True

    # etapa 2 (opcional): vindos da análise prévia; sem opcao_escolhida = fluxo idêntico ao de hoje
    id_analise: str | None = None
    opcao_escolhida: OpcaoAnalise | None = None
    informacoes_adicionais: str = ""
