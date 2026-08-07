import os
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
import resend
from supabase import create_client
import httpx
import google.generativeai as genai

app = FastAPI()

resend.api_key = os.environ.get("RESEND_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gfzgpsmazicmpzykwsht.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_EC1AjbMq9Uy-EbBA845sZg_4MkqlhzC")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

class InvoiceData(BaseModel):
    fournisseur: Optional[str] = None
    numero_facture: Optional[str] = None
    date_emission: Optional[str] = None
    montant_ht: Optional[float] = None
    tva: Optional[float] = None
    montant_ttc: Optional[float] = None
    devise: Optional[str] = "EUR"
    iban: Optional[str] = None
    category: Optional[str] = "Frais généraux"

@app.post("/webhook/email")
async def inbound_email_webhook(request: Request):
    """
    Reçoit les e-mails entrants de Resend, extrait la facture et l'insère dans Supabase.
    """
    try:
        payload = await request.json()
        
        # On vérifie qu'il s'agit bien d'un e-mail reçu
        if payload.get("type") != "email.received":
            return {"status": "ignored"}
            
        data = payload.get("data", {})
        email_id = data.get("email_id")
        sender_email = data.get("from", "")
        
        # Déduire le nom du client depuis l'expéditeur (ou utiliser l'adresse e-mail brute)
        client_name = sender_email.split("@")[0].capitalize() if "@" in sender_email else "Client Email"

        # 1. Récupérer les pièces jointes de l'e-mail via l'API Resend
        attachments_response = resend.Emails.Receiving.Attachments.list(email_id=email_id)
        attachments = getattr(attachments_response, "data", [])

        if not attachments:
            return {"status": "no_attachments"}

        # 2. Traiter la première pièce jointe (PDF ou Image)
        for att in attachments:
            file_name = att.get("filename", "facture.pdf")
            download_url = att.get("download_url")
            
            if not download_url:
                continue

            # Télécharger le fichier
            async with httpx.AsyncClient() as client:
                file_resp = await client.get(download_url)
                file_bytes = file_resp.content

            # 3. Envoyer à Gemini pour extraction
            model = genai.GenerativeModel("gemini-1.5-flash")
            prompt = """
            Analyse cette facture et renvoie un JSON strict avec ces clés:
            fournisseur, numero_facture, date_emission (YYYY-MM-DD), montant_ht (float), tva (float), montant_ttc (float), devise, iban, category.
            """
            
            # Appel Gemini avec les octets du fichier
            response = model.generate_content([
                {'mime_type': 'application/pdf', 'data': file_bytes},
                prompt
            ])
            
            # Nettoyage et parsing du JSON renvoyé par l'IA
            text_res = response.text.replace("```json", "").replace("```", "").strip()
            import json
            parsed_data = json.loads(text_res)

            # 4. Sauvegarde automatique dans Supabase
            new_invoice = {
                "user_id": "SYSTEM_EMAIL_INGESTION", # Ou ID utilisateur lié si stocké en dur
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
                "category": parsed_data.get("category", "Frais généraux"),
            }
            
            supabase.from("invoices").insert([new_invoice]).execute()

        return {"status": "success", "processed_emails": 1}

    except Exception as e:
        print(f"Erreur Webhook Email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
