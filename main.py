import os
import json
import base64
import urllib.request
import urllib.error
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Agent IA - Tout Terrain", version="27.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    # 1. On accepte les PDF ET les images (les fameuses "photos de merde")
    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        mime_type = "application/pdf"
    elif filename.endswith((".jpg", ".jpeg")):
        mime_type = "image/jpeg"
    elif filename.endswith(".png"):
        mime_type = "image/png"
    else:
        raise HTTPException(status_code=400, detail="Format refusé. Envoie un PDF, un JPG ou un PNG.")
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Clé API manquante dans Render.")
        
    try:
        # 2. Lecture du fichier
        file_bytes = await file.read()
        file_base64 = base64.b64encode(file_bytes).decode('utf-8')
        
        # 3. Le tir sur gemini-3.6-flash
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [
                    {
                        "text": "Tu es un DAF. Analyse ce document (facture ou reçu). S'il est de mauvaise qualité, fais de ton mieux pour extraire les infos. Renvoie UNIQUEMENT un objet JSON valide avec les clés exactes : fournisseur, numero_facture, date_emission, montant_ht, tva, montant_ttc, iban. Si une info est illisible, mets null. Aucun autre texte."
                    },
                    {
                        "inline_data": {
                            "mime_type": mime_type, # <-- ICI : On donne le VRAI format à Google
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
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            raise Exception(f"Erreur Google : {err_msg}")
            
        # 4. Extraction chirurgicale
        raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
        return {"data": json.loads(raw_text.strip())}
        
    except Exception as e:
        print(f"Erreur fatale : {e}")
        raise HTTPException(status_code=500, detail=str(e))
