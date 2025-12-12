# app/ai_utils.py
from io import BytesIO
from typing import Literal, Dict, Any, List
import os
import re

from pypdf import PdfReader
from PIL import Image
import pytesseract

# ---------------------------------------------------------
# Configuración de Tesseract (binario del sistema)
# ---------------------------------------------------------
TESSERACT_CMD = os.getenv("TESSERACT_CMD")
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

DocType = Literal["factura", "informacion"]


# =========================================================
# EXTRACCIÓN DE TEXTO (PDF / IMAGEN)
# =========================================================
def _extract_with_tesseract_image(file_bytes: bytes) -> str:
    """
    Usa Tesseract OCR para extraer texto de una IMAGEN (JPG/PNG).
    """
    try:
        image = Image.open(BytesIO(file_bytes))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        text = pytesseract.image_to_string(image, lang="spa+eng")
        return text or ""
    except Exception as e:
        print(f"[Tesseract] Error al extraer texto: {e}")
        return ""


def extract_text_from_document(file_bytes: bytes, filename: str) -> str:
    """
    Extrae texto del documento (PDF -> pypdf, imágenes -> Tesseract).
    """
    name = filename.lower()
    _, ext = os.path.splitext(name)

    # PDF
    if ext == ".pdf":
        try:
            reader = PdfReader(BytesIO(file_bytes))
            texts: List[str] = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                texts.append(page_text)
            return "\n".join(texts)
        except Exception as e:
            print(f"[PDF] Error al extraer texto con pypdf: {e}")
            return ""

    # Imágenes
    if ext in (".jpg", ".jpeg", ".png"):
        return _extract_with_tesseract_image(file_bytes)

    return ""


# =========================================================
# CLASIFICACIÓN DEL DOCUMENTO
# =========================================================
def classify_document(text: str) -> DocType:
    """
    Clasificación simple por palabras clave.
    """
    text_lower = text.lower()

    invoice_keywords = [
        "factura",
        "factura proforma",
        "invoice",
        "subtotal",
        "iva",
        "rfc",
        "cuit",
        "total a pagar",
        "número de factura",
        "numero de factura",
        "no. factura",
    ]

    score = sum(1 for kw in invoice_keywords if kw in text_lower)
    if score >= 2:
        return "factura"
    return "informacion"


# --------------------------------------------------------------------
# Ítems de factura (líneas de tabla)
# --------------------------------------------------------------------
# Nuevo REGEX tolerante a ruido entre descripción y cantidad
_item_line_regex = re.compile(
    r"""
    ^\s*
    (?P<codigo>\w+)\s+                        # Código: Producto
    (?P<descripcion>[\w\s\-\~\.]+?)\s+        # Descripción (tolerante a "~" y ruido)
    (?P<cantidad>\d+)\s+                      # Cantidad (SIEMPRE un número)
    (?P<precio>\d+(?:[.,]\d{1,2})?)\s+        # Precio unitario
    (?P<total>\d+(?:[.,]\d{1,2})?)            # Total
    \s*$
    """,
    re.VERBOSE,
)


