from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    # Tijdelijke fallback response voor testdoeleinden
    return {
        "html": "<h1>Test pagina</h1><p>Backend werkt!</p>",
        "supabase_instructions": "",
        "version_timestamp": datetime.utcnow().isoformat(),
        "raw_output": "fallback test"
    }
