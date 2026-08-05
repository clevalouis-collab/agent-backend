import os
import json
import base64
import urllib.request
import urllib.error
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Agent IA - Pur HTTP", version="21.0")

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
        # 1. Préparation du PDF
        pdf_bytes = await file.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # 2. La sulfateuse : On teste les noms de modèles un par un
        models_to_try = [
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-1.5-pro",
            "gemini-1.5-flash-001"
        ]
        
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
        
        result = None
        
        # 3. Assaut HTTP direct
        for model_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode('utf-8'), 
                headers={'Content-Type': 'application/json'}
            )
            
            try:
                print(f"Tentative de connexion au modèle : {model_name}...")
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    print(f"✅ BINGO ! Le modèle {model_name} a répondu.")
                    break # On a la réponse, on stoppe la boucle
            except urllib.error.HTTPError as e:
                print(f"❌ Échec pour {model_name}.")
                continue # On passe au nom de modèle suivant
                
        if not result:
            raise Exception("Google a refusé tous les noms de modèles de la liste.")
            
        # 4. Extraction chirurgicale
        raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
        return {"data": json.loads(raw_text.strip())}
        
    except Exception as e:
        print(f"Erreur backend : {e}")
        raise HTTPException(status_code=500, detail=str(e))
