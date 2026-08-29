import os
import datetime
from google.cloud import firestore
from google import genai

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
_db = None

def db():
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT)
    return _db


def build_weekly_plan(household_size: int = 5, budget_ngn: int = 20000) -> dict:
    """Reads current prices and containers, produces a week's meal plan
    and shopping list within budget. Called by Cloud Scheduler.
    """
    prices = [d.to_dict() for d in db().collection("prices").stream()]
    containers = [d.to_dict() for d in db().collection("containers").stream()]

    if not prices:
        return {"status": "no_data", "message": "No price records available."}

    client = genai.Client(vertexai=True, project=PROJECT, location="global")

    prompt = f"""You plan weekly meals for a Nigerian household.

Household size: {household_size}
Weekly food budget: {budget_ngn} naira

Known prices (JSON): {prices}
Known container weights (JSON): {containers}

Rules:
- Use ONLY items present in the price data. Never invent prices.
- Prefer high-confidence records. If confidence is below 0.6, say the
  figure is uncertain.
- Plan 7 days of realistic Nigerian meals for this household.
- Produce a shopping list with quantities and a running total.
- The total MUST come in at or under budget. If it cannot, say so and
  show the cheapest viable plan.

Return JSON only:
{{
  "week_of": "YYYY-MM-DD",
  "meals": [{{"day": "Monday", "dishes": ["..."]}}],
  "shopping_list": [{{"item": "...", "quantity": "...", "cost_ngn": 0,
                      "confidence": 0.0}}],
  "total_ngn": 0,
  "budget_ngn": {budget_ngn},
  "under_budget_by_ngn": 0,
  "notes": "any caveats about data quality"
}}"""

    resp = client.models.generate_content(
        model="gemini-3.5-flash", contents=prompt
    )
    text = resp.text.replace("```json", "").replace("```", "").strip()

    week_id = datetime.date.today().isoformat()
    db().collection("plans").document(week_id).set({
        "raw": text,
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "household_size": household_size,
        "budget_ngn": budget_ngn,
        "trigger": "scheduled",
    })

    return {"status": "ok", "week_of": week_id, "plan": text}
