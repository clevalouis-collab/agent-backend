import os
import json
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

app = FastAPI(title="API Agent IA - Expert Comptable Vision", version="14.0")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration de l'API Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ATTENTION: Variable d'environnement GEMINI_API_KEY manquante.")
genai.configure(api_key=GEMINI_API_KEY)

@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont acceptés.")
        
    try:
        pdf_bytes = await file.read()
        
        # Le nom STRICT du modèle, sans les suffixes capricieux
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = """
        Tu es un DAF (Directeur Administratif et Financier) expert.
        Analyse visuellement cette facture en pièce jointe et extrais les informations clés.
        
        Renvoie-moi UNIQUEMENT un objet JSON valide avec les clés exactes suivantes, sans aucun autre texte autour, sans markdown (pas de ```json) :
        {
            "fournisseur": "Nom de l'entreprise",
            "numero_facture": "Le numéro de la facture",
            "date_emission": "JJ/MM/AAAA",
            "montant_ht": 0.00,
            "tva": 0.00,
            "montant_ttc": 0.00,
            "iban": "L'IBAN s'il y en a un, sinon null"
        }
        """
        
        response = model.generate_content([
            prompt,
            {
                "mime_type": "application/pdf",
                "data": pdf_bytes
            }
        ])
        
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "", 1)
        if raw_text.startswith("```"):
            raw_text = raw_text.replace("```", "", 1)
        if raw_text.endswith("```"):
            raw_text = raw_text[:raw_text.rfind("```")]
            
        raw_text = raw_text.strip()
        parsed_data = json.loads(raw_text)
        
        return {"data": parsed_data}
        
    except json.JSONDecodeError:
        print(f"Erreur de décodage JSON. Réponse brute : {response.text}")
        raise HTTPException(status_code=500, detail="L'IA n'a pas renvoyé un format de données valide.")
    except Exception as e:
        print(f"Erreur serveur : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse : {str(e)}")
