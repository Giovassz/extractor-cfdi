import hashlib
import os
from google.cloud import dlp_v2

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "extractor-cfdi-23198")

def generate_sha256_hash(data_bytes: bytes) -> str:
    """Genera un hash SHA-256 no reversible para garantizar la integridad del archivo."""
    return hashlib.sha256(data_bytes).hexdigest()

def mask_sensitive_rfc(rfc: str) -> str:
    """
    Anonimiza un RFC protegiendo los caracteres centrales PII.
    Ejemplo: 'ALUM990101XXX' -> 'ALUM******XXX'
    """
    if not rfc or len(rfc) < 10:
        return rfc
    return f"{rfc[:4]}******{rfc[-3:]}"
