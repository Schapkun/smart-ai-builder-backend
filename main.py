# File: main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client
from datetime import datetime, timezone
import os
import sys
import json

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
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE")
openai_key   = os.getenv("OPENAI_API_KEY")

if not supabase_url or not supabase_key:
    raise Exception("SUPABASE_URL en SUPABASE_SERVICE_ROLE moeten zijn ingesteld")
if not openai_key:
    raise Exception("OPENAI_API_KEY ontbreekt")

supabase = create_client(supabase_url, supabase_key)
openai   = OpenAI(api_key=openai_key)

print("✅ SUPABASE_URL:", supabase_url, file=sys.stderr)
print("✅ OPENAI_API_KEY:", (openai_key[:5] + "..."), file=sys.stderr)

# ─── 4) Models ──────────────────────────────────────────────────────────
class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    version_id: str

# ─── 5) Routes ──────────────────────────────────────────────────────────

@app.get("/env")
async def get_env():
    return {
        "supabase_url": supabase_url,
        "openai_key_start": (openai_key[:5] + "..."),
    }

@app.post("/prompt")
async def handle_prompt(req: PromptRequest, request: Request):
    origin = request.headers.get("origin")
    print("🌐 Inkomend verzoek van origin:", origin, file=sys.stderr)

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
Je bent een AI die bestaande HTML aanpast op basis van een gebruikersverzoek.
Geef alleen de volledige aangepaste HTML terug.

Huidige HTML:
{current_html}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""

        completion = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": ai_prompt}],
            temperature=0
        )

        html = completion.choices[0].message.content.strip()
        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")

        instructions = {
            "modification_summary": f"HTML aangepast op basis van prompt: '{req.prompt}'",
            "generated_by": "AI v1",
        }

        supabase.table("versions").insert({
            "prompt": req.prompt,
            "html_preview": html,
            "html_live": current_html,
            "timestamp": timestamp,
            "supabase_instructions": json.dumps(instructions),
        }).execute()

        return {
            "html": html,
            "version_timestamp": timestamp,
            "supabase_instructions": json.dumps(instructions),
        }

    except Exception as e:
        print("❌ ERROR in /prompt:", str(e), file=sys.stderr)
        return {"error": "Interne fout bij verwerken prompt."}

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

        return {"message": "Live versie succesvol gepubliceerd."}

    except Exception as e:
        print("❌ ERROR in /publish:", str(e), file=sys.stderr)
        return {"error": "Publicatie mislukt"}
