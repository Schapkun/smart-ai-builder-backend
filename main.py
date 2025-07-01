# File: main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, sys
from openai import OpenAI
from supabase import create_client

# ─── 1) App Setup ───────────────────────────────────────────────────────
app = FastAPI()

# ─── 2) CORS Middleware ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smart-ai-builder-frontend.onrender.com",
        "https://meester.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 3) Environment ─────────────────────────────────────────────────────
supabase_url   = os.getenv("SUPABASE_URL")
supabase_key   = os.getenv("SUPABASE_SERVICE_ROLE")
openai_key     = os.getenv("OPENAI_API_KEY")

print("DEBUG - SUPABASE_URL:", supabase_url, file=sys.stderr)
print("DEBUG - OPENAI_API_KEY:", (openai_key[:5] + "...") if openai_key else None, file=sys.stderr)

if not supabase_url or not supabase_key:
    raise Exception("SUPABASE_URL en SUPABASE_SERVICE_ROLE moeten als env vars zijn ingesteld")
if not openai_key:
    raise Exception("OPENAI_API_KEY ontbreekt")

supabase = create_client(supabase_url, supabase_key)
openai   = OpenAI(api_key=openai_key)

# ─── 4) Data Models ─────────────────────────────────────────────────────
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

# ─── 5) Routes ──────────────────────────────────────────────────────────

@app.get("/env")
async def get_env():
    return {
        "supabase_url": supabase_url,
        "openai": (openai_key[:5] + "...") if openai_key else None,
    }

@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    try:
        result = supabase.table("versions") \
                         .select("html_live") \
                         .order("timestamp", desc=True) \
                         .limit(1) \
                         .execute()

        current_html = "<html><body><div>Welkom</div></body></html>"
        if result.data and isinstance(result.data, list) and "html_live" in result.data[0]:
            current_html = result.data[0]["html_live"]

        ai_prompt = f"""
Je bent een AI die HTML aanpast op basis van een gebruikersverzoek.
Geef alleen de **volledige aangepaste HTML** terug.

Huidige HTML:
{current_html}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""

        completion = openai.chat.completions.create(
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

    except Exception as e:
        print("ERROR in /prompt route:", str(e), file=sys.stderr)
        return {"error": "Er is iets misgegaan bij het verwerken van de prompt."}

@app.post("/publish")
async def publish_version(req: PublishRequest):
    try:
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

        return {"message": "Live versie gepubliceerd."}

    except Exception as e:
        print("ERROR in /publish route:", str(e), file=sys.stderr)
        return {"error": "Publicatie mislukt"}
