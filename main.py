from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict
import uuid

app = FastAPI(title="API Agent IA Financier", version="1.0")

class InvoiceTextRequest(BaseModel):
    text_content: str = Field(..., description="Texte brut de la facture")

db_documents: Dict[str, dict] = {}

def mock_llm_extraction(text: str):
    return {
        "fournisseur": "TechCorp SAS",
        "montant_ttc": 1200.00,
        "tva": 200.00,
        "iban": "FR76 3000 3000 3000 3000 3000 300"
    }

@app.post("/extract")
async def extract_invoice(request: InvoiceTextRequest):
    extracted_json = mock_llm_extraction(request.text_content)
    document_id = str(uuid.uuid4())
    
    db_documents[document_id] = {
        "status": "pending_validation",
        "data": extracted_json
    }
    
    return {
        "message": "Extraction réussie, en attente de validation DAF.",
        "document_id": document_id,
        "data": extracted_json
    }
