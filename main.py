from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client
from datetime import datetime
from zoneinfo import ZoneInfo
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

def validate_and_fix_html(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        return str(soup)
    except Exception as e:
        print(f"❌ HTML validatie fout: {e}", file=sys.stderr)
        return html

@app.post("/prompt")
async def handle_prompt(req: PromptRequest, request: Request):
    origin = request.headers.get("origin")
    print("🌐 Inkomend verzoek van origin:", origin, file=sys.stderr)

    try:
        fixed_route = "homepage"

        result = supabase.table("versions") \
            .select("html_preview", "html_live") \
            .eq("page_route", fixed_route) \
            .order("timestamp", desc=True) \
            .limit(1) \
            .execute()

        current_html = "<html><body><div>Welkom op de testpagina van Mike</div></body></html>"
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
                f"De gebruiker werkt aan pagina: {fixed_route}.\n"
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
            "Vat het verzoek van de gebruiker bondig samen in 1 zin, alsof je uitlegt wat je gaat doen.\n"
            "Zeg bijvoorbeeld: 'Ik ga de titel groen maken op de homepage'.\n"
            "Vermijd zinnen alsof je de wijziging al hebt gedaan.\n"
            "Geef GEEN HTML terug in dit antwoord."
        )

        print("📨 Verstuurde messages naar OpenAI (uitleg):", json.dumps(messages + [{"role": "system", "content": explanation_prompt}], indent=2), file=sys.stderr)

        explanation = ""
        try:
            explanation = openai.chat.completions.create(
                model="gpt-4",
                messages=messages + [{"role": "system", "content": explanation_prompt}],
                temperature=0.4,
            ).choices[0].message.content.strip()
            print("✅ AI uitleg gegenereerd:", explanation, file=sys.stderr)
        except Exception as e:
            print("❌ ERROR AI uitleg generatie:", str(e), file=sys.stderr)

        action_keywords = ["verander", "pas aan", "voeg toe", "verwijder", "zet", "maak", "stel in", "kleur", "toon"]
        html = None

        if any(k in req.prompt.lower() for k in action_keywords):
            html_prompt_text = (
                "Je krijgt hieronder de huidige volledige HTML.\n"
                "Pas deze HTML volledig aan volgens het gebruikersverzoek.\n"
                "Geef alleen de volledige nieuwe HTML terug, zonder uitleg of voorbeeldcode.\n\n"
                f"Huidige HTML:\n{current_html}\n\n"
                f"Gebruikersverzoek:\n{req.prompt}\n\n"
                "Nieuwe volledige HTML:\n"
            )

            print("📨 Verstuurde messages naar OpenAI (HTML):", json.dumps(messages + [{"role": "system", "content": html_prompt_text}], indent=2), file=sys.stderr)

            try:
                html = openai.chat.completions.create(
                    model="gpt-4",
                    messages=messages + [{"role": "system", "content": html_prompt_text}],
                    temperature=0,
                ).choices[0].message.content.strip()
                print("✅ AI HTML gegenereerd", file=sys.stderr)
            except Exception as e:
                print("❌ ERROR AI HTML generatie:", str(e), file=sys.stderr)

            html = validate_and_fix_html(html) if html else None

        timestamp = datetime.now(ZoneInfo("Europe/Amsterdam")).isoformat(timespec="microseconds")

        instructions = {
            "message": explanation,
            "generated_by": "AI v4"
        }

        return {
            "html": html,
            "version_timestamp": timestamp,
            "instructions": instructions
        }

    except Exception as e:
        print("❌ ERROR in /prompt route:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij verwerken prompt."})

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

@app.post("/init")
async def init_html(req: InitRequest):
    try:
        html = validate_and_fix_html(req.html)
        timestamp = datetime.now(ZoneInfo("Europe/Amsterdam")).isoformat(timespec="microseconds")
        supabase.table("versions").insert({
            "prompt": "init",
            "html_preview": html,
            "page_route": "homepage",
            "timestamp": timestamp,
            "supabase_instructions": json.dumps({"message": "Initiale HTML toegevoegd"}),
        }).execute()
        return {"message": "HTML preview succesvol opgeslagen als startpunt."}
    except Exception as e:
        print("❌ ERROR in /init:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Initialisatie mislukt"})

@app.get("/preview/{page_route}")
async def get_html_preview(page_route: str):
    try:
        fixed_route = "homepage"
        result = supabase.table("versions") \
                         .select("html_preview") \
                         .eq("page_route", fixed_route) \
                         .order("timestamp", desc=True) \
                         .limit(1) \
                         .execute()

        if not result.data or not result.data[0].get("html_preview"):
            return JSONResponse(status_code=404, content={"error": "Geen preview-versie gevonden."})

        return {"html": result.data[0]["html_preview"]}
    except Exception as e:
        print("❌ ERROR in /preview route:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij ophalen preview."})

@app.post("/clone-live-to-preview")
async def clone_live_to_preview():
    try:
        fixed_route = "homepage"

        result = supabase.table("versions") \
            .select("html_live") \
            .eq("page_route", fixed_route) \
            .order("timestamp", desc=True) \
            .limit(1) \
            .execute()

        if not result.data or not result.data[0].get("html_live"):
            return JSONResponse(status_code=404, content={"error": "Geen live versie gevonden."})

        html_live = result.data[0]["html_live"]

        timestamp = datetime.now(ZoneInfo("Europe/Amsterdam")).isoformat(timespec="microseconds")

        supabase.table("versions").insert({
            "prompt": "Live naar preview gekopieerd",
            "html_preview": html_live,
            "page_route": fixed_route,
            "timestamp": timestamp,
            "supabase_instructions": json.dumps({"message": "Gekopieerd vanaf live versie"}),
        }).execute()

        return {"message": "Live versie succesvol gekopieerd naar preview."}
    except Exception as e:
        print("❌ ERROR in /clone-live-to-preview:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Kopie mislukt."})
