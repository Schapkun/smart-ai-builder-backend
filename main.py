# main.py (backend)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import OpenAI
from supabase import create_client
import sys

app = FastAPI()

# CORS middleware: sta expliciet je frontend- en preview-domeinen toe
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smart-ai-builder-frontend.onrender.com",
        "https://meester.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ENV vars
supabase_url      = os.getenv("SUPABASE_URL")
supabase_key      = os.getenv("SUPABASE_SERVICE_ROLE")
openai_api_key    = os.getenv("OPENAI_API_KEY")

# Debug naar logs
print("DEBUG - SUPABASE_URL:",      supabase_url,   file=sys.stderr)
print("DEBUG - SUPABASE_SERVICE_ROLE:", supabase_key, file=sys.stderr)
print("DEBUG - OPENAI_API_KEY:",   (openai_api_key[:5] + "...") if openai_api_key else None, file=sys.stderr)

if not supabase_url or not supabase_key:
    raise Exception("Supabase URL en key moeten als environment variables gezet zijn.")
if not openai_api_key:
    raise Exception("OpenAI API key moet als environment variable gezet zijn.")

# Clients aanmaken
supabase = create_client(supabase_url, supabase_key)
client   = OpenAI(api_key=openai_api_key)

# Data-modellen
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

@app.get("/env")
async def get_env():
    return {
        "SUPABASE_URL":      supabase_url,
        "SUPABASE_SERVICE_ROLE": supabase_key,
        "OPENAI_API_KEY":    (openai_api_key[:5] + "...") if openai_api_key else None
    }

@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    # Haal huidige live HTML
    res = supabase.table("versions") \
                  .select("html_live") \
                  .order("timestamp", desc=True) \
                  .limit(1) \
                  .execute()
    current_html = res.data[0]["html_live"] if res.data else """
    <!DOCTYPE html>
    <html><head><title>Meester.app</title></head>
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

    # Bewaar nieuwe preview
    supabase.table("versions").insert({
        "prompt": req.prompt,
        "html_preview": html,
        "html_live": current_html,
        "timestamp": timestamp,
    }).execute()

    return {"html": html, "version_timestamp": timestamp}

@app.post("/publish")
async def publish_version(req: PublishRequest):
    row = supabase.table("versions") \
                  .select("html_preview") \
                  .eq("id", req.version_id) \
                  .single() \
                  .execute()
    if not row.data:
        return {"error": "Versie niet gevonden"}

    html_to_publish = row.data["html_preview"]
    supabase.table("versions") \
            .update({"html_live": html_to_publish}) \
            .eq("id", req.version_id) \
            .execute()

    return {"message": "Live versie bijgewerkt."}
