from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import OpenAI
from supabase import create_client
import sys

app = FastAPI()

# CORS middleware: staat ALLES toe (voor debug, niet voor productie!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Laat alle origins toe
    allow_credentials=True,
    allow_methods=["*"],  # Laat alle HTTP methoden toe
    allow_headers=["*"],  # Laat alle headers toe
)

# Environment variables ophalen
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE")
openai_api_key = os.getenv("OPENAI_API_KEY")

# Debug info naar logs sturen
print("DEBUG - SUPABASE_URL:", supabase_url, file=sys.stderr)
print("DEBUG - SUPABASE_SERVICE_ROLE:", supabase_key, file=sys.stderr)
print("DEBUG - OPENAI_API_KEY:", (openai_api_key[:5] + "...") if openai_api_key else None, file=sys.stderr)

# Check of keys bestaan
if not supabase_url or not supabase_key:
    raise Exception("Supabase URL en key moeten als environment variables gezet zijn.")
if not openai_api_key:
    raise Exception("OpenAI API key moet als environment variable gezet zijn.")

# Clients aanmaken
supabase = create_client(supabase_url, supabase_key)
client = OpenAI(api_key=openai_api_key)

# Data models
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

# Endpoint om environment variables te checken
@app.get("/env")
async def get_env():
    return {
        "SUPABASE_URL": supabase_url,
        "SUPABASE_SERVICE_ROLE": supabase_key,
        "OPENAI_API_KEY": (openai_api_key[:5] + "...") if openai_api_key else None,
    }

# Endpoint om prompt te verwerken
@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
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
        temperature=0,
    )
    html = completion.choices[0].message.content.strip()
    timestamp = str(os.times().elapsed)

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

# Endpoint om preview te publiceren als live
@app.post("/publish")
async def publish_version(req: PublishRequest):
    version = supabase.table("versions").select("html_preview").eq("id", req.version_id).single().execute()
    if not version.data:
        return {"error": "Versie niet gevonden"}

    html_to_publish = version.data["html_preview"]

    supabase.table("versions").update({"html_live": html_to_publish}).eq("id", req.version_id).execute()

    return {"message": "Live versie bijgewerkt."}
