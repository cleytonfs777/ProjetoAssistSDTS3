from pydantic import BaseModel, Field


class ProcessoRequest(BaseModel):
    numero: str = Field(..., examples=["1400.01.0048767/2026-38"])


class ProcessoResponse(BaseModel):
    numero: str
    documentos: list[str]


class HealthResponse(BaseModel):
    status: str
