import logging

# Zet logging aan
logging.basicConfig(level=logging.INFO)

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
            ],
        )

        ai_output = response.choices[0].message.content

        import json
        try:
            ai_json = json.loads(ai_output)
            html = ai_json.get("html", "<div>Geen HTML ontvangen</div>")
            supabase_instructions = ai_json.get("supabase_instructions", "")
        except json.JSONDecodeError:
            html = extract_between(ai_output, "<html>", "</html>")
            supabase_instructions = extract_between(ai_output, "<supabase>", "</supabase>")

        return {
            "html": html,
            "supabase_instructions": supabase_instructions,
            "version_timestamp": datetime.utcnow().isoformat(),
            "raw_output": ai_output,
        }

    except Exception as e:
        logging.error(f"OpenAI error: {str(e)}")
        return {
            "error": str(e),
            "html": "<div style='color:red'>Fout bij AI-aanroep</div>",
            "supabase_instructions": "",
            "version_timestamp": datetime.utcnow().isoformat(),
        }
