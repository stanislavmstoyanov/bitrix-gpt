from fastapi import FastAPI
import requests
from openai import OpenAI
import os

app = FastAPI()

BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)


@app.get("/")
def health():
    return {"status": "ok"}


def get_entity(entity_type, entity_id):
    method = "crm.deal.get" if entity_type == "deal" else "crm.lead.get"
    return requests.get(
        f"{BITRIX_WEBHOOK}/{method}",
        params={"ID": entity_id}
    ).json()["result"]


def update_entity(entity_type, entity_id, text):
    if entity_type == "deal":
        field = "UF_CRM_GPT_FOLLOWUP_DEAL"
        update_method = "crm.deal.update"
        timeline_type = "deal"
    else:
        field = "UF_CRM_GPT_FOLLOWUP_LEAD"
        update_method = "crm.lead.update"
        timeline_type = "lead"

    requests.post(
        f"{BITRIX_WEBHOOK}/{update_method}",
        json={
            "id": entity_id,
            "fields": {field: text}
        }
    )

    requests.post(
        f"{BITRIX_WEBHOOK}/crm.timeline.comment.add",
        json={
            "fields": {
                "ENTITY_ID": entity_id,
                "ENTITY_TYPE": timeline_type,
                "COMMENT": "📧 GPT Follow-up Email\n\n" + text
            }
        }
    )


@app.post("/gpt/followup")
def gpt_followup(data: dict):
    entity_type = data["entity_type"]   # lead / deal
    entity_id = data["entity_id"]

    entity = get_entity(entity_type, entity_id)

    name = entity.get("TITLE") or entity.get("NAME", "")
    company = entity.get("COMPANY_TITLE", "")
    stage = entity.get("STATUS_ID") or entity.get("STAGE_ID", "")
    amount = entity.get("OPPORTUNITY", "")

    prompt = f"""
You are an experienced sales manager.

Write a professional follow-up email in English.

Context:
- Entity type: {entity_type}
- Client / Lead: {company or name}
- Stage: {stage}
- Amount: {amount}

Rules:
- Polite and friendly
- Short (max 120 words)
- Ask if client needs more info
- Suggest next step
- No pressure, no clichés
"""

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )

    email_text = response.choices[0].message.content

    update_entity(entity_type, entity_id, email_text)

    return {"status": "ok"}
