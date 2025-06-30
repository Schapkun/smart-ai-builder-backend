from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ CORS Middleware toevoegen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Voor productie liever beperken tot je frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ POST endpoint voor prompt
@app.post("/prompt")
async def prompt_handler(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    return {"response": f"Je prompt was: '{prompt}'"}
