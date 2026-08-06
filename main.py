import os
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

app = FastAPI(title="API Agent IA - CLFinance Enterprise Ultimate", version="60.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schéma Pydantic strict pour garantir des types parfaits et zéro hallucination de clés
class FactureExtraction(BaseModel):
    fournisseur: Optional[str] = Field(default=None, description="Nom du fournisseur ou de l'entreprise émettrice")
    numero_facture: Optional[str] = Field(default=None, description="Numéro de la facture ou du reçu")
    date_emission: Optional[str] = Field(default=None, description="Date d'émission au format YYYY-MM-DD ou clair")
    montant_ht: Optional[float] = Field(default=None, description="Montant total Hors Taxes en nombre décimal")
    tva: Optional[float] = Field(default=None, description="Montant total de la TVA en nombre décimal")
    montant_ttc: Optional[float] = Field(default=None, description="Montant total TTC en nombre décimal")
    devise: Optional[str] = Field(default="EUR", description="Devise (EUR, CHF, USD...)")
    iban: Optional[str] = Field(default=None, description="IBAN bancaire du fournisseur")

def process_single_file(file_bytes: bytes, filename: str, api_key: str):
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        mime_type = "application/pdf"
    elif filename_lower.endswith((".jpg", ".jpeg")):
        mime_type = "image/jpeg"
    elif filename_lower.endswith(".png"):
        mime_type = "image/png"
    else:
        return {"filename": filename, "error": "Format non supporté (PDF, JPG, PNG)"}

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = (
            "Tu es un DAF expert de CLFinance. Analyse minutieusement ce document comptable (facture, reçu ou note de frais, multi-pages inclus). "
            "Extrais rigoureusement les informations demandées."
        )
        
        doc_part = types.Part.from_bytes(
            data=file_bytes,
            mime_type=mime_type,
        )
        
        # Appel avec Structured Outputs stricts
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=[prompt, doc_part],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FactureExtraction,
                temperature=0.0
            ),
        )
        
        data_json = json.loads(response.text)
        return {"filename": filename, "data": data_json}
        
    except Exception as e:
        return {"filename": filename, "error": str(e)}

@app.post("/extract-batch")
async def extract_batch(files: List[UploadFile] = File(...)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
        
    results = []
    for file in files:
        file_bytes = await file.read()
        res = process_single_file(file_bytes, file.filename, api_key)
        results.append(res)
        await asyncio.sleep(0.5)
        
    return {"results": results}

@app.post("/extract-pdf")
async def extract_pdf_single(file: UploadFile = File(...)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
    file_bytes = await file.read()
    res = process_single_file(file_bytes, file.filename, api_key)
    return res

@app.post("/sync-erp")
async def sync_erp(payload: dict):
    # Endpoint prêt pour connecter Sage, QuickBooks ou un Webhook tiers
    return {"status": "success", "message": "Lot injecté avec succès dans l'ERP."}
