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
from commit_to_github import commit_file_to_github  # ✅ aangepast om gebruik te maken van env key

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
    file_path: str
    chat_history: list[Message]

@app.post("/prompt")
async def handle_prompt(req: PromptRequest, request: Request):
    origin = request.headers.get("origin")
    print("🌐 Inkomend verzoek van origin:", origin, file=sys.stderr)

    try:
        file_path = req.file_path.strip()
        if not file_path:
            return JSONResponse(status_code=400, content={"error": "Geen bestandsnaam opgegeven."})

        # ✅ Systemprompt voor volledige bestandsgeneratie
        system_message = {
            "role": "system",
            "content": (
                f"Je bent een AI-assistent die volledige bestanden genereert of aanpast op basis van gebruikersinstructies.\n"
                f"Je krijgt een bestaand bestand te zien (in zijn geheel) en een verzoek tot wijziging.\n"
                f"Geef ALTIJD het volledige gewijzigde bestand terug.\n"
                f"Voeg GEEN uitleg, voorbeelden of fragmenten toe."
            )
        }

        messages = [system_message] + [
            {"role": msg.role, "content": msg.content} for msg in req.chat_history
        ] + [{"role": "user", "content": req.prompt}]

        explanation = ""
        try:
            explanation = openai.chat.completions.create(
                model="gpt-4",
                messages=messages + [{"role": "system", "content": "Vat in 1 zin samen wat je gaat doen. Geen uitleg, geen HTML."}],
                temperature=0.4,
            ).choices[0].message.content.strip()
        except Exception as e:
            print("❌ ERROR AI uitleg generatie:", str(e), file=sys.stderr)

        generated_code = ""
        try:
            generated_code = openai.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.3,
            ).choices[0].message.content.strip()
        except Exception as e:
            print("❌ ERROR AI code generatie:", str(e), file=sys.stderr)
            return JSONResponse(status_code=500, content={"error": "AI gegenereerde code mislukt."})

        # ✅ Wegschrijven naar GitHub
        try:
            commit_file_to_github(
                html_content=generated_code,
                path=f"preview_version/{file_path}",
                commit_message=f"AI update aan {file_path} via preview versie"
            )
        except Exception as e:
            print("❌ Fout bij commit naar GitHub:", str(e), file=sys.stderr)
            return JSONResponse(status_code=500, content={"error": "GitHub commit mislukt."})

        timestamp = datetime.now(ZoneInfo("Europe/Amsterdam")).isoformat(timespec="microseconds")

        return {
            "file_path": file_path,
            "version_timestamp": timestamp,
            "instructions": {
                "message": explanation,
                "generated_by": "AI v5"
            }
        }

    except Exception as e:
        print("❌ ERROR in /prompt route:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij verwerken prompt."})
