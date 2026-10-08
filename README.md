# SEI Automation API

## Setup
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # preencha credenciais
```

## Rodar
```bash
uvicorn app.main:app --reload
```

## Mapear seletores rápido (substitui achar XPath na mão)
```bash
playwright codegen https://seu-sei.gov.br/sei
```
Interaja com a tela; o codegen gera os locators. Cole no Page Object correspondente.

## Fluxo de trabalho
1. `codegen` grava a interação -> locators prontos
2. Cria/ajusta um Page Object em `app/pages/`
3. Expõe uma rota em `app/main.py`
