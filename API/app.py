from fastapi import FastAPI
from .process.process import process

app = FastAPI()

@app.post("/")
def info(model: dict):
    return process(model)