import os
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import APIError
from google.cloud import bigquery
from dotenv import load_dotenv

from app.schemas.invoice import InvoiceData
from app.services.security import generate_sha256_hash, mask_sensitive_rfc

load_dotenv()

app = FastAPI(title="CFDI Extractor API - Secures", version="1.0.0")

client = genai.Client()

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "extractor-cfdi-23198")
bq_client = bigquery.Client(project=PROJECT_ID)
TABLE_ID = f"{PROJECT_ID}.fiscal_data.invoices"

MODEL_NAME = 'gemini-3.6-flash'

class ExtractRequest(BaseModel):
    raw_text: str

SYSTEM_INSTRUCTION = """
Eres un contador público y auditor fiscal experto en comprobantes fiscales mexicanos (CFDI).
Tu objetivo es analizar el documento adjunto y extraer la información financiera con precisión matemática.

REGLAS STRICTAS DE MONTO Y CONCEPTOS:
1. 'subtotal': Corresponde al valor antes de impuestos de la suma de los conceptos/servicios.
2. 'iva_amount': Corresponde únicamente al impuesto trasladado IVA.
3. 'total': Corresponde a la suma total a pagar (subtotal + IVA).
4. Para cada ítem en 'items':
   - 'quantity': Cantidad prestada/comprada.
   - 'description': Descripción completa del servicio o concepto.
   - 'unit_price': Precio por unidad antes de impuestos.
   - 'amount': Importe total del concepto.
"""

def save_to_bigquery_secure(invoice: InvoiceData, file_hash: str):
    """Inserta la factura en BigQuery aplicando enmascaramiento de PII y hash de seguridad."""
    
    # Enmascarar datos sensibles (PII) antes de guardar
    masked_rfc_receiver = mask_sensitive_rfc(invoice.rfc_receiver)

    rows_to_insert = [
        {
            "rfc_issuer": invoice.rfc_issuer,
            "name_issuer": invoice.name_issuer,
            "rfc_receiver": masked_rfc_receiver, # Guardado seguro
            "name_receiver": invoice.name_receiver,
            "invoice_date": invoice.invoice_date,
            "currency": invoice.currency,
            "subtotal": invoice.subtotal,
            "total": invoice.total,
            "processed_at": datetime.utcnow().isoformat(),
        }
    ]
    errors = bq_client.insert_rows_json(TABLE_ID, rows_to_insert)
    if errors:
        print(f"⚠️ Error insertando en BigQuery: {errors}")
    else:
        print(f"🔒 Registro guardado de forma segura en BQ (SHA256: {file_hash[:10]}...).")

def generate_with_retry(prompt: str, contents: list = None, max_retries: int = 5) -> str:
    full_prompt = f"{SYSTEM_INSTRUCTION}\n\n{prompt}"
    payload = [full_prompt]
    if contents:
        payload.extend(contents)

    last_error = None
    for attempt in range(max_retries):
        try:
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
            if e.code in (429, 503, 500) and attempt < max_retries - 1:
                time.sleep(4 + attempt * 3)
                continue
            raise e
        except Exception as e:
            last_error = e
            break

    raise HTTPException(status_code=503, detail=f"Servicio no disponible: {str(last_error)}")

@app.get("/")
def read_root():
    return {"status": "online", "service": "CFDI Extractor con Seguridad PII"}

@app.post("/extract-file", response_model=InvoiceData)
async def extract_invoice_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        
        # 1. Generar Hash SHA-256 de seguridad e integridad
        file_hash = generate_sha256_hash(contents)

        mime_type = file.content_type or "application/pdf"
        file_part = types.Part.from_bytes(data=contents, mime_type=mime_type)
        
        prompt = "Analiza directamente la imagen/documento adjunto de la factura y extrae la información fiscal estructurada."
        json_response = generate_with_retry(prompt, contents=[file_part])
        data = InvoiceData.model_validate_json(json_response)
        
        # 2. Persistencia en BigQuery con protección PII
        try:
            save_to_bigquery_secure(data, file_hash)
        except Exception as err:
            print(f"Error BQ: {err}")

        return data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")
