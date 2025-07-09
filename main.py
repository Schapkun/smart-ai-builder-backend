from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import OpenAI
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import sys
import json
from commit_to_github import commit_file_to_github

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

openai_key = os.getenv("OPENAI_API_KEY")
if not openai_key:
    raise Exception("OPENAI_API_KEY ontbreekt")

openai = OpenAI(api_key=openai_key)
print("✅ OPENAI_API_KEY:", (openai_key[:5] + "..."), file=sys.stderr)

class Message(BaseModel):
    role: str
    content: str

class PromptRequest(BaseModel):
    prompt: str
    chat_history: list[Message]

@app.post("/prompt")
async def handle_prompt(req: PromptRequest, request: Request):
    origin = request.headers.get("origin")
    print("🌐 Inkomend verzoek van origin:", origin, file=sys.stderr)

    try:
        system_message = {
            "role": "system",
            "content": (
                "Je bent een AI die bestaande frontendbestanden in een project aanpast op basis van gebruikersinstructies.\n"
                "Je retourneert een array van objecten met 'path' en 'content'. Elke entry is een volledig bestand.\n"
                "Voorbeeld:\n"
                "[\n"
                "  {\"path\": \"components/Header.tsx\", \"content\": \"...volledige nieuwe inhoud...\"},\n"
                "  {\"path\": \"pages/About.tsx\", \"content\": \"...\"}\n"
                "]\n"
                "Voeg GEEN uitleg of tekst toe buiten de JSON.\n"
                "Alle paden zijn relatief aan de map preview_version/"
            )
        }

        messages = [system_message] + [
            {"role": msg.role, "content": msg.content} for msg in req.chat_history
        ] + [{"role": "user", "content": req.prompt}]

        # 🔍 Verkorte uitleg ophalen
        explanation = ""
        try:
            explanation_resp = openai.chat.completions.create(
                model="gpt-4",
                messages=messages + [{"role": "user", "content": "Vat in 1 zin samen wat je hebt gedaan."}],
                temperature=0.4,
            )
            explanation = explanation_resp.choices[0].message.content.strip()
        except Exception as e:
            print("❌ ERROR uitleg:", str(e), file=sys.stderr)

        # 🧠 Code ophalen
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.3,
            )
            content_raw = response.choices[0].message.content.strip()
        except Exception as e:
            print("❌ ERROR code generatie:", str(e), file=sys.stderr)
            return JSONResponse(status_code=500, content={"error": "AI-output mislukt."})

        if not content_raw:
            return JSONResponse(status_code=400, content={"error": "AI gaf geen inhoud terug."})

        try:
            files = json.loads(content_raw)
            assert isinstance(files, list)
        except Exception as e:
            print("❌ AI-output is geen geldige JSON lijst:", str(e), file=sys.stderr)
            return JSONResponse(status_code=400, content={"error": "AI gaf geen geldige JSON-array terug."})

        for file in files:
            path = file.get("path", "").strip()
            content = file.get("content", "")
            if not path or not content:
                continue

            try:
                commit_file_to_github(
                    html_content=content,
                    path=f"preview_version/{path}",
                    commit_message=f"AI wijziging aan {path} via prompt"
                )
            except Exception as e:
                print(f"❌ Commit mislukt voor {path}:", str(e), file=sys.stderr)
                return JSONResponse(status_code=500, content={"error": f"Fout bij commit: {path}"})

        timestamp = datetime.now(ZoneInfo("Europe/Amsterdam")).isoformat(timespec="microseconds")

        return {
            "version_timestamp": timestamp,
            "instructions": {
                "message": explanation,
                "generated_by": "AI v6",
                "files_changed": [file["path"] for file in files if "path" in file]
            }
        }

    except Exception as e:
        print("❌ Interne fout:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij promptverwerking."})
