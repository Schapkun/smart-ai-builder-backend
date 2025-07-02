from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client
from datetime import datetime, timezone
import os
import sys
import json
from bs4 import BeautifulSoup

app = FastAPI()

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

# ✅ ENVIRONMENT VARS
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE")
openai_key = os.getenv("OPENAI_API_KEY")

if not supabase_url or not supabase_key:
    raise Exception("SUPABASE_URL en SUPABASE_SERVICE_ROLE moeten zijn ingesteld")
if not openai_key:
    raise Exception("OPENAI_API_KEY ontbreekt")

supabase = create_client(supabase_url, supabase_key)
openai = OpenAI(api_key=openai_key)

print("✅ SUPABASE_URL:", supabase_url, file=sys.stderr)
print("✅ OPENAI_API_KEY:", (openai_key[:5] + "..."), file=sys.stderr)


# ✅ STRUCTURE
class Message(BaseModel):
    role: str
    content: str

class PromptRequest(BaseModel):
    prompt: str
    page_route: str
    chat_history: list[Message]

class PublishRequest(BaseModel):
    version_id: str

class InitRequest(BaseModel):
    html: str
    page_route: str


# ✅ HELPER
def validate_and_fix_html(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        return str(soup)
    except Exception as e:
        print(f"❌ HTML validatie fout: {e}", file=sys.stderr)
        return html


# ✅ POST /prompt
@app.post("/prompt")
async def handle_prompt(req: PromptRequest, request: Request):
    origin = request.headers.get("origin")
    print("🌐 Inkomend verzoek van origin:", origin, file=sys.stderr)

    try:
        result = supabase.table("versions") \
            .select("html_preview", "html_live") \
            .eq("page_route", req.page_route) \
            .order("timestamp", desc=True) \
            .limit(1) \
            .execute()

        current_html = "<html><body><div>Welkom</div></body></html>"
        if result.data and isinstance(result.data, list):
            latest = result.data[0]
            if latest.get("html_preview"):
                current_html = latest["html_preview"]
            elif latest.get("html_live"):
                current_html = latest["html_live"]

        system_message = {
            "role": "system",
            "content": (
                f"Je bent een AI-assistent die helpt met het aanpassen van HTML voor een website.\n"
                f"De gebruiker werkt aan pagina: {req.page_route}.\n"
                f"De huidige HTML van die pagina is:\n{current_html}\n"
                f"Wanneer je een wijziging uitvoert, geef dan alleen de volledige aangepaste HTML terug, zonder uitleg of voorbeeldcode.\n"
                f"Geef geen gedeeltelijke HTML of codefragmenten, alleen de volledige HTML.\n"
                f"Als het een vraag of advies is, geef dan alleen een vriendelijk antwoord zonder HTML."
            )
        }

        messages = [system_message] + [
            {"role": msg.role, "content": msg.content} for msg in req.chat_history
        ] + [{"role": "user", "content": req.prompt}]

        explanation_prompt = (
            "Beantwoord vriendelijk en duidelijk.\n"
            "Als het een wijziging betreft, geef in 1 zin aan wat er is aangepast."
        )

        explanation = openai.chat.completions.create(
            model="gpt-4",
            messages=messages + [{"role": "system", "content": explanation_prompt}],
            temperature=0.4,
        ).choices[0].message.content.strip()

        action_keywords = ["verander", "pas aan", "voeg toe", "verwijder", "zet", "maak", "stel in", "kleur", "toon"]
        if any(k in req.prompt.lower() for k in action_keywords):
            html_prompt_text = (
                "Je krijgt hieronder de huidige volledige HTML.\n"
                "Pas deze HTML volledig aan volgens het gebruikersverzoek.\n"
                "Geef alleen de volledige nieuwe HTML terug, zonder uitleg of voorbeeldcode.\n\n"
                f"Huidige HTML:\n{current_html}\n\n"
                f"Gebruikersverzoek:\n{req.prompt}\n\n"
                "Nieuwe volledige HTML:\n"
            )

            html = openai.chat.completions.create(
                model="gpt-4",
                messages=messages + [{"role": "system", "content": html_prompt_text}],
                temperature=0,
            ).choices[0].message.content.strip()

            html = validate_and_fix_html(html)
        else:
            html = None

        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        instructions = {
            "message": explanation,
            "generated_by": "AI v3"
        }

        if html:
            supabase.table("versions").insert({
                "prompt": req.prompt,
                "html_preview": html,
                "page_route": req.page_route,
                "timestamp": timestamp,
                "supabase_instructions": json.dumps(instructions),
            }).execute()
        else:
            print("ℹ️ Geen nieuwe HTML gegenereerd, geen versie opgeslagen.")

        return {
            "html": html,
            "version_timestamp": timestamp,
            "instructions": instructions
        }

    except Exception as e:
        print("❌ ERROR in /prompt route:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij verwerken prompt."})


# ✅ POST /publish
@app.post("/publish")
async def publish_version(req: PublishRequest):
    try:
        version = supabase.table("versions") \
            .select("html_preview") \
            .eq("id", req.version_id) \
            .single() \
            .execute()

        if not version.data:
            return JSONResponse(status_code=404, content={"error": "Versie niet gevonden"})

        html_to_publish = version.data["html_preview"]

        supabase.table("versions") \
            .update({"html_live": html_to_publish}) \
            .eq("id", req.version_id) \
            .execute()

        return {"message": "Live versie succesvol gepubliceerd."}

    except Exception as e:
        print("❌ ERROR in /publish:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Publicatie mislukt"})


# ✅ POST /init
@app.post("/init")
async def init_html(req: InitRequest):
    try:
        html = validate_and_fix_html(req.html)
        timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        supabase.table("versions").insert({
            "prompt": "init",
            "html_preview": html,
            "page_route": req.page_route,
            "timestamp": timestamp,
            "supabase_instructions": json.dumps({"message": "Initiale HTML toegevoegd"}),
        }).execute()
        return {"message": "HTML preview succesvol opgeslagen als startpunt."}
    except Exception as e:
        print("❌ ERROR in /init:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Initialisatie mislukt"})


# ✅ GET /preview/{page_route}
@app.get("/preview/{page_route}")
async def get_html_preview(page_route: str):
    try:
        result = supabase.table("versions") \
                         .select("html_preview") \
                         .eq("page_route", page_route) \
                         .order("timestamp", desc=True) \
                         .limit(1) \
                         .execute()

        if not result.data or not result.data[0].get("html_preview"):
            return JSONResponse(status_code=404, content={"error": "Geen preview-versie gevonden."})

        return {"html": result.data[0]["html_preview"]}

    except Exception as e:
        print("❌ ERROR in /preview route:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij ophalen preview."})
