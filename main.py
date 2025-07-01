# src/main.py

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
from openai import OpenAI
from supabase import create_client

app = FastAPI()

# --- 1) Globale CORS-middleware (debug) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Voor productie hier je frontend URL
    allow_credentials=True,
    allow_methods=["*"],        # Ook OPTIONS
    allow_headers=["*"],
)

# --- 2) Env-vars inladen & debugprint ---
SUPABASE_URL          = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")
OPENAI_API_KEY        = os.getenv("OPENAI_API_KEY")

print("🔧 SUPABASE_URL:",          SUPABASE_URL,          file=sys.stderr)
print("🔧 SUPABASE_SERVICE_ROLE:", SUPABASE_SERVICE_ROLE, file=sys.stderr)
print("🔧 OPENAI_API_KEY:",        (OPENAI_API_KEY[:5] + "...") if OPENAI_API_KEY else None, file=sys.stderr)

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
    raise Exception("Supabase URL + SERVICE_ROLE ontbreken als env vars.")
if not OPENAI_API_KEY:
    raise Exception("OpenAI API key ontbreekt als env var.")

# --- 3) Clients opzetten ---
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)
openai   = OpenAI(api_key=OPENAI_API_KEY)

# --- 4) Data-modellen ---
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

# --- 5) Health-endpoint ---
@app.get("/")
async def health_check():
    return {"status": "ok"}

# --- 6) Expliciete OPTIONS handlers voor preflight ---
@app.options("/prompt")
async def options_prompt():
    return Response(status_code=200)

@app.options("/publish")
async def options_publish():
    return Response(status_code=200)

# --- 7) /prompt endpoint ---
@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    # Huidige live HTML ophalen
    resp = supabase.table("versions") \
                   .select("html_live") \
                   .order("timestamp", desc=True) \
                   .limit(1) \
                   .execute()
    current_html = (
        resp.data[0]["html_live"]
        if resp.data
        else """
        <!DOCTYPE html>
        <html><head><title>Meester.app</title></head>
        <body><div id='main'>Welkom bij Meester.app</div></body>
        </html>
        """
    )

    ai_prompt = f"""
Je bent een AI die bestaande HTML aanpast op basis van een gebruikersvraag.
Geef alleen de volledige aangepaste HTML terug, zonder extra uitleg.

Huidige HTML:
{current_html}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""

    try:
        completion = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": ai_prompt}],
            temperature=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI-error: {e}")

    html = completion.choices[0].message.content.strip()
    timestamp = str(os.times().elapsed)

    # Preview wegschrijven, live blijft ongewijzigd
    supabase.table("versions").insert({
        "prompt":       req.prompt,
        "html_preview": html,
        "html_live":    current_html,
        "timestamp":    timestamp,
    }).execute()

    return {"html": html, "version_timestamp": timestamp}

# --- 8) /publish endpoint ---
@app.post("/publish")
async def publish_version(req: PublishRequest):
    version = supabase.table("versions") \
                      .select("html_preview") \
                      .eq("id", req.version_id) \
                      .single() \
                      .execute()
    if not version.data:
        raise HTTPException(status_code=404, detail="Versie niet gevonden")

    html_to_publish = version.data["html_preview"]
    supabase.table("versions") \
            .update({"html_live": html_to_publish}) \
            .eq("id", req.version_id) \
            .execute()

    return {"message": "Live versie bijgewerkt."}
