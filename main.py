from fastapi import FastAPI

app = FastAPI()

@app.post("/prompt")
async def prompt_handler(prompt: dict):
    return {"received": prompt}
