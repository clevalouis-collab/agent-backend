import os
import json
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

app = FastAPI(title="API Agent IA", version="16.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF uniquement.")
        
    try:
        pdf_bytes = await file.read()
        prompt = """
        Tu es un DAF. Analyse visuellement cette facture.
        Renvoie UNIQUEMENT un objet JSON valide avec les clés exactes suivantes, sans aucun autre texte autour, sans markdown (pas de ```json) :
        {"fournisseur": "Nom", "numero_facture": "Num", "date_emission": "JJ/MM/AAAA", "montant_ht": 0.0, "tva": 0.0, "montant_ttc": 0.0, "iban": "IBAN ou null"}
        """
        
        # LA FORCE BRUTE : On tire dans le tas jusqu'à ce que Google accepte
        models_to_try = [
            'gemini-1.5-flash-001',
            'gemini-1.5-pro-001',
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-1.5-flash-latest',
            'gemini-1.5-pro-latest'
        ]
        
        raw_text = None
        for model_name in models_to_try:
            try:
                print(f"Tentative de forçage avec : {model_name}")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([
                    prompt,
                    {"mime_type": "application/pdf", "data": pdf_bytes}
                ])
                raw_text = response.text
                print(f"✅ Cible abattue avec : {model_name}")
                break  # Ça passe, on sort de la boucle
            except Exception as e:
                print(f"❌ Échec {model_name} : {e}")
                continue  # Ça casse, on passe à la balle suivante
                
        if not raw_text:
            raise Exception("L'API Google a rejeté tous les modèles de la liste.")
            
        # Nettoyage chirurgical du JSON
        raw_text = raw_text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
        return {"data": json.loads(raw_text.strip())}
        
    except Exception as e:
        print(f"Erreur fatale : {e}")
        raise HTTPException(status_code=500, detail=str(e))
