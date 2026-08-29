import os
from fastapi import FastAPI
from planner import build_weekly_plan

app = FastAPI()

@app.get("/")
def health():
    return {"status": "alive"}

@app.post("/weekly-plan")
def weekly_plan():
    return build_weekly_plan()
