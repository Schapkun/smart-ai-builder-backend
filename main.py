# main.py (BACKEND)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
from openai import OpenAI
from supabase import create_client

app = FastAPI()

# --- 1) CORS INSTELLINGEN (sta alle origins toe voor debug) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # voor productie hier je frontend-domein invullen
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2) ENVIRONMENT VARIABLES OPHALEN ---
SUPABASE_URL           = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE  = os.getenv("SUPABASE_SERVICE_ROLE")
OPENAI_API_KEY         = os.getenv("OPENAI_API_KEY")

# Debug-print in de Render-logs:
print("🔧 SUPABASE_URL:",          SUPABASE_URL,          file=sys.stderr)
print("🔧 SUPABASE_SERVICE_ROLE:", SUPABASE_SERVICE_ROLE, file=sys.stderr)
print("🔧 OPENAI_API_KEY:",        (OPENAI_API_KEY[:5] + "...") if OPENAI_API_KEY else None, file=sys.stderr)

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
    raise Exception("Supabase URL + SERVICE_ROLE missen als environment variables.")
if not OPENAI_API_KEY:
    raise Exception("OpenAI API key ontbreekt als environment variable.")

# --- 3) CLIENTS AANMAKEN ---
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)
openai  = OpenAI(api_key=OPENAI_API_KEY)

# --- 4) DATA MODELS ---
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

# --- 5) TEST-ENDPOINT (root) ---
@app.get("/")
async def health_check():
    return {"status": "ok"}

# --- 6) /prompt ENDPOINT ---
@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    # Haal de laatst gepubliceerde HTML op
    result = supabase.table("versions") \
                     .select("html_live") \
                     .order("timestamp", desc=True) \
                     .limit(1) \
                     .execute()
    current_html = result.data[0]["html_live"] if result.data else """
    <!DOCTYPE html>
    <html>
    <head><title>Meester.app</title></head>
    <body><div id='main'>Welkom bij Meester.app</div></body>
    </html>
    """

    # Stel de prompt samen voor de AI
    ai_prompt = f"""
Je bent een AI die bestaande HTML aanpast op basis van een gebruikersvraag.
Geef alleen de volledige aangepaste HTML terug, zonder extra toelichting.

Huidige HTML:
{current_html}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""
    # Roep OpenAI aan
    try:
        completion = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": ai_prompt}],
            temperature=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI-fout: {e}")

    html = completion.choices[0].message.content.strip()
    timestamp = str(os.times().elapsed)

    # Sla alleen de preview op; de live-versie blijft ongewijzigd
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

# --- 7) /publish ENDPOINT ---
@app.post("/publish")
async def publish_version(req: PublishRequest):
    # Zoek de preview-versie op
    version = supabase.table("versions") \
                      .select("html_preview") \
                      .eq("id", req.version_id) \
                      .single() \
                      .execute()
    if not version.data:
        raise HTTPException(status_code=404, detail="Versie niet gevonden")

    html_to_publish = version.data["html_preview"]

    # Update de live-kolom naar de geselecteerde preview
    supabase.table("versions") \
            .update({"html_live": html_to_publish}) \
            .eq("id", req.version_id) \
            .execute()

    return {"message": "Live versie bijgewerkt."}
