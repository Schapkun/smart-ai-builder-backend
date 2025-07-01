from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
import openai
import requests

app = FastAPI()

# Allow frontend to access this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

class PromptRequest(BaseModel):
    prompt: str

@app.post("/prompt")
async def handle_prompt(request: PromptRequest):
    try:
        # Step 1: Generate HTML preview from prompt
        system_prompt = (
            "You are a senior frontend developer. Respond ONLY with clean HTML and inline CSS. "
            "DO NOT include code fences (like ```html)."
        )
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            temperature=0.2
        )
        html_preview = response['choices'][0]['message']['content']

        # Step 2: Generate Supabase instruction from prompt
        instruction_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in database design. Based on this prompt, generate a JSON Supabase instruction, for example: {\"action\": \"create_table\", \"table\": \"users\", \"columns\": [{\"name\": \"id\", \"type\": \"uuid\"}, ...]}"},
                {"role": "user", "content": request.prompt}
            ],
            temperature=0.2
        )
        supabase_instructions = instruction_response['choices'][0]['message']['content']

        # Step 3: Store in Supabase
        payload = {
            "prompt": request.prompt,
            "html_preview": html_preview,
            "timestamp": datetime.utcnow().isoformat(),
            "supabase_instructions": supabase_instructions
        }

        headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/versions",
            headers=headers,
            json=payload
        )

        if not response.ok:
            return {"error": "Supabase insert failed", "details": response.text}

        return {
            "html_preview": html_preview,
            "supabase_instructions": supabase_instructions
        }

    except Exception as e:
        return {"error": str(e)}
