from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import OpenAI
from supabase import create_client, Client

app = FastAPI()

# Supabase client setup
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE")
supabase: Client = create_client(supabase_url, supabase_key)

# CORS instellingen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Pas aan naar frontend domein in productie
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    # Haal laatst gepubliceerde HTML op als basis
    result = supabase.table("versions").select("html_live").order("timestamp", desc=True).limit(1).execute()
    current_html = result.data[0]["html_live"] if result.data else """
    <!DOCTYPE html>
    <html>
    <head><title>Meester.app</title></head>
    <body><div id='main'>Welkom bij Meester.app</div></body>
    </html>
    """

    ai_prompt = f"""
Je bent een AI die bestaande HTML aanpast op basis van een gebruikersvraag.
Geef alleen de volledige aangepaste HTML terug.

Huidige HTML:
{current_html}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""

    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": ai_prompt}],
        temperature=0
    )

    html = completion.choices[0].message.content.strip()
    timestamp = str(os.times().elapsed)

    # Sla preview op, live HTML blijft ongewijzigd
    supabase.table("versions").insert({
        "prompt": req.prompt,
        "html_preview": html,
        "html_live": current_html,
        "timestamp": timestamp,
    }).execute()

    return {
        "html": html,
        "version_timestamp": timestamp,
    }

@app.post("/publish")
async def publish_version(req: PublishRequest):
    # Vind preview versie op basis van id
    version = supabase.table("versions").select("html_preview").eq("id", req.version_id).single().execute()
    if not version.data:
        return {"error": "Versie niet gevonden"}

    html_to_publish = version.data["html_preview"]

    # Zet preview om naar live HTML
    supabase.table("versions").update({"html_live": html_to_publish}).eq("id", req.version_id).execute()

    return {"message": "Live versie bijgewerkt."}
