# ─── backend/main.py ───────────────────────────────────────────────────────────

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import OpenAI
from supabase import create_client
import sys

# 1) FastAPI‐app aanmaken
app = FastAPI()

# 2) CORS‐middleware meteen na app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://smart-ai-builder-frontend.onrender.com"],  # jouw front-end URL
    allow_credentials=True,
    allow_methods=["OPTIONS", "POST"],  # preflight + POST toestaan
    allow_headers=["*"],
    max_age=600,
)

# 3) (Optioneel) expliciete preflight handler voor /prompt
@app.options("/prompt")
async def preflight_prompt():
    return Response(status_code=200)

# 4) Environment variables lezen
supabase_url       = os.getenv("SUPABASE_URL")
supabase_key       = os.getenv("SUPABASE_SERVICE_ROLE")
openai_api_key     = os.getenv("OPENAI_API_KEY")

# 5) Verplicht checken
if not supabase_url or not supabase_key:
    raise Exception("Supabase URL en key moeten als environment variables gezet zijn.")
if not openai_api_key:
    raise Exception("OpenAI API key moet als environment variable gezet zijn.")

# 6) Clients aanmaken
supabase = create_client(supabase_url, supabase_key)
client   = OpenAI(api_key=openai_api_key)

# 7) Data‐modellen
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

# 8) /prompt endpoint
@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    # haal laatste gepubliceerde live-HTML
    result = supabase.table("versions") \
                     .select("html_live") \
                     .order("timestamp", desc=True) \
                     .limit(1) \
                     .execute()

    current_html = result.data[0]["html_live"] if result.data else """
    <!DOCTYPE html>
    <html><head><title>Meester.app</title></head>
    <body><div id='main'>Welkom bij Meester.app</div></body></html>
    """

    # AI prompt bouw
    ai_prompt = f"""
Je bent een AI die bestaande HTML aanpast op basis van een gebruikersvraag.
Geef alleen de volledige aangepaste HTML terug.

Huidige HTML:
{current_html}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""

    # aanroep OpenAI
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": ai_prompt}],
        temperature=0
    )

    html      = completion.choices[0].message.content.strip()
    timestamp = str(os.times().elapsed)

    # sla preview op (live blijft ongewijzigd)
    supabase.table("versions").insert({
        "prompt":         req.prompt,
        "html_preview":   html,
        "html_live":      current_html,
        "timestamp":      timestamp,
    }).execute()

    return {
        "html":              html,
        "version_timestamp": timestamp,
    }

# 9) /publish endpoint
@app.post("/publish")
async def publish_version(req: PublishRequest):
    version = supabase.table("versions") \
                      .select("html_preview") \
                      .eq("id", req.version_id) \
                      .single() \
                      .execute()

    if not version.data:
        return {"error": "Versie niet gevonden"}

    html_to_publish = version.data["html_preview"]

    supabase.table("versions") \
            .update({"html_live": html_to_publish}) \
            .eq("id", req.version_id) \
            .execute()

    return {"message": "Live versie bijgewerkt."}
