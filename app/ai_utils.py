# app/ai_utils.py
from __future__ import annotations

from io import BytesIO
from typing import Literal, Dict, Any, List, Optional
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
# HELPERS
# =========================================================
def _to_float(s: str) -> float:
    """
    Convierte números tipo:
      - "1.308,80" -> 1308.80
      - "600,00"   -> 600.00
      - "1451"     -> 1451.0
    """
    s = (s or "").strip()
    if not s:
        return 0.0
    s = s.replace("€", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _infer_qty_from_total(price: float, total: float) -> Optional[int]:
    """
    Si OCR no capturó la cantidad pero tenemos precio+total,
    inferimos cantidad = total/price cuando da un entero razonable.
    """
    if price <= 0:
        return None
    qty = total / price
    rounded = int(round(qty))
    # tolerancia por redondeos de OCR
    if abs(qty - rounded) < 0.05 and 1 <= rounded <= 10_000:
        return rounded
    return None


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
    Extrae texto del documento:
    - PDF -> pypdf
    - imágenes -> Tesseract
    """
    name = (filename or "").lower()
    _, ext = os.path.splitext(name)

    if ext == ".pdf":
        try:
            reader = PdfReader(BytesIO(file_bytes))
            texts: List[str] = []
            for page in reader.pages:
                texts.append(page.extract_text() or "")
            return "\n".join(texts)
        except Exception as e:
            print(f"[PDF] Error al extraer texto con pypdf: {e}")
            return ""

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
    text_lower = (text or "").lower()

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
    return "factura" if score >= 2 else "informacion"


# =========================================================
# Ítems de factura (líneas de tabla)
# =========================================================

# Regex general: Código + descripción + cantidad + precio + total
_item_line_regex = re.compile(
    r"""
    ^\s*
    (?P<codigo>\w+)\s+
    (?P<descripcion>[\w\s\-\~\.]+?)\s+
    (?P<cantidad>\d+)\s+
    (?P<precio>\d+(?:[.,]\d{1,2})?)\s+
    (?P<total>\d+(?:[.,]\d{1,2})?)
    \s*$
    """,
    re.VERBOSE,
)

# Regex específico para "Producto 1 2 100 200,00" con basura OCR entre medio
_product_line_regex = re.compile(
    r"""
    ^\s*
    (?P<codigo>Producto)\s*
    (?P<descripcion>\d+)\s*
    [^\d]*                              # ruido OCR (~, -, etc)
    (?P<cantidad>\d+)\s+
    (?P<precio>\d+(?:[.,]\d*)?)\s+
    (?P<total>\d+(?:[.,]\d*)?)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Caso OCR roto: "Producto 2 ~ 150 600,00" (sin cantidad)
_product_line_noqty_regex = re.compile(
    r"""
    ^\s*
    (?P<codigo>Producto)\s*
    (?P<descripcion>\d+)\s*
    [^\d]+
    (?P<precio>\d+(?:[.,]\d*)?)\s+
    (?P<total>\d+(?:[.,]\d*)?)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _parse_invoice_items(text: str) -> List[Dict[str, Any]]:
    """
    Parsea ítems de factura desde el texto OCR / PDF.
    Estrategia:
      1) Intentar patrón "Producto X ..." (factura azul)
      2) Intentar patrón genérico
      3) Intentar patrón "Producto X ~ precio total" e inferir cantidad
    """
    items: List[Dict[str, Any]] = []

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # 1) Patrón específico factura azul (con cantidad)
        m = _product_line_regex.match(line)
        if m:
            codigo = m.group("codigo").strip()
            descripcion = m.group("descripcion").strip()
            cantidad = int(m.group("cantidad"))
            precio = _to_float(m.group("precio"))
            total = _to_float(m.group("total"))
            items.append(
                {
                    "codigo": codigo,
                    "descripcion": descripcion,
                    "cantidad": cantidad,
                    "precio_unitario": precio,
                    "total": total,
                }
            )
            continue

        # 2) Patrón genérico
        m = _item_line_regex.match(line)
        if m:
            codigo = m.group("codigo").strip()
            descripcion = m.group("descripcion").strip(" -~")
            cantidad = int(m.group("cantidad"))
            precio = _to_float(m.group("precio"))
            total = _to_float(m.group("total"))
            items.append(
                {
                    "codigo": codigo,
                    "descripcion": descripcion,
                    "cantidad": cantidad,
                    "precio_unitario": precio,
                    "total": total,
                }
            )
            continue

        # 3) Patrón factura azul SIN cantidad -> inferir cantidad
        m = _product_line_noqty_regex.match(line)
        if m:
            codigo = m.group("codigo").strip()
            descripcion = m.group("descripcion").strip()
            precio = _to_float(m.group("precio"))
            total = _to_float(m.group("total"))

            inferred = _infer_qty_from_total(precio, total)
            if inferred is None:
                continue

            items.append(
                {
                    "codigo": codigo,
                    "descripcion": descripcion,
                    "cantidad": inferred,
                    "precio_unitario": precio,
                    "total": total,
                }
            )
            continue

    return items


# =========================================================
# EXTRACCIÓN DE CAMPOS DE FACTURA
# =========================================================
def extract_invoice_data(text: str) -> Dict[str, Any]:
    """
    Extracción básica de datos de una factura usando heurísticas y regex.
    """
    tl = (text or "").lower()

    def find_after_any(labels, max_chars: int = 100) -> str:
        if isinstance(labels, str):
            labels_list = [labels]
        else:
            labels_list = labels

        for label in labels_list:
            idx = tl.find(label)
            if idx == -1:
                continue
            fragment = text[idx + len(label) : idx + len(label) + max_chars]
            for line in fragment.splitlines():
                line = line.strip(" :;-•\t")
                if line:
                    return line
        return ""

    # CLIENTE
    cliente = find_after_any(["cliente", "client"]) or find_after_any(
        ["razón social", "razon social"]
    )

    # PROVEEDOR
    proveedor = find_after_any(["emisor", "proveedor", "vendedor"])
    if not proveedor:
        proveedor = find_after_any(["razón social", "razon social"])

    # Heurística factura azul: "Orlando ... Empresa de logística..."
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
                    cliente = cliente or m.group("cli").strip()
                    proveedor = proveedor or m.group("prov").strip()
                    break

    # NÚMERO FACTURA
    numero_factura = ""
    m = re.search(
        r"(?:n[uú]mero\s+de\s+factura|numero\s+de\s+factura)"
        r"[^\S\r\n]*[:#\-]?\s*([A-Z0-9\-/\.]+)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        numero_factura = m.group(1).strip()

    if not numero_factura:
        m = re.search(
            r"(?:n[°ºo]\s*factura|nro\.?\s*factura|factura\s*n[°ºo]?)"
            r"[^\S\r\n]*[:#\-]?\s*([A-Z0-9\-/\.]+)",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            numero_factura = m.group(1).strip()

    if not numero_factura:
        numero_factura = find_after_any(
            ["n° factura", "no. factura", "nro factura", "n° comprobante"],
            max_chars=40,
        )

    # FECHA
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

    # TOTAL
    total = ""
    for line in text.splitlines():
        line_lower = line.lower()
        if "importe total" in line_lower or "total" in line_lower:
            nums = re.findall(r"(\d[\d\.,]*)", line)
            if nums:
                total = nums[-1].strip()

    if not total:
        nums = re.findall(r"(\d[\d\.,]*)", text)
        if nums:
            total = nums[-1].strip()

    # ÍTEMS
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
# ANÁLISIS DOCUMENTOS DE INFORMACIÓN
# =========================================================
def simple_sentiment(text: str) -> str:
    positive_words = ["bueno", "excelente", "positivo", "satisfactorio", "feliz"]
    negative_words = ["malo", "negativo", "problema", "queja", "insatisfecho"]

    tl = (text or "").lower()
    pos_score = sum(tl.count(w) for w in positive_words)
    neg_score = sum(tl.count(w) for w in negative_words)

    if pos_score > neg_score:
        return "positivo"
    if neg_score > pos_score:
        return "negativo"
    return "neutral"


def summarize(text: str, max_sentences: int = 3) -> str:
    sentences = [s.strip() for s in (text or "").split(".") if s.strip()]
    return ". ".join(sentences[:max_sentences])


# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================
def analyze_document(text: str) -> Dict[str, Any]:
    doc_type: DocType = classify_document(text)

    if doc_type == "factura":
        invoice_data = extract_invoice_data(text)
        return {
            "doc_type": doc_type,
            "kind": "factura",
            "raw_text_length": len(text or ""),
            **invoice_data,
        }

    description = (text or "")[:200].replace("\n", " ")
    summary = summarize(text, max_sentences=3)
    sentiment = simple_sentiment(text)

    return {
        "doc_type": doc_type,
        "kind": "informacion",
        "raw_text_length": len(text or ""),
        "description": description,
        "summary": summary,
        "sentiment": sentiment,
    }
