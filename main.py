import os
import asyncio
from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

app = FastAPI(title="API Agent IA - CLFinance Bulldozer", version="37.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def process_single_file(file_bytes: bytes, filename: str, api_key: str):
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        mime_type = "application/pdf"
    elif filename_lower.endswith((".jpg", ".jpeg")):
        mime_type = "image/jpeg"
    elif filename_lower.endswith(".png"):
        mime_type = "image/png"
    else:
        return {"filename": filename, "error": "Format non supporté (PDF, JPG, PNG uniquement)"}

    # Tentative blindée avec 3 essais automatiques en cas de micro-coupure réseau
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = genai.Client(api_key=api_key)
            model = 'gemini-2.0-flash'
            
            prompt = "Tu es un DAF de CLFinance. Analyse ce document (facture ou reçu). Renvoie UNIQUEMENT un objet JSON valide avec les clés exactes : fournisseur, numero_facture, date_emission, montant_ht, tva, montant_ttc, devise, iban. Si une info est illisible, mets null. Aucun autre texte."
            
            image_part = types.Part.from_bytes(
                data=file_bytes,
                mime_type=mime_type,
            )
            
            response = client.models.generate_content(
                model=model,
                contents=[prompt, image_part]
            )
            
            raw_text = response.text.strip()
            if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
            if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
            if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
            import json
            data_json = json.loads(raw_text.strip())
            return {"filename": filename, "data": data_json}
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2) # Petite pause locale avant de retenter
                continue
            return {"filename": filename, "error": str(e)}

@app.post("/extract-batch")
async def extract_batch(files: List[UploadFile] = File(...)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
        
    results = []
    # Mode Bulldozer : Traitement un par un propre, sans s'affoler, cadencé à la perfection
    for file in files:
        file_bytes = await file.read()
        res = process_single_file(file_bytes, file.filename, api_key)
        results.append(res)
        await asyncio.sleep(1.2) # Pause de sécurité anti-saturation Google
        
    return {"results": results}

@app.post("/extract-pdf")
async def extract_pdf_single(file: UploadFile = File(...)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
    file_bytes = await file.read()
    res = process_single_file(file_bytes, file.filename, api_key)
    return res
