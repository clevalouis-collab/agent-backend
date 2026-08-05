import os
import json
import base64
import urllib.request
import urllib.error
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="API Agent IA - Pur HTTP Auto", version="22.0")

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
        
        # 2. AUTO-DÉCOUVERTE : On interroge ton compte Google pour savoir ce qui est autorisé
        url_models = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            req_models = urllib.request.Request(url_models)
            with urllib.request.urlopen(req_models) as response:
                models_data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            raise Exception(f"Google refuse de lister tes modèles. Erreur : {err_msg}")
            
        # 3. On capture le premier modèle officiel disponible pour TA clé
        target_model = None
        for m in models_data.get('models', []):
            methods = m.get('supportedGenerationMethods', [])
            name = m.get('name', '') # ex: "models/gemini-2.0-flash"
            # On cherche un modèle qui génère du contenu
            if 'generateContent' in methods and ('flash' in name.lower() or 'pro' in name.lower()):
                target_model = name
                print(f"✅ Modèle détecté et verrouillé : {target_model}")
                break
                
        if not target_model:
            raise Exception("Ta clé API est valide, mais Google n'autorise aucun modèle d'analyse sur ce compte.")
            
        # 4. Assaut HTTP direct avec le BON modèle
        url_generate = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        
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
        
        req = urllib.request.Request(
            url_generate, 
            data=json.dumps(payload).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            # Si ça pète ici, le VRAI message de Google s'affichera sur ton site Web.
            raise Exception(f"Rejet par {target_model} : {err_msg}")
            
        # 5. Extraction chirurgicale
        raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
        return {"data": json.loads(raw_text.strip())}
        
    except Exception as e:
        print(f"Erreur backend : {e}")
        # On remonte l'erreur exacte à ton site Web
        raise HTTPException(status_code=500, detail=str(e))
