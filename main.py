from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
import json
import logging
from openai import OpenAI
import requests

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

SUPABASE_URL = "https://rybezhoovslkutsugzvv.supabase.co"
SUPABASE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ5YmV6aG9vdnNsa3V0c3VnenZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTIyMzA0OCwiZXhwIjoyMDY0Nzk5MDQ4fQ.7cp-7vlUyIcgT15kS6wjE9ayopjXVZzLIB9E0d0_68Q"

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

def execute_supabase_instructions(instructions: str):
    try:
        parsed = json.loads(instructions)
        table = parsed.get("table")
        action = parsed.get("action")
        data = parsed.get("data", {})

        if not table or not action:
            return {"error": "Ongeldige instructies: ontbrekend 'table' of 'action'"}

        url = f"{SUPABASE_URL}/rest/v1/{table}"

        headers = {
            "apikey": SUPABASE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        if action == "insert":
            r = requests.post(url, headers=headers, json=data)
        elif action == "update":
            match = parsed.get("match", {})
            r = requests.patch(url, headers=headers, json=data, params=match)
        elif action == "delete":
            match = parsed.get("match", {})
            r = requests.delete(url, headers=headers, params=match)
        else:
            return {"error": f"Onbekende actie: {action}"}

        return r.json()
    except Exception as e:
        logging.error(f"Supabase instructie mislukt: {e}")
        return {"error": str(e)}

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

        execution_result = execute_supabase_instructions(supabase_instructions)

        return {
            "html": html,
            "supabase_instructions": supabase_instructions,
            "version_timestamp": datetime.utcnow().isoformat(),
            "execution_result": execution_result,
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

@app.post("/execute-supabase")
async def execute_supabase(data: SupabaseInstructionRequest):
    try:
        instructions = data.instructions
        logging.info(f"Supabase instructie ontvangen: {instructions}")
        result = execute_supabase_instructions(instructions)
        return {"message": "Instructies uitgevoerd.", "result": result}
    except Exception as e:
        logging.error(f"Fout bij supabase-instructie: {str(e)}")
        return {"message": "Fout bij uitvoeren", "error": str(e)}
