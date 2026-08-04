from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
from pypdf import PdfReader

app = FastAPI(title="API Agent IA Financier - PDF Reader", version="1.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté.")
    
    try:
        contents = await file.read()
        pdf_file = io.BytesIO(contents)
        reader = PdfReader(pdf_file)
        
        extracted_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
        
        if not extracted_text.strip():
            extracted_text = "Texte illisible ou document scanné."

        simulated_extracted_data = {
            "fournisseur": f"Fournisseur détecté pour {file.filename}",
            "montant_ttc": 1250.00,
            "tva": 250.00,
            "iban": "FR76 3000 3000 3000 3000 300"
        }

        return {
            "message": "PDF lu et analysé avec succès par l'agent.",
            "filename": file.filename,
            "raw_text_preview": extracted_text[:200],
            "data": simulated_extracted_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la lecture du PDF : {str(e)}")
