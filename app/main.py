import io
import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv
from app.schemas.invoice import InvoiceData

load_dotenv()

app = FastAPI(title="CFDI Extractor API", version="1.0.0")

# Cliente de Gemini
client = genai.Client()

SYSTEM_INSTRUCTION = """
Eres un auditor fiscal experto. Tu tarea es extraer los datos exactos del comprobante fiscal (factura) adjunto.

REGLAS DE MONTO NUMÉRICO CRÍTICAS:
1. "subtotal": Corresponde a la suma de los conceptos antes de aplicar impuestos (ej. $5000.00 -> 5000.0).
2. "iva_amount": Corresponde exclusivamente al impuesto IVA (ej. $800.00 -> 800.0).
3. "total": Corresponde al monto total a pagar, resultante de subtotal + impuestos (ej. $5800.00 -> 5800.0).
4. Para cada ítem en "items", extrae cantidad, descripción, precio unitario e importe correspondiente.
"""

# Nombres de modelos actualizados
PREFERRED_MODELS = ['gemini-3.6-flash', 'gemini-3.1-pro-preview']

@app.get("/")
def read_root():
    return {"status": "online", "service": "CFDI Extractor API"}

@app.post("/extract-file", response_model=InvoiceData)
async def extract_invoice_file(file: UploadFile = File(...)):
    contents = await file.read()
    mime_type = file.content_type or "application/pdf"
    file_part = types.Part.from_bytes(data=contents, mime_type=mime_type)
    prompt = f"{SYSTEM_INSTRUCTION}\n\nExtrae los datos fiscales del comprobante."

    last_error = None
    for model_name in PREFERRED_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt, file_part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=InvoiceData,
                    temperature=0.0,
                ),
            )
            return InvoiceData.model_validate_json(response.text)
        except Exception as e:
            last_error = e
            continue

    raise HTTPException(status_code=500, detail=f"Error con los modelos: {str(last_error)}")
