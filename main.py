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

# import commit util (handles GH_PAT internally)
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

# OpenAI key
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
    page_route: str = "homepage"

@app.post("/prompt")
async def handle_prompt(req: PromptRequest, request: Request):
    origin = request.headers.get("origin")
    print("🌐 Inkomend verzoek van origin:", origin, file=sys.stderr)

    try:
        system_message = {
            "role": "system",
            "content": (
                "Je bent een AI die gebruikers helpt met uitleg en codewijzigingen."
                " Indien er code gewijzigd moet worden, geef dan een geldige JSON array terug met objecten met 'path' en 'content'."
                " Als er geen wijzigingen nodig zijn, retourneer alleen uitleg zonder JSON-structuur."
                f" Het relevante bestand voor deze prompt is: {req.page_route}"
            )
        }

        messages = [system_message] + [
            {"role": msg.role, "content": msg.content} for msg in req.chat_history
        ] + [{"role": "user", "content": req.prompt}]

        # Genereer AI antwoord met detectie van wijzigingen
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()

        explanation = raw
        files = []
        has_changes = False
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                files = parsed
                has_changes = True
                explanation = "Ik heb een wijziging voorbereid."
        except json.JSONDecodeError:
            # gewoon uitleg
            pass

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
            "files": files if has_changes else [],
            "page_route": req.page_route
        }

    except Exception as e:
        print("❌ Interne fout:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij promptverwerking."})

@app.post("/implement")
async def implement_changes(request: Request):
    try:
        payload = await request.json()
        files = payload.get("files", [])

        # Commit util haalt GH_PAT zelf op
        for file in files:
            path = file.get("path", "").strip()
            content = file.get("content", "")
            if not path or not content:
                continue
            try:
                commit_file_to_github(
                    html_content=content,
                    path=f"preview_version/{path}",
                    commit_message=f"AI wijziging aan {path} via implementatie"
                )
            except Exception as e:
                print(f"❌ Commit mislukt voor {path}:", str(e), file=sys.stderr)
                return JSONResponse(status_code=500, content={"error": f"Implementatie mislukt voor {path}"})

        return {"status": "success", "message": "Wijzigingen succesvol doorgevoerd."}
    except Exception as e:
        print("❌ Commit implementatie fout:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Implementatie mislukt."})
