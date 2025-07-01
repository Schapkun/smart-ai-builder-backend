# === backend/main.py ===

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import OpenAI
from supabase import create_client

# 1. FastAPI-app opzetten
app = FastAPI(title="Smart AI Builder Backend")

# 2. CORS-middleware wérkelijk bovenaan registreren
#    Alleen jouw frontend-domein mag requests doen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://smart-ai-builder-frontend.onrender.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)

# 3. Environment variables lezen
supabase_url    = os.getenv("SUPABASE_URL")
supabase_key    = os.getenv("SUPABASE_SERVICE_ROLE")
openai_api_key  = os.getenv("OPENAI_API_KEY")

if not supabase_url or not supabase_key:
    raise Exception("Supabase URL en key missen (SUPABASE_URL / SUPABASE_SERVICE_ROLE).")
if not openai_api_key:
    raise Exception("OpenAI API key missen (OPENAI_API_KEY).")

# 4. Clients aanmaken
supabase = create_client(supabase_url, supabase_key)
client   = OpenAI(api_key=openai_api_key)

# 5. Pydantic-modellen
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

# 6. Test-endpoint om te checken dat de server draait
@app.get("/health")
async def health():
    return {"status": "ok"}

# 7. /prompt endpoint
@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    # Haal laatste live HTML op
    result = supabase.table("versions") \
                     .select("html_live") \
                     .order("timestamp", desc=True) \
                     .limit(1) \
                     .execute()
    current_html = result.data[0]["html_live"] if result.data else """
    <!DOCTYPE html>
    <html><head><title>Meester.app</title></head>
    <body><div id='main'>Welkom bij Meester.app</div></body>
    </html>
    """

    # Stel AI-prompt op
    ai_prompt = f"""
Je bent een AI die bestaande HTML aanpast op basis van een gebruikersvraag.
Geef alleen de volledige aangepaste HTML terug.

Huidige HTML:
{current_html}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""

    # Vraag GPT-4 om de HTML aan te passen
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": ai_prompt}],
        temperature=0,
    )

    html      = completion.choices[0].message.content.strip()
    timestamp = str(os.times().elapsed)

    # Sla de preview op
    supabase.table("versions").insert({
        "prompt":        req.prompt,
        "html_preview":  html,
        "html_live":     current_html,
        "timestamp":     timestamp,
    }).execute()

    return {
        "html":              html,
        "version_timestamp": timestamp,
    }

# 8. /publish endpoint
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
