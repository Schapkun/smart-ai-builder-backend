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
    page_route: str = "index"  # default fallback

@app.post("/prompt")
async def handle_prompt(req: PromptRequest, request: Request):
    origin = request.headers.get("origin")
    print("🌐 Inkomend verzoek van origin:", origin, file=sys.stderr)

    try:
        # ⬇️ Laad huidige code uit het juiste bestand
        filename = f"preview_version/{req.page_route}.tsx"
        try:
            with open(filename, "r", encoding="utf-8") as f:
                current_code = f.read()
        except FileNotFoundError:
            current_code = ""
            print(f"⚠️ Bestand niet gevonden: {filename}", file=sys.stderr)

        system_message = {
            "role": "system",
            "content": (
                "Je bent een AI die codebestanden aanpast op basis van gebruikersinstructies.\n"
                "Hieronder zie je de huidige inhoud van het bestand:\n\n"
                f"{current_code}\n\n"
                "Als er een wijziging nodig is, retourneer dan een JSON array van objecten met 'path' en 'content'.\n"
                f"Gebruik exact dit pad voor het bestand: '{req.page_route}.tsx'\n"
                "Voorbeeld:\n"
                "[{\"path\": \"Home.tsx\", \"content\": \"...volledige nieuwe inhoud...\"}]\n"
                "Als er geen wijziging nodig is, geef dan alleen uitleg terug."
            )
        }

        messages = [system_message] + [
            {"role": msg.role, "content": msg.content} for msg in req.chat_history
        ] + [{"role": "user", "content": req.prompt}]

        # 🧠 AI aanroepen
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.3,
            )
            raw_content = response.choices[0].message.content.strip()
        except Exception as e:
            print("❌ ERROR code generatie:", str(e), file=sys.stderr)
            return JSONResponse(status_code=500, content={"error": "AI-output mislukt."})

        explanation = raw_content
        files = []
        has_changes = False

        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                files = parsed
                has_changes = True
                explanation = "Ik heb een wijziging voorbereid."
        except json.JSONDecodeError:
            pass  # AI gaf geen JSON, dus alleen uitleg

        timestamp = datetime.now(ZoneInfo("Europe/Amsterdam")).isoformat(timespec="microseconds")

        return {
            "version_timestamp": timestamp,
            "instructions": {
                "message": explanation,
                "generated_by": "AI v7",
                "files_changed": [f["path"] for f in files] if has_changes else [],
                "hasChanges": has_changes,
                "html": "" if not has_changes else None
            },
            "files": files if has_changes else []
        }

    except Exception as e:
        print("❌ Interne fout:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij promptverwerking."})


@app.post("/implement")
async def implement_changes(request: Request):
    try:
        payload = await request.json()
        files = payload.get("files", [])

        for file in files:
            path = file.get("path", "").strip()
            content = file.get("content", "")
            if not path or not content:
                continue

            from commit_to_github import commit_file_to_github
            commit_file_to_github(
                html_content=content,
                path=f"preview_version/{path}",
                commit_message=f"AI wijziging aan {path} via implementatie"
            )

        return {"status": "success", "message": "Wijzigingen zijn succesvol doorgevoerd."}

    except Exception as e:
        print("❌ Commit implementatie fout:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Implementatie mislukt."})
