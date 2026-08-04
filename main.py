from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import json
from pypdf import PdfReader
import requests

app = FastAPI(title="API Agent IA Financier - Bypass Direct", version="6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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
            raise HTTPException(status_code=400, detail="Le PDF semble être un scan sans texte lisible.")

        # 2. BYPASS : Appel direct à l'URL de Google (Sans utiliser leur bibliothèque buggée)
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Clé API non configurée.")

        prompt = f"""
        Tu es un assistant comptable expert pour les DAF. Voici le texte extrait d'une facture.
        Ton travail est de trouver les informations suivantes et de me les renvoyer STRICTEMENT au format JSON.
        Ne réponds rien d'autre que l'objet JSON.
        
        Format attendu :
        {{
            "fournisseur": "Nom de l'entreprise",
            "montant_ttc": 0.00,
            "tva": 0.00,
            "iban": "Le numéro IBAN, ou N/A s'il n'y en a pas"
        }}
        
        Voici le texte de la facture :
        {extracted_text}
        """
        
        # L'URL d'attaque directe
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        # On frappe à la porte en HTTP pur
        api_response = requests.post(url, json=payload)
        
        if api_response.status_code != 200:
            raise Exception(f"Refus de Google : {api_response.text}")
            
        result_json = api_response.json()
        response_text = result_json['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # 3. Nettoyage et renvoi du JSON
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()
        
        extracted_data = json.loads(response_text)

        return {
            "message": "Analyse IA terminée avec succès.",
            "filename": file.filename,
            "data": extracted_data
        }
        
    except Exception as e:
        print(f"🚨 ERREUR CRASH IA : {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur du serveur IA : {str(e)}")