# 2) Patrón específico para la factura azul (Producto 1/2/3)
_product_line_regex = re.compile(
    r"""
    ^\s*
    (?P<codigo>Producto)\s*          # Literal 'Producto'
    (?P<descripcion>\d+)\s*          # Nº de producto (1,2,3)
    [^\d]*                           # Basura del OCR (~, -, etc.)
    (?P<cantidad>\d+)\s+             # Cantidad
    (?P<precio>\d+(?:[.,]\d*)?)\s+   # Precio unitario (100 o 100,00)
    (?P<total>\d+(?:[.,]\d*)?)       # Total (200 o 200,00)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _to_float(s: str) -> float:
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_invoice_items(text: str) -> List[Dict[str, Any]]:
    items = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = _item_line_regex.match(line)
        if not m:
            continue

        def _to_float(s: str) -> float:
            s = s.replace(".", "").replace(",", ".")
            try:
                return float(s)
            except:
                return 0.0

        codigo = m.group("codigo")
        descripcion = m.group("descripcion").strip(" -~")
        cantidad = int(m.group("cantidad"))
        precio = _to_float(m.group("precio"))
        total = _to_float(m.group("total"))

        items.append({
            "codigo": codigo,
            "descripcion": descripcion,
            "cantidad": cantidad,
            "precio_unitario": precio,
            "total": total,
        })

    return items



# =========================================================
# EXTRACCIÓN DE CAMPOS DE FACTURA
# =========================================================
def extract_invoice_data(text: str) -> Dict[str, Any]:
    """
    Extracción básica de datos de una factura usando heurísticas y regex.
    """
    tl = text.lower()

    def find_after_any(labels, max_chars: int = 100) -> str:
        """
        Busca cualquiera de los labels (lista de strings) en el texto en minúsculas
        y devuelve la primera línea no vacía que aparezca a continuación.
        """
        if isinstance(labels, str):
            labels_list = [labels]
        else:
            labels_list = labels

        for label in labels_list:
            idx = tl.find(label)
            if idx == -1:
                continue
            fragment = text[idx + len(label): idx + len(label) + max_chars]
            for line in fragment.splitlines():
                line = line.strip(" :;-•\t")
                if line:
                    return line
        return ""

    # ---------------- CLIENTE ----------------
    cliente = find_after_any(["cliente", "client"])
    if not cliente:
        cliente = find_after_any(["razón social", "razon social"])

    # ---------------- PROVEEDOR / EMISOR ----------------
    proveedor = find_after_any(["emisor", "proveedor", "vendedor"])
    if not proveedor:
        proveedor = find_after_any(["razón social", "razon social"])

    # Heurística extra para la factura azul:
    # línea tipo "Orlando Juan Loban Empresa de logistica, S. L."
    if (not cliente or not proveedor) and "empresa de" in tl:
        for raw_line in text.splitlines():
            if "empresa de" in raw_line.lower():
                m = re.search(
                    r"(?P<cli>[A-ZÁÉÍÓÚÑ][^ \n]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñü]+)*)\s+"
                    r"(?P<prov>Empresa\s+de[^\n]+)",
                    raw_line,
                    flags=re.IGNORECASE,
                )
                if m:
                    if not cliente:
                        cliente = m.group("cli").strip()
                    if not proveedor:
                        proveedor = m.group("prov").strip()
                    break

    # ---------------- NÚMERO DE FACTURA ----------------
    numero_factura = ""

    # 1) patrón específico: "Número de factura: 2024-0001"
    m = re.search(
        r"(?:n[uú]mero\s+de\s+factura|numero\s+de\s+factura)"
        r"[^\S\r\n]*[:#\-]?\s*([A-Z0-9\-/\.]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        numero_factura = m.group(1).strip()

    # 2) otras formas típicas
    if not numero_factura:
        m = re.search(
            r"(?:n[°ºo]\s*factura|nro\.?\s*factura|factura\s*n[°ºo]?)"
            r"[^\S\r\n]*[:#\-]?\s*([A-Z0-9\-/\.]+)",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            numero_factura = m.group(1).strip()

    # 3) fallback
    if not numero_factura:
        numero_factura = find_after_any(
            ["n° factura", "no. factura", "nro factura", "n° comprobante"],
            max_chars=40,
        )

    # ---------------- FECHA ----------------
    fecha = ""
    m = re.search(
        r"(fecha\s+(?:emisi[oó]n|factura|comprobante)[^\d]{0,15})"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        fecha = m.group(2).strip()
    else:
        m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)
        if m:
            fecha = m.group(1).strip()

    # ---------------- TOTAL ----------------
    total = ""
    for line in text.splitlines():
        line_lower = line.lower()
        if "importe total" in line_lower or "total" in line_lower:
            nums = re.findall(r"(\d[\d\.,]*)", line)
            if nums:
                total = nums[-1].strip()

    # Fallback: si no encontró "total", tomar el último número grande del texto
    if not total:
        nums = re.findall(r"(\d[\d\.,]*)", text)
        if nums:
            total = nums[-1].strip()

    # ---------------- ÍTEMS ----------------
    items = _parse_invoice_items(text)

    return {
        "cliente": cliente or "",
        "proveedor": proveedor or "",
        "numero_factura": numero_factura or "",
        "fecha": fecha or "",
        "total": total or "",
        "items": items,
    }


# =========================================================
# ANÁLISIS PARA DOCUMENTOS DE INFORMACIÓN GENERAL
# =========================================================
def simple_sentiment(text: str) -> str:
    """
    'Análisis de sentimiento' básico.
    """
    positive_words = ["bueno", "excelente", "positivo", "satisfactorio", "feliz"]
    negative_words = ["malo", "negativo", "problema", "queja", "insatisfecho"]

    tl = text.lower()
    pos_score = sum(tl.count(w) for w in positive_words)
    neg_score = sum(tl.count(w) for w in negative_words)

    if pos_score > neg_score:
        return "positivo"
    if neg_score > pos_score:
        return "negativo"
    return "neutral"


def summarize(text: str, max_sentences: int = 3) -> str:
    """
    Resumen muy sencillo: primeras N oraciones separadas por punto.
    """
    sentences = [s.strip() for s in text.split(".") if s.strip()]
    return ". ".join(sentences[:max_sentences])


# =========================================================
# FUNCIÓN PRINCIPAL DE ANÁLISIS
# =========================================================
def analyze_document(text: str) -> Dict[str, Any]:
    """
    - Clasifica el documento.
    - Si es factura, devuelve campos de factura (incluyendo ítems).
    - Si es información, devuelve descripción, resumen y sentimiento.
    """
    doc_type: DocType = classify_document(text)

    if doc_type == "factura":
        invoice_data = extract_invoice_data(text)
        return {
            "doc_type": doc_type,
            "kind": "factura",
            "raw_text_length": len(text),
            **invoice_data,
        }

    # Información general
    description = text[:200].replace("\n", " ")
    summary = summarize(text, max_sentences=3)
    sentiment = simple_sentiment(text)

    return {
        "doc_type": doc_type,
        "kind": "informacion",
        "raw_text_length": len(text),
        "description": description,
        "summary": summary,
        "sentiment": sentiment,
    }
