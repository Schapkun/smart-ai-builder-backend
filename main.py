from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
import json
import logging

from openai import OpenAI

logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI()

class PromptRequest(BaseModel):
    prompt: str

def extract_between(text, start_tag, end_tag):
    try:
        return text.split(start_tag)[1].split(end_tag)[0].strip()
    except:
        return ""

@app.post("/prompt")
async def run_prompt(data: PromptRequest):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Je bent een expert frontend developer en Supabase specialist. "
                        "Je genereert altijd een JSON-object met twee velden: "
                        "`html` en `supabase_instructions`. "
                        "Het veld `html` bevat volledige, geldige HTML-code die gebruikt kan worden als frontend output. "
                        "Het veld `supabase_instructions` bevat de benodigde Supabase database-aanpassingen in tekstvorm. "
                        "Antwoord alleen met de JSON-string, zonder enige extra tekst."
                    )
                },
                {"role": "user", "content": data.prompt},
            ],
        )

        ai_output = response.choices[0].message.content
        print("AI output:", ai_output)  # Log AI output voor debugging

        try:
            ai_json = json.loads(ai_output)
            html = ai_json.get("html", "<div>Geen HTML ontvangen</div>")
            supabase_instructions = ai_json.get("supabase_instructions", "")
        except json.JSONDecodeError:
            html = extract_between(ai_output, "<html>", "</html>")
            supabase_instructions = extract_between(ai_output, "<supabase>", "</supabase>")

        return {
            "html": html,
            "supabase_instructions": supabase_instructions,
            "version_timestamp": datetime.utcnow().isoformat(),
            "raw_output": ai_output,
        }

    except Exception as e:
        logging.error(f"OpenAI error: {str(e)}")
        return {
            "error": str(e),
            "html": f"<div style='color:red'>Fout bij AI-aanroep: {str(e)}</div>",
            "supabase_instructions": "",
            "version_timestamp": datetime.utcnow().isoformat(),
        }
