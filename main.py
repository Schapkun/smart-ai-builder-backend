from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import os
from datetime import datetime
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str

def extract_between(text, start_tag, end_tag):
    try:
        return text.split(start_tag)[1].split(end_tag)[0].strip()
    except:
        return ""

@app.post("/prompt")
async def run_prompt(data: PromptRequest):
    openai.api_key = os.getenv("OPENAI_API_KEY")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Je genereert HTML/JS wijzigingen en Supabase database-aanpassingen "
                        "op basis van natuurlijke taal. Geef output als JSON met: html, supabase_instructions."
                    )
                },
                {"role": "user", "content": data.prompt}
            ]
        )

        ai_output = response.choices[0].message.content

        # Probeer JSON uit AI-output te parsen
        try:
            ai_json = json.loads(ai_output)
            html = ai_json.get("html", "<div>Geen HTML ontvangen</div>")
            supabase_instructions = ai_json.get("supabase_instructions", "")
        except json.JSONDecodeError:
            # Fallback: probeer oude extract_between methode
            html = extract_between(ai_output, "<html>", "</html>")
            supabase_instructions = extract_between(ai_output, "<supabase>", "</supabase>")

        return {
            "html": html,
            "supabase_instructions": supabase_instructions,
            "version_timestamp": datetime.utcnow().isoformat(),
            "raw_output": ai_output
        }

    except Exception as e:
        return {
            "error": str(e),
            "html": "<div style='color:red'>Fout bij AI-aanroep</div>",
            "supabase_instructions": "",
            "version_timestamp": datetime.utcnow().isoformat()
        }
