import io
import time
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

MODEL_NAME = 'gemini-3.6-flash'

class ExtractRequest(BaseModel):
    raw_text: str

SYSTEM_INSTRUCTION = """
Eres un contador público y auditor fiscal experto en comprobantes fiscales mexicanos (CFDI).
Tu objetivo es analizar el documento adjunto y extraer la información financiera con precisión matemática.

REGLAS STRICTAS DE MONTO Y CONCEPTOS:
1. 'subtotal': Corresponde al valor antes de impuestos de la suma de los conceptos/servicios (Ejemplo: si la suma es 5000.00, pon 5000.0).
2. 'iva_amount': Corresponde únicamente al impuesto trasladado IVA (Ejemplo: si el IVA es 800.00, pon 800.0).
3. 'total': Corresponde a la suma total a pagar (subtotal + IVA).
4. Para cada ítem en 'items':
   - 'quantity': Cantidad prestada/comprada.
   - 'description': Descripción completa del servicio o concepto.
   - 'unit_price': Precio por unidad antes de impuestos.
   - 'amount': Importe total del concepto (quantity * unit_price).
5. NUNCA asignes 0.0 al subtotal ni al unit_price si hay montos visibles en el documento.
"""

def generate_with_retry(prompt: str, contents: list = None, max_retries: int = 5) -> str:
    full_prompt = f"{SYSTEM_INSTRUCTION}\n\n{prompt}"
    payload = [full_prompt]
    if contents:
        payload.extend(contents)

    last_error = None

    for attempt in range(max_retries):
        try:
            print(f"Enviando petición a {MODEL_NAME} (intento {attempt + 1}/{max_retries})...")
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=payload,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=InvoiceData,
                    temperature=0.0,
                ),
            )
            return response.text
        except APIError as e:
            last_error = e
            print(f"APIError ({e.code}): {e.message}")
            
            # Si la API nos limita por cuotas (429), saturación (503) o error temporal (500)
            if e.code in (429, 503, 500) and attempt < max_retries - 1:
                # Tiempo de espera progresivo: 4s, 7s, 11s, 16s...
                wait_time = 4 + (attempt * 3)
                print(f"Cuota/Saturación detectada. Esperando {wait_time} segundos antes de reintentar...")
                time.sleep(wait_time)
                continue
            
            raise e
        except Exception as e:
            last_error = e
            break

    raise HTTPException(
        status_code=503, 
        detail=f"Servicio saturado o cuota excedida temporalmente: {str(last_error)}"
    )

@app.get("/")
def read_root():
    return {"status": "online", "service": "CFDI Extractor"}

@app.post("/extract", response_model=InvoiceData)
def extract_invoice_data(request: ExtractRequest):
    prompt = f"Extrae la información fiscal estructurada del siguiente texto de factura:\n\n{request.raw_text}"
    json_response = generate_with_retry(prompt)
    return InvoiceData.model_validate_json(json_response)

@app.post("/extract-file", response_model=InvoiceData)
async def extract_invoice_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        mime_type = file.content_type or "application/pdf"
        file_part = types.Part.from_bytes(data=contents, mime_type=mime_type)
        
        prompt = "Analiza directamente la imagen/documento adjunto de la factura. Revisa minuciosamente la tabla de conceptos y desglose de subtotales/impuestos para extraer la información estructurada."
        
        json_response = generate_with_retry(prompt, contents=[file_part])
        return InvoiceData.model_validate_json(json_response)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
