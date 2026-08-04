from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import json
from pypdf import PdfReader
from google import genai # <--- La nouvelle bibliothèque

app = FastAPI(title="API Agent IA Financier - Cerveau Gemini V3", version="3.0")

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
            raise HTTPException(status_code=400, detail="Le PDF semble être un scan.")

        # 2. IA Google (Nouvelle méthode)
        if not GEMINI_API_KEY:
            print("🚨 ERREUR : La clé GEMINI_API_KEY n'est pas trouvée dans Render !")
            raise HTTPException(status_code=500, detail="Clé API manquante.")

        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
        Tu es un expert comptable pour DAF. Extrais les infos de cette facture.
        Renvoie UNIQUEMENT un objet JSON valide, rien d'autre.
        
        Format :
        {{
            "fournisseur": "Nom de l'entreprise",
            "montant_ttc": 0.00,
            "tva": 0.00,
            "iban": "Numéro IBAN ou N/A"
        }}
        
        Texte :
        {extracted_text}
        """
        
        # Appel à la nouvelle API
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
        )
        
        # 3. Nettoyage
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        extracted_data = json.loads(response_text)

        return {
            "message": "Analyse IA terminée avec succès.",
            "filename": file.filename,
            "data": extracted_data
        }
        
    except Exception as e:
        # L'ALARME ROUGE : s'affichera dans les logs Render
        print(f"🚨 ERREUR CRASH IA : {str(e)}") 
        raise HTTPException(status_code=500, detail="Erreur interne du serveur IA.")
