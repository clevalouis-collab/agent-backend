import os
import json
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

app = FastAPI(title="API Agent IA", version="17.0")

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
        
    temp_file_path = ""
    uploaded_gemini_file = None
    
    try:
        # 1. Création d'un vrai fichier temporaire (Exigence absolue de Google pour les PDF)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(await file.read())
            temp_file_path = temp_file.name
            
        # 2. Upload OFFICIEL via l'API Fichier de Google
        uploaded_gemini_file = genai.upload_file(path=temp_file_path, display_name=file.filename)
        
        # 3. L'IA lit le fichier
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """
        Tu es un DAF. Analyse visuellement cette facture.
        Renvoie UNIQUEMENT un objet JSON valide avec les clés exactes suivantes, sans aucun autre texte autour, sans markdown (pas de ```json) :
        {"fournisseur": "Nom", "numero_facture": "Num", "date_emission": "JJ/MM/AAAA", "montant_ht": 0.0, "tva": 0.0, "montant_ttc": 0.0, "iban": "IBAN ou null"}
        """
        
        response = model.generate_content([prompt, uploaded_gemini_file])
        
        # Nettoyage chirurgical du JSON
        raw_text = response.text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"): raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"): raw_text = raw_text[:raw_text.rfind("```")]
            
        return {"data": json.loads(raw_text.strip())}
        
    except Exception as e:
        print(f"Erreur fatale : {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 4. Nettoyage absolu des serveurs (Render et Google)
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if uploaded_gemini_file:
            genai.delete_file(uploaded_gemini_file.name)
