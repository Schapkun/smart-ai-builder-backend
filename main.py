# ✅ BACKEND: main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import openai
from openai import OpenAI
import supabase

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase_client = supabase.create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE")
)

class PromptRequest(BaseModel):
    prompt: str

class PublishRequest(BaseModel):
    timestamp: str

current_html_live = """
<!DOCTYPE html>
<html>
<head>
  <title>Meester.app</title>
</head>
<body>
  <div id="main">Welkom bij Meester.app</div>
  <footer>Meester.app v1.0</footer>
</body>
</html>
"""

@app.post("/prompt")
async def handle_prompt(req: PromptRequest):
    ai_prompt = f"""
Je bent een AI die bestaande HTML aanpast op basis van een gebruikersvraag.
Geef alleen de volledige aangepaste HTML terug.

Huidige HTML:
{current_html_live}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""

    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": ai_prompt}],
        temperature=0
    )

    html = completion.choices[0].message.content.strip()

    timestamp = str(os.times().elapsed)

    supabase_client.table("versions").insert({
        "prompt": req.prompt,
        "html_preview": html,
        "timestamp": timestamp
    }).execute()

    return {
        "html_preview": html,
        "timestamp": timestamp
    }

@app.post("/publish")
async def publish_html(req: PublishRequest):
    row = supabase_client.table("versions").select("html_preview").eq("timestamp", req.timestamp).single().execute()
    html = row.data.get("html_preview")
    
    supabase_client.table("versions").update({"html_live": html}).eq("timestamp", req.timestamp).execute()
    return {"message": "Live-versie bijgewerkt."}
