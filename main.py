import os
import asyncio
from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

app = FastAPI(title="API Agent IA - CLFinance SDK Officiel", version="50.0")

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
        return {"filename": filename, "error": "Format non supporté"}

    try:
        client = genai.Client(api_key=api_key)
        
        prompt = "Tu es un DAF de CLFinance. Analyse ce document (facture ou reçu). Renvoie UNIQUEMENT un objet JSON valide avec les clés exactes : fournisseur, numero_facture, date_emission, montant_ht, tva, montant_ttc, devise, iban. Si une info est illisible, mets null. Aucun autre texte."
        
        image_part = types.Part.from_bytes(
            data=file_bytes,
            mime_type=mime_type,
        )
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
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
        await asyncio.sleep(1.0)
        
    return {"results": results}

@app.post("/extract-pdf")
async def extract_pdf_single(file: UploadFile = File(...)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
    file_bytes = await file.read()
    res = process_single_file(file_bytes, file.filename, api_key)
    return res
