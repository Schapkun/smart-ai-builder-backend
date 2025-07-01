from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from openai import OpenAI  # ✅ Alleen deze import gebruiken

app = FastAPI()

# CORS voor frontend toegang
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Vervang door frontend domein in productie
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI client instellen
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class PromptRequest(BaseModel):
    prompt: str

class ExecuteRequest(BaseModel):
    instructions: str

current_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Meester.app</title>
  <style>
    footer {
      color: gray;
      font-size: 12px;
      padding: 20px;
    }
  </style>
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
{current_html}

Gebruikersverzoek:
{req.prompt}

Aangepaste HTML:
"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": ai_prompt}],
        temperature=0
    )

    html = response.choices[0].message.content.strip()

    return {
        "html": html,
        "supabase_instructions": "",
        "version_timestamp": str(os.times().elapsed),
    }

@app.post("/execute-supabase")
async def execute_supabase(req: ExecuteRequest):
    return {"message": "Supabase instructies uitgevoerd (simulatie)"}
