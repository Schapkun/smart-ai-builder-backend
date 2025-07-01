from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import json
import logging
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# CORS-instellingen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI-client
client = OpenAI()

# Request-model
class PromptRequest(BaseModel):
    prompt: str

# Fallback: extractie tussen tags bij JSON-fouten
def extract_between(text, start_tag, end_tag):
    try:
        return text.split(start_tag)[1].split(end_tag)[0].strip()
    except Exception as e:
        logging.warning(f"Extractie mislukt: {e}")
        return ""

# Endpoint
@app.post("/prompt")
async def run_prompt(data: PromptRequest):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Je bent een frontend developer en Supabase-expert. "
                        "Je output is ALTIJD een JSON-object met twee velden: "
                        "`html` en `supabase_instructions`. "
                        "Gebruik GEEN markdown, GEEN backticks, GEEN uitleg. Alleen geldige JSON als output."
                    )
                },
                {"role": "user", "content": data.prompt},
            ],
        )

        ai_output = response.choices[0].message.content.strip()
        logging.info(f"AI output:\n{ai_output}")

        # Strip eventueel ```json of ``` terugval
        if ai_output.startswith("```"):
            ai_output = ai_output.strip("`").replace("json", "").strip()

        try:
            # Probeer te parsen als JSON
            ai_json = json.loads(ai_output)
            html = ai_json.get("html", "<div>Geen geldige HTML ontvangen.</div>")
            supabase_instructions = ai_json.get("supabase_instructions", "")
        except json.JSONDecodeError as e:
            logging.warning(f"JSON decode error: {e}")
            html = extract_between(ai_output, "<html>", "</html>") or "<div>HTML extractie mislukt</div>"
            supabase_instructions = extract_between(ai_output, "<supabase>", "</supabase>") or ""

        return {
            "html": html,
            "supabase_instructions": supabase_instructions,
            "version_timestamp": datetime.utcnow().isoformat(),
            "raw_output": ai_output,
        }

    except Exception as e:
        logging.error(f"OpenAI fout: {str(e)}")
        return {
            "error": str(e),
            "html": f"<div style='color:red'>Fout bij AI-aanroep: {str(e)}</div>",
            "supabase_instructions": "",
            "version_timestamp": datetime.utcnow().isoformat(),
        }
