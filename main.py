import os
import json
import base64
import urllib.request
import urllib.error
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Agent IA - Pur HTTP", version="20.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF uniquement.")
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
        
    try:
        # 1. On lit le PDF et on le transforme en texte chiffré (Base64) pour voyager sur le web
        pdf_bytes = await file.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # 2. On contourne la bibliothèque Google en tapant directement sur leur serveur REST
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [
                    {
                        "text": "Tu es un DAF. Analyse cette facture. Renvoie UNIQUEMENT un objet JSON valide avec les clés exactes : fournisseur, numero_facture, date_emission, montant_ht, tva, montant_ttc, iban. Aucun autre texte."
                    },
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": pdf_base64
                        }
                    }
                ]
            }]
        }
        
        # 3. Envoi de la roquette
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_info = e.read().decode()
            print(f"Refus du serveur Google : {error_info}")
            raise Exception(f"Clé API rejetée ou erreur Google ({e.code}). Vérifie la clé.")
            
        # 4. Extraction chirurgicale
        raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
        return {"data": json.loads(raw_text.strip())}
        
    except Exception as e:
        print(f"Erreur backend : {e}")
        raise HTTPException(status_code=500, detail=str(e))
