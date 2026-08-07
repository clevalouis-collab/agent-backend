import os
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

app = FastAPI()

# --- CONFIGURATION DE BASE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- TON MOTEUR QUI MARCHE (Analyse via Vercel) ---
@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        # Détection pour accepter PDF, JPG ou PNG sans planter
        mime_type = file.content_type if file.content_type else "application/pdf"
        if mime_type == "image/jpg": 
            mime_type = "image/jpeg"
            
        # On remet le modèle standard stable
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = """
        Analyse cette facture et renvoie uniquement un JSON strict avec ces clés:
        fournisseur, numero_facture, date_emission (YYYY-MM-DD), montant_ht (float), tva (float), montant_ttc (float), devise, iban, category.
        """
        
        response = model.generate_content([
            {'mime_type': mime_type, 'data': content},
            prompt
        ])
        
        # Nettoyage et renvoi du JSON à ton site Vercel
        text_res = response.text.replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(text_res)
        
        return {"status": "success", "filename": file.filename, "data": parsed_data}
        
    except Exception as e:
        print(f"Erreur IA: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
