import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from app.schemas.invoice import InvoiceData

load_dotenv()

client = genai.Client()

prompt = "Analiza el texto de la factura y extrae los datos fiscales principales en formato JSON estricto."

sample_invoice_text = """
FACTURA: A-1024
EMISOR: DESARROLLO DE SOFTWARE Y SISTEMAS S.A. DE C.V.
RFC EMISOR: DSS120304ABC
RECEPTOR: SERVICIOS DIGITALES S.C.
RFC RECEPTOR: SDI180920XYZ
FECHA: 2026-09-23
CANTIDAD / DESCRIPCION / PRECIO UNITARIO / IMPORTE
1 / Desarrollo de API Backend Python / $20000.00 / $20000.00
SUBTOTAL: $20000.00
IVA (16%): $3200.00
TOTAL: $23200.00 MXN
"""

response = client.models.generate_content(
    model='gemini-3.6-flash',
    contents=[prompt, sample_invoice_text],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=InvoiceData,
        temperature=0.1,
    ),
)

print("\n--- Extracción Estructurada con Gemini ---")
print(response.text)
