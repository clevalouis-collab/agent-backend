import os
import json
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import resend
from supabase import create_client
import httpx
import google.generativeai as genai

app = FastAPI()

# --- CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

resend.api_key = os.environ.get("RESEND_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gfzgpsmazicmpzykwsht.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_EC1AjbMq9Uy-EbBA845sZg_4MkqlhzC")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- ROUTE 1 : ANALYSE MANUELLE (Depuis ton site) ---
@app.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        # Détection automatique du type de fichier (PDF ou Image)
        mime_type = file.content_type if file.content_type else "application/pdf"
        if mime_type == "image/jpg": 
            mime_type = "image/jpeg"
            
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = """
        Analyse cette facture et renvoie uniquement un JSON strict avec ces clés:
        fournisseur, numero_facture, date_emission (YYYY-MM-DD), montant_ht (float), tva (float), montant_ttc (float), devise, iban, category.
        """
        response = model.generate_content([
            {'mime_type': mime_type, 'data': content},
            prompt
        ])
        text_res = response.text.replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(text_res)
        
        return {"status": "success", "filename": file.filename, "data": parsed_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- ROUTE 2 : AUTOMATISATION PAR EMAIL (Depuis Resend) ---
@app.post("/webhook/email")
async def inbound_email_webhook(request: Request):
    try:
        payload = await request.json()
        
        # Vérification du signal
        if payload.get("type") != "email.received":
            return {"status": "ignored"}
            
        data = payload.get("data", {})
        email_id = data.get("email_id")
        sender_email = data.get("from", "")
        
        # Déduire le nom du client
        client_name = sender_email.split("@")[0].capitalize() if "@" in sender_email else "Client Email"

        # Récupérer les pièces jointes
        attachments_response = resend.Emails.Receiving.Attachments.list(email_id=email_id)
        attachments = getattr(attachments_response, "data", [])

        if not attachments:
            return {"status": "no_attachments"}

        # Traiter les pièces jointes
        for att in attachments:
            file_name = att.get("filename", "facture.pdf")
            download_url = att.get("download_url")
            
            if not download_url:
                continue

            # Télécharger le fichier
            async with httpx.AsyncClient() as client:
                file_resp = await client.get(download_url)
                file_bytes = file_resp.content

            # Détection auto du format depuis l'extension de l'email
            mime_type = "application/pdf"
            lower_name = file_name.lower()
            if lower_name.endswith(".jpeg") or lower_name.endswith(".jpg"):
                mime_type = "image/jpeg"
            elif lower_name.endswith(".png"):
                mime_type = "image/png"

            # IA
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = """
            Analyse cette facture et renvoie uniquement un JSON strict avec ces clés:
            fournisseur, numero_facture, date_emission (YYYY-MM-DD), montant_ht (float), tva (float), montant_ttc (float), devise, iban, category.
            """
            response = model.generate_content([
                {'mime_type': mime_type, 'data': file_bytes},
                prompt
            ])
            text_res = response.text.replace("```json", "").replace("```", "").strip()
            parsed_data = json.loads(text_res)

            # Sauvegarde base de données
            new_invoice = {
                "user_id": "SYSTEM_EMAIL_INGESTION",
                "filename": file_name,
                "client_name": client_name,
                "fournisseur": parsed_data.get("fournisseur"),
                "numero_facture": parsed_data.get("numero_facture"),
                "date_emission": parsed_data.get("date_emission"),
                "montant_ht": parsed_data.get("montant_ht"),
                "tva": parsed_data.get("tva"),
                "montant_ttc": parsed_data.get("montant_ttc"),
                "devise": parsed_data.get("devise", "EUR"),
                "iban": parsed_data.get("iban"),
                "category": parsed_data.get("category", "Frais généraux")
            }
            
            supabase.table("invoices").insert([new_invoice]).execute()

        return {"status": "success"}

    except Exception as e:
        print(f"Erreur Webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
