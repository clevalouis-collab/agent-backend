from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import json
from pypdf import PdfReader
import requests

app = FastAPI(title="API Agent IA - Le Terminator", version="10.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Merci d'envoyer un vrai fichier PDF.")
    
    try:
        # 1. Lecture du PDF
        contents = await file.read()
        pdf_file = io.BytesIO(contents)
        reader = PdfReader(pdf_file)
        
        extracted_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
        
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Le PDF semble être un scan.")

        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Clé API non configurée.")

        prompt = f"""
        Tu es un assistant comptable expert pour les DAF. Extraire les infos en JSON STRICT.
        Ne réponds RIEN d'autre que l'objet JSON.
        
        Format attendu :
        {{
            "fournisseur": "Nom de l'entreprise",
            "montant_ttc": 0.00,
            "tva": 0.00,
            "iban": "Numéro IBAN ou N/A"
        }}
        
        Texte de la facture :
        {extracted_text}
        """

        # 2. LA BOUCLE TERMINATOR (Force Brute)
        models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        models_response = requests.get(models_url)
        
        if models_response.status_code != 200:
            raise Exception("Impossible de lire la liste des modèles Google.")
            
        models_data = models_response.json().get("models", [])
        
        extracted_data = None
        target_model_used = None
        last_error = ""

        # On teste tous les modèles un par un !
        for m in models_data:
            name = m.get("name", "")
            methods = m.get("supportedGenerationMethods", [])
            
            if "gemini" in name and "generateContent" in methods:
                print(f"⏳ Tentative avec {name}...")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/{name}:generateContent?key={GEMINI_API_KEY}"
                payload = { "contents": [{"parts": [{"text": prompt}]}] }
                
                api_response = requests.post(url, json=payload)
                
                # Si le modèle accepte, on traite la donnée et on ARRETE LA BOUCLE !
                if api_response.status_code == 200:
                    result_json = api_response.json()
                    response_text = result_json['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    if response_text.startswith("```json"):
                        response_text = response_text.replace("```json", "").replace("```", "").strip()
                    elif response_text.startswith("```"):
                        response_text = response_text.replace("```", "").strip()
                    
                    try:
                        extracted_data = json.loads(response_text)
                        target_model_used = name
                        print(f"✅ VICTOIRE avec {name} !")
                        break
                    except json.JSONDecodeError:
                        print(f"⚠️ {name} a mal formaté le JSON. On passe au suivant.")
                        continue
                else:
                    print(f"❌ {name} a refusé (Erreur {api_response.status_code}).")
                    last_error = str(api_response.status_code)

        if not extracted_data:
            raise Exception(f"Tous les modèles ont échoué. Dernière erreur : {last_error}")

        return {
            "message": f"Analyse IA ({target_model_used}) réussie.",
            "filename": file.filename,
            "data": extracted_data
        }
        
    except Exception as e:
        print(f"🚨 ERREUR CRASH IA : {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur du serveur IA : {str(e)}")
