# File: main.py  (Backend)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
from openai import OpenAI
from supabase import create_client

app = FastAPI()

# ─── 1) CORS ────────────────────────────────────────────────────────────
# Must come before any @app.route definitions!
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

# ─── 2) ENVIRONMENT ─────────────────────────────────────────────────────
supabase_url       = os.getenv("SUPABASE_URL")
supabase_key       = os.getenv("SUPABASE_SERVICE_ROLE")
openai_api_key     = os.getenv("OPENAI_API_KEY")

# Quick sanity-check in logs
print("DEBUG - SUPABASE_URL:",       supabase_url,    file=sys.stderr)
print("DEBUG - SUPABASE_SERVICE_ROLE:", supabase_key,   file=sys.stderr)
print("DEBUG - OPENAI_API_KEY:",    (openai_api_key[:5] + "...") if openai_api_key else None, file=sys.stderr)

if not supabase_url or not supabase_key:
    raise Exception("Supabase URL + service-role key must be set as env vars")
if not openai_api_key:
    raise Exception("OpenAI API key must be set as env var")

# Instantiate clients
supabase = create_client(supabase_url, supabase_key)
client   = OpenAI(api_key=openai_api_key)

# ─── 3) DATA MODELS ─────────────────────────────────────────────────────
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

# ─── 4) ROUTES ───────────────────────────────────────────────────────────

@app.get("/env")
async def get_env():
    """Simple diagnostics — make sure CORS also applies here."""
    return {
        "SUPABASE_URL":       supabase_url,
        "SUPABASE_SERVICE_ROLE": supabase_key,
        "OPENAI_API_KEY":     (openai_api_key[:5] + "...") if openai_api_key else None,
    }

@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    # fetch latest live HTML
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
        messages=[{"role":"user","content":ai_prompt}],
        temperature=0
    )

    html      = completion.choices[0].message.content.strip()
    timestamp = str(os.times().elapsed)

    # save preview (live HTML remains untouched)
    supabase.table("versions").insert({
        "prompt":        req.prompt,
        "html_preview":  html,
        "html_live":     current_html,
        "timestamp":     timestamp,
    }).execute()

    return {
        "html":             html,
        "version_timestamp": timestamp,
    }

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
