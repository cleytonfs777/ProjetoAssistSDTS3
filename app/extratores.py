"""
Converte o arquivo de um anexo do SEI (bytes baixados) em texto.
Funções síncronas e pesadas em CPU: chame-as via asyncio.to_thread.
"""
import io

from pypdf import PdfReader

ASSINATURAS_IMAGEM = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"II*\x00", b"MM\x00*", b"BM")


def tipo_anexo(conteudo: bytes, content_type: str = "") -> str | None:
    """Retorna "pdf", "imagem" ou None (não suportado)."""
    content_type = content_type.lower()
    if conteudo.startswith(b"%PDF") or "pdf" in content_type:
        return "pdf"
    if conteudo.startswith(ASSINATURAS_IMAGEM) or content_type.startswith("image/"):
        return "imagem"
    return None


def extrair_texto_anexo(conteudo: bytes, content_type: str = "") -> str:
    tipo = tipo_anexo(conteudo, content_type)
    if tipo == "pdf":
        return texto_pdf(conteudo)
    if tipo == "imagem":
        return texto_imagem(conteudo)
    return f"[tipo de anexo não suportado: {content_type or 'desconhecido'}]"


def texto_pdf(conteudo: bytes) -> str:
    leitor = PdfReader(io.BytesIO(conteudo))
    texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages).strip()
    # PDF escaneado não tem camada de texto; precisaria de OCR página a página
    return texto or "[PDF sem texto extraível (provavelmente escaneado)]"


def texto_imagem(conteudo: bytes) -> str:
    # OCR é opcional: requer `sudo apt install tesseract-ocr tesseract-ocr-por`
    # e `pip install pytesseract pillow`
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "[imagem: OCR não instalado (pytesseract/pillow)]"
    try:
        return pytesseract.image_to_string(Image.open(io.BytesIO(conteudo)), lang="por").strip()
    except pytesseract.TesseractNotFoundError:
        return "[imagem: OCR não instalado (tesseract-ocr)]"
