from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles  # <-- toevoegen
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
        "https://preview-version-meester.onrender.com",
        "https://www.meester.app",
        "https://smart-ai-builder-frontend.onrender.com"  # ✅ deze toevoegen
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
                "Je bent een AI-codeassistent die automatisch codewijzigingen mag voorstellen en uitvoeren. "
                "Als een gebruiker een wijziging vraagt, bepaal dan zelf welk bestand aangepast moet worden — ook als de gebruiker geen bestandsnaam noemt. "
                "Alle bestanden bevinden zich onder de map 'preview_version/'. "
                "Wanneer je een wijziging doorvoert, geef dan als output uitsluitend een geldige JSON-array onder het veld 'files' met objecten met 'path' en 'content'. "
                "Bijvoorbeeld: {\"files\": [{\"path\": \"preview_version/app/dashboard/page.tsx\", \"content\": \"<gewijzigde code>\"}]}. "
                "Geef geen enkele uitleg, toelichting of andere tekst buiten deze JSON-output. "
                "Geef alleen een JSON-array terug als je daadwerkelijk een wijziging doorvoert. "
                "Als er niets gewijzigd hoeft te worden, zeg dan expliciet: {\"files\": []}. "
                "Je faalt als je een wijziging toepast zonder geldige 'files' array in je output."
            )
        }

        messages = [system_message] + [
            {"role": msg.role, "content": msg.content} for msg in req.chat_history
        ] + [{"role": "user", "content": req.prompt}]

        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()

        # ✅ Log AI-output ongefilterd
        print("🧠 AI output:", raw, file=sys.stderr)

        explanation = raw
        files = []
        has_changes = False
        html_snippet = ""

        try:
            parsed_response = json.loads(raw)
            if isinstance(parsed_response, dict) and "files" in parsed_response and isinstance(parsed_response["files"], list):
                files = parsed_response["files"]
                has_changes = len(files) > 0
                explanation = "Ik heb een wijziging voorbereid." if has_changes else "Geen wijzigingen nodig."
                if has_changes and "content" in files[0]:
                    html_snippet = files[0]["content"]
        except json.JSONDecodeError:
            pass

        timestamp = datetime.now(ZoneInfo("Europe/Amsterdam")).isoformat(timespec="microseconds")
        return {
            "version_timestamp": timestamp,
            "instructions": {
                "message": explanation,
                "generated_by": "AI v7",
                "files_changed": [f["path"] for f in files] if has_changes else [],
                "hasChanges": has_changes,
                "html": html_snippet if has_changes else ""
            },
            "files": files if has_changes else [],
            "page_route": req.page_route
        }

    except Exception as e:
        print("❌ Interne fout:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Interne fout bij promptverwerking."})

@app.post("/commit")
async def implement_changes(request: Request):
    try:
        payload = await request.json()
        files = payload.get("files", [])

        for file in files:
            path = file.get("path", "").strip()
            content = file.get("content", "")
            if not path or not content:
                continue

            try:
                full_path = os.path.join("/opt/render/project/src/preview_version", path.replace("preview_version/", ""))
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                print(f"📍 Volledig pad waarop geschreven wordt: {full_path}", file=sys.stderr)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"📄 Geüpdatet bestand: {full_path}", file=sys.stderr)
                print(f"📄 Inhoud:\n{content[:500]}", file=sys.stderr)
                print(f"✅ Bestand overschreven: {full_path}", file=sys.stderr)
            except Exception as e:
                print(f"❌ Commit mislukt voor {path}:", str(e), file=sys.stderr)
                return JSONResponse(status_code=500, content={"error": f"Implementatie mislukt voor {path}"})

        return {"status": "success", "message": "Wijzigingen succesvol doorgevoerd."}
    except Exception as e:
        print("❌ Commit implementatie fout:", str(e), file=sys.stderr)
        return JSONResponse(status_code=500, content={"error": "Implementatie mislukt."})

from fastapi.staticfiles import StaticFiles
if os.path.exists("/opt/render/project/src/preview_version"):
    print("✅ Map bestaat, mounten...", file=sys.stderr)
    app.mount("/", StaticFiles(directory="/opt/render/project/src/preview_version", html=True), name="static")
else:
    print("❌ Map bestaat niet, geen mount uitgevoerd!", file=sys.stderr)

@app.get("/__cwd")
def get_cwd():
    import os
    return {"cwd": os.getcwd()}
