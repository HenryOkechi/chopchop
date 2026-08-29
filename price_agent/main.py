import os
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from .planner import build_weekly_plan

app: FastAPI = get_fast_api_app(
    agents_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    web=True,
)

@app.post("/weekly-plan")
def weekly_plan():
    return build_weekly_plan()
