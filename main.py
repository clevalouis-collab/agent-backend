import os
import json
import base64
import asyncio
import time
import urllib.request
import urllib.error
from typing import List
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Agent IA - CLFinance Enterprise", version="33.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

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

    file_base64 = base64.b64encode(file_bytes).decode('utf-8')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [
                {
                    "text": "Tu es un DAF de CLFinance. Analyse ce document (facture ou reçu). S'il est de mauvaise qualité, fais de ton mieux. Renvoie UNIQUEMENT un objet JSON valide avec les clés exactes : fournisseur, numero_facture, date_emission, montant_ht, tva, montant_ttc, devise, iban. Si une info est illisible, mets null. Aucun autre texte."
                },
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": file_base64
                    }
                }
            ]
        }]
    }
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                
            raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
            if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
            if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
            if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
            data_json = json.loads(raw_text.strip())
            return {"filename": filename, "data": data_json}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {"filename": filename, "error": f"Erreur HTTP {e.code}"}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return {"filename": filename, "error": "Timeout / Erreur réseau"}

@app.post("/extract-batch")
async def extract_batch(files: List[UploadFile] = File(...)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
        
    loop = asyncio.get_running_loop()
    tasks = []
    
    for file in files:
        file_bytes = await file.read()
        tasks.append(
            loop.run_in_executor(executor, process_single_file, file_bytes, file.filename, api_key)
        )
        
    results = await asyncio.gather(*tasks)
    return {"results": results}

@app.post("/extract-pdf")
async def extract_pdf_single(file: UploadFile = File(...)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
    file_bytes = await file.read()
    res = process_single_file(file_bytes, file.filename, api_key)
    return res
