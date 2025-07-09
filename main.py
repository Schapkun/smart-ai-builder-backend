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
import requests
import base64

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

github_token = os.getenv("GH_PAT")
if not github_token:
    raise Exception("GH_PAT ontbreekt")

REPO = "Schapkun/agent-action-atlas"
BRANCH = "main"

class Message(BaseModel):
    role: str
    content: str

class PromptRequest(BaseModel):
    prompt: str
    chat_history: list[Message]
    page_route: str = "homepage"

@app.post("/prompt")
async def handle_prompt(req: PromptRequest, request: Request):
    origin = request.headers.get("origin")
    print("🌐 Inkomend verzoek van origin:", origin, file=sys.stderr)

    try:
        # 🧾 Stap 1: lees huidige bestand van GitHub
        path = f"preview_version/{req.page_route}.tsx"
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }
        file_url = f"https://api.github.com/repos/{REPO}/contents/{path}"
        file_response = requests.get(file_url, headers=headers)
        if file_response.status_code != 200:
            print(f"⚠️ Bestand niet gevonden: {path}", file=sys.stderr)
            return JSONResponse(status_code=404, content={"error": "Bestand niet gevonden", "path": path})

        file_data = file_response.json()
        file_content = base64.b64decode(file_data["content"]).decode("utf-8")
        sha = file_data["sha"]

        # 🧠 Stap 2: prompt genereren op basis van bestaande code
        system_message = {
            "role": "system",
            "content": (
                f"Je bent een AI die gebruikers helpt met uitleg en codewijzigingen."
                f" Hier is de huidige inhoud van het bestand {path}:\n\n{file_content}\n\n"
                "Indien de gebruiker vraagt om een wijziging, geef dan een geldige JSON array terug zoals:"
                '[{"path": "preview_version/homepage.tsx", "content": "nieuwebestandinhoud"}].'
                " Als er geen wijziging nodig is, geef dan alleen uitleg terug."
            )
        }

        messages = [system_message] + [
            {"role": msg.role, "content": msg.content} for msg in req.chat_history
        ] + [{"role": "user", "content": req.prompt}]

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
            pass

        timestamp = datetime.now(ZoneInfo("Europe/Amsterdam")).isoformat(timespec="microseconds")

        return {
            "version_timestamp": timestamp,
            "instructions": {
                "message": explanation,
                "generated_by": "AI v8",
                "files_changed": [f["path"] for f in files] if has_changes else [],
                "hasChanges": has_changes,
                "html": "" if not has_changes else None
            },
            "files": files if has_changes else [],
            "page_route": req.page_route,
            "sha": sha
        }

    except Exception as e:
        print("❌ Interne fout:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": str(e)})
