import os
import json
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

app = FastAPI(title="API Agent IA - Expert Comptable Vision", version="15.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ATTENTION: Variable d'environnement manquante.")
genai.configure(api_key=GEMINI_API_KEY)

# LA SOLUTION DE FORCE : Le code cherche lui-même le bon modèle dispo pour ta clé
def get_working_vision_model():
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            # On cherche un modèle 1.5 (qui gère la vision PDF/Image)
            if '1.5' in m.name:
                return m.name
    # Si vraiment il ne trouve pas, il tente le standard de base
    return 'models/gemini-1.5-flash'

@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont acceptés.")
        
    try:
        pdf_bytes = await file.read()
        
        # On appelle notre détecteur automatique
        model_name = get_working_vision_model()
        print(f"✅ Modèle trouvé et forcé : {model_name}")
        
        model = genai.GenerativeModel(model_name)
        
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
        
    except Exception as e:
        print(f"❌ Erreur serveur : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")
