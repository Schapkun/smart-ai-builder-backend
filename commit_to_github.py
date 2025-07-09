import requests
import base64
import os
from datetime import datetime

def commit_file_to_github(html_content: str, path: str, commit_message: str):
    token = os.getenv("GH_PAT")
    if not token:
        raise Exception("GH_PAT ontbreekt. Stel deze in als environment variable.")

    repo = "Schapkun/smart-ai-builder"
    branch = "main"
    api_base = f"https://api.github.com/repos/{repo}/contents"

    file_url = f"{api_base}/{path}"

    # 1. Huidige versie ophalen (voor backup)
    get_resp = requests.get(file_url, headers={"Authorization": f"Bearer {token}"})
    if get_resp.status_code == 200:
        current_content = base64.b64decode(get_resp.json()["content"]).decode("utf-8")
        current_sha = get_resp.json()["sha"]

        # 2. Backup aanmaken
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f".backups/{now}/{path}"
        backup_url = f"{api_base}/{backup_path}"
        backup_payload = {
            "message": f"🕒 Backup van {path} op {now}",
            "content": base64.b64encode(current_content.encode("utf-8")).decode("utf-8"),
            "branch": branch
        }

        backup_resp = requests.put(backup_url, headers={"Authorization": f"Bearer {token}"}, json=backup_payload)
        if not backup_resp.ok:
            raise Exception(f"Backup mislukt: {backup_resp.status_code} - {backup_resp.text}")
    else:
        current_sha = None  # nieuw bestand – geen backup nodig

    # 3. Nieuwe inhoud committen
    payload = {
        "message": commit_message,
        "content": base64.b64encode(html_content.encode("utf-8")).decode("utf-8"),
        "branch": branch
    }
    if current_sha:
        payload["sha"] = current_sha

    commit_resp = requests.put(file_url, headers={"Authorization": f"Bearer {token}"}, json=payload)
    if not commit_resp.ok:
        raise Exception(f"GitHub commit mislukt: {commit_resp.status_code} - {commit_resp.text}")
