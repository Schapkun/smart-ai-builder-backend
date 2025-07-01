from fastapi import FastAPI, Request
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

class SupabaseInstructionRequest(BaseModel):
    instructions: str

def extract_between(text, start_tag, end_tag):
    try:
        return text.split(start_tag)[1].split(end_tag)[0].strip()
    except Exception as e:
        logging.warning(f"Extract failed: {e}")
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
                        "Je bent een frontend developer en Supabase-expert. "
                        "Je output is ALTIJD een JSON-object met twee velden: "
                        "`html` en `supabase_instructions`. "
                        "Gebruik GEEN markdown of backticks. GEEN extra tekst. Alleen geldige JSON als output."
                    )
                },
                {"role": "user", "content": data.prompt},
            ],
        )

        ai_output = response.choices[0].message.content.strip()
        logging.info(f"AI output: {ai_output}")

        if ai_output.startswith("```"):
            ai_output = ai_output.strip("`").replace("json", "").strip()

        try:
            ai_json = json.loads(ai_output)
            html = ai_json.get("html", "<div>Geen geldige HTML ontvangen.</div>")
            supabase_instructions = ai_json.get("supabase_instructions", "")
        except json.JSONDecodeError as decode_err:
            logging.warning(f"JSON decode error: {decode_err}")
            html = extract_between(ai_output, "<html>", "</html>") or "<div>HTML extractie mislukt</div>"
            supabase_instructions = extract_between(ai_output, "<supabase>", "</supabase>") or ""

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
