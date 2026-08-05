import os
import json
import base64
import urllib.request
import urllib.error
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Agent IA - Pur HTTP Bulldozer", version="23.0")

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
        
        # 2. Le Radar : On récupère TOUS tes modèles
        url_models = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            req_models = urllib.request.Request(url_models)
            with urllib.request.urlopen(req_models) as response:
                models_data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            raise Exception(f"Impossible de lister les modèles : {err_msg}")
            
        # On filtre pour ne garder que les modèles Gemini capables de lire des documents
        valid_models = []
        for m in models_data.get('models', []):
            methods = m.get('supportedGenerationMethods', [])
            name = m.get('name', '')
            if 'generateContent' in methods and 'gemini' in name.lower():
                valid_models.append(name)
                
        if not valid_models:
            raise Exception("Google ne t'autorise aucun modèle Gemini sur cette clé.")
            
        # 3. Le Bulldozer : On les essaye TOUS jusqu'à ce qu'un passe
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
        last_error = ""
        working_model = ""
        
        for target_model in valid_models:
            url_generate = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url_generate, 
                data=json.dumps(payload).encode('utf-8'), 
                headers={'Content-Type': 'application/json'}
            )
            
            try:
                print(f"Tentative de forçage avec : {target_model}...")
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    working_model = target_model
                    print(f"✅ BINGO ! La porte a cédé avec {working_model}")
                    break # ÇA PASSE ! On arrête la boucle et on continue.
            except urllib.error.HTTPError as e:
                last_error = e.read().decode('utf-8')
                print(f"❌ {target_model} a refusé. On passe au suivant.")
                continue # Ça pète, on essaye le modèle suivant.
                
        if not result:
            raise Exception(f"Google a bloqué TOUS les modèles. Dernière erreur : {last_error}")
            
        # 4. Extraction chirurgicale
        raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
        return {"data": json.loads(raw_text.strip())}
        
    except Exception as e:
        print(f"Erreur fatale : {e}")
        raise HTTPException(status_code=500, detail=str(e))
