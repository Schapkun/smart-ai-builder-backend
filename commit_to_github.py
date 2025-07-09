import requests
import base64
import os

def commit_file_to_github(html_content: str, path: str, commit_message: str):
    token = os.getenv("GH_PAT")
    if not token:
        raise Exception("GH_PAT ontbreekt. Stel deze in als environment variable.")

    repo = "Schapkun/smart-ai-builder"
    branch = "main"
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # 1. Bestaat het bestand al? Dan moeten we de SHA ophalen
    get_resp = requests.get(api_url, headers={"Authorization": f"Bearer {token}"})
    sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

    # 2. Payload voorbereiden
    payload = {
        "message": commit_message,
        "content": base64.b64encode(html_content.encode("utf-8")).decode("utf-8"),
        "branch": branch
    }
    if sha:
        payload["sha"] = sha

    # 3. Commit uitvoeren
    response = requests.put(api_url, headers={"Authorization": f"Bearer {token}"}, json=payload)
    if not response.ok:
        raise Exception(f"GitHub commit mislukt: {response.status_code} - {response.text}")
