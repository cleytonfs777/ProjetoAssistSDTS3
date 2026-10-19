# SEI Automation API

API REST (FastAPI + Playwright) que automatiza o SEI de Minas Gerais: recebe o número de um processo, faz login, percorre a árvore de documentos e devolve o conteúdo de cada documento (HTML, PDF e, com OCR instalado, imagem) em JSON.

Documentação completa — arquitetura, fluxo, iframes do SEI, depuração, pendências e plano de Docker: **[ARQUITETURA.md](ARQUITETURA.md)**.

## Setup local

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium     # se falhar por timeout, ver ARQUITETURA.md seção 8.1
cp .env.example .env            # preencha as credenciais
```

Anexos do tipo imagem são ignorados por padrão (`LER_IMAGENS=false`). Para lê-los via OCR, instale e defina `LER_IMAGENS=true` no `.env`:

```bash
sudo apt install tesseract-ocr tesseract-ocr-por
pip install pytesseract pillow
```

## Rodar

```bash
uvicorn app.main:app --reload
```

- **Interface do ofício de resposta:** http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs

### Ofício de resposta (interface web)

1. Copie `dados/dadosmil.example.json` para `dados/dadosmil.json` e cadastre os militares (o arquivo tem CPFs e fica fora do git).
2. No `.env`, defina `OPENAI_API_KEY` (sem ela o texto é simulado), `DESPACHO_ASSINATURA` e, na rede da Prodemge, `OPENAI_PROXY`.
3. Abra http://127.0.0.1:8000/ e preencha o processo, o documento respondido, o assunto, o destinatário, o signatário, o militar da atribuição e o marcador.
4. **Pré-visualizar (sem gravar)** lê o processo e mostra o ofício e o despacho. **Gerar e enviar ao SEI** cria o ofício, adiciona o marcador com o despacho e atribui o processo.

Detalhes: [ARQUITETURA.md, seção 6.2](ARQUITETURA.md#62-ofício-de-resposta-interface-web-e-fluxo-completo).

```bash
curl -s -X POST http://127.0.0.1:8000/processos/consultar \
     -H "Content-Type: application/json" \
     -d '{"numero": "39563202632"}'
```

Resposta:

```json
{
  "numero": "39563202632",
  "documentos": {
    "CBMMG - Rel. Viagem/Determina...": "RELATÓRIO DE VIAGEM CBMMG ...",
    "Edital (151138170)": "texto extraído do PDF ..."
  }
}
```

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | interface web do ofício de resposta |
| GET | `/health` | status da API |
| GET | `/militares`, `/etiquetas`, `/configuracao` | dados usados pela interface |
| POST | `/processos/consultar` | `{"numero": "...", "tipo_documento": "Ofício"}` → documentos lidos (+ documento gerado se `CRIAR_DOCUMENTO=true`) |
| POST | `/oficios/responder` | fluxo completo: leitura → IA → ofício → marcador/despacho → atribuição (progresso em NDJSON) |

Com `CRIAR_DOCUMENTO=true`, `/processos/consultar` também cria um documento no processo com o texto da IA. Veja [ARQUITETURA.md, seção 6.1](ARQUITETURA.md#61-geração-de-documento-com-o-texto-da-ia).

## Mapear seletores (Playwright Codegen)

```bash
playwright codegen --target python-async -o gravacao_async.py \
  "https://www.sei.mg.gov.br/sip/login.php?sigla_orgao_sistema=GOVMG&sigla_sistema=SEI&infra_url=L3NlaS8="
```

Interaja com a tela; o codegen gera os locators. Copie para o Page Object correspondente em `app/pages/` e substitua CPF/senha gravados por `get_settings()`.

## Fluxo de trabalho para novas funcionalidades

1. `codegen` grava a interação → locators prontos
2. Cria/ajusta um Page Object em `app/pages/`
3. Define schemas em `app/schemas.py`
4. Expõe uma rota em `app/main.py`

## Docker (planejado)

Proposta de `Dockerfile`, `docker-compose.yml` e `.dockerignore`, com os cuidados específicos de Chromium em container, está em [ARQUITETURA.md, seção 13](ARQUITETURA.md#13-migração-para-docker-e-docker-compose).
