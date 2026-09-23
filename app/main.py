import io
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv
from app.schemas.invoice import InvoiceData

load_dotenv()

app = FastAPI(title="CFDI Extractor API", version="1.0.0")
client = genai.Client()

PREFERRED_MODELS = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-2.5-flash']

class ExtractRequest(BaseModel):
    raw_text: str

SYSTEM_INSTRUCTION = """
Eres un experto contable y fiscal. Extrae la información del comprobante fiscal (factura) con máxima precisión.
Reglas estrictas para los valores numéricos:
1. Convierte todos los montos monetarios a números flotantes (ej. "$5000.00" -> 5000.0).
2. Asegúrate de mapear correctamente:
   - SUBTOTAL: El monto antes de impuestos.
   - IVA: El impuesto trasladado (IVA).
   - TOTAL: La suma del subtotal más impuestos.
3. Para cada ítem/concepto, extrae la cantidad, descripción, precio unitario e importe correspondiente.
"""

def generate_with_fallback(prompt: str, contents: list) -> str:
    last_error = None
    full_prompt = f"{SYSTEM_INSTRUCTION}\n\n{prompt}"
    for model_name in PREFERRED_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[full_prompt] + contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=InvoiceData,
                    temperature=0.0,
                ),
            )
            return response.text
        except APIError as e:
            last_error = e
            if e.code in (503, 500):
                continue
            raise e
    raise HTTPException(status_code=503, detail=f"Todos los modelos están saturados: {str(last_error)}")

@app.get("/")
def read_root():
    return {"status": "online", "service": "CFDI Extractor"}

@app.post("/extract", response_model=InvoiceData)
def extract_invoice_data(request: ExtractRequest):
    prompt = "Analiza el siguiente texto de factura y extrae los datos fiscales estructurados."
    json_response = generate_with_fallback(prompt, [request.raw_text])
    return InvoiceData.model_validate_json(json_response)

@app.post("/extract-file", response_model=InvoiceData)
async def extract_invoice_file(file: UploadFile = File(...)):
    contents = await file.read()
    mime_type = file.content_type or "application/pdf"
    file_part = types.Part.from_bytes(data=contents, mime_type=mime_type)
    prompt = "Analiza el documento/imagen adjunto de la factura y extrae los datos fiscales en formato JSON."
    json_response = generate_with_fallback(prompt, [file_part])
    return InvoiceData.model_validate_json(json_response)
