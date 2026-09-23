from pydantic import BaseModel, Field
from typing import List, Optional

class InvoiceItem(BaseModel):
    description: str = Field(description="Descripción del producto o servicio")
    quantity: float = Field(description="Cantidad")
    unit_price: float = Field(description="Precio unitario")
    amount: float = Field(description="Importe total de la partida")

class TaxDetails(BaseModel):
    iva_amount: Optional[float] = Field(default=0.0, description="Monto total de IVA")
    retention_amount: Optional[float] = Field(default=0.0, description="Monto de retenciones si existen")

class InvoiceData(BaseModel):
    rfc_issuer: str = Field(description="RFC del emisor")
    name_issuer: str = Field(description="Nombre o razón social del emisor")
    rfc_receiver: str = Field(description="RFC del receptor")
    name_receiver: str = Field(description="Nombre o razón social del receptor")
    invoice_date: str = Field(description="Fecha de emisión en formato YYYY-MM-DD")
    currency: str = Field(description="Moneda (ej. MXN, USD)")
    subtotal: float = Field(description="Subtotal de la factura")
    taxes: TaxDetails = Field(description="Desglose de impuestos")
    total: float = Field(description="Monto total de la factura")
    items: List[InvoiceItem] = Field(description="Lista de conceptos o partidas")
