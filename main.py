
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import os
from datetime import datetime

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

@app.post("/prompt")
async def run_prompt(data: PromptRequest):
    openai.api_key = os.getenv("OPENAI_API_KEY")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "Je genereert HTML/JS wijzigingen en Supabase database-aanpassingen op basis van natuurlijke taal. "
                               "Geef output als JSON met: html, supabase_instructions, version_timestamp."
                },
                { "role": "user", "content": data.prompt }
            ]
        )

        ai_output = response.choices[0].message.content

        return {
            "html": extract_between(ai_output, "<html>", "</html>"),
            "supabase_instructions": extract_between(ai_output, "<supabase>", "</supabase>"),
            "version_timestamp": datetime.utcnow().isoformat(),
            "raw_output": ai_output
        }

    except Exception as e:
        return {
            "error": str(e),
            "html": "<div>Fout bij AI-aanroep</div>",
            "supabase_instructions": "",
            "version_timestamp": datetime.utcnow().isoformat()
        }

def extract_between(text, start_tag, end_tag):
    try:
        return text.split(start_tag)[1].split(end_tag)[0].strip()
    except:
        return ""
