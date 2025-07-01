from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import openai
import os
from datetime import datetime

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# In-memory HTML (optioneel later vervangen door DB)
current_html = """<div class='content'>
  <footer style='text-align: left;'>Meester.app v1.0</footer>
</div>"""

# Prompt input
class PromptRequest(BaseModel):
    prompt: str

# Execute Supabase-instructies (voor later)
class SupabaseRequest(BaseModel):
    instructions: str

@app.post("/prompt")
async def process_prompt(req: PromptRequest):
    global current_html

    # Prompt voor AI om HTML aan te passen
    ai_prompt = f"""
Je bent een AI die bestaande HTML aanpast op basis van een gebruikersvraag.
Geef alleen de volledige aangepaste HTML terug.

Huidige HTML:
{current_html}

Gebruikersverzoek:
"""{req.prompt}"""

Aangepaste HTML:
"""

    response = openai.ChatCompletion.create(
        model="gpt-4",  # evt. gpt-4o
        messages=[
            {"role": "system", "content": "Je bent een AI die bestaande HTML aanpast. Geef alleen volledige geldige HTML terug."},
            {"role": "user", "content": ai_prompt},
        ],
        temperature=0.2,
    )

    new_html = response.choices[0].message.content.strip()
    current_html = new_html  # update globale html

    return {
        "html": new_html,
        "supabase_instructions": "",  # optioneel leeg
        "version_timestamp": datetime.utcnow().isoformat()
    }

@app.post("/execute-supabase")
async def execute_supabase(req: SupabaseRequest):
    return {"message": "Geen supabase-acties nodig voor deze prompt."}

@app.get("/")
def root():
    return {"message": "AI HTML builder draait"}
