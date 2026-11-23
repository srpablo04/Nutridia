import csv
import json
from ..process.models import Model_ai
from ..ai.llama.ai_llama import llama
from ..ai.gemini.ai_gemini import gemini
from ..config import AI_DIR

# Busca el prompt indicado y sustituye sus variables con los datos recibidos.

def build_prompt(payload: Model_ai, ai_prompt: str, internal_data: list | dict | None):
    with (AI_DIR / "prompts.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["prompt"] == ai_prompt:
                return row["texto"].format(
                    payload=payload,
                    data=json.dumps(internal_data, ensure_ascii=False),
                )

    raise ValueError(f"Prompt desconocido: {ai_prompt}")

# Selecciona el proveedor según payload.ai y devuelve su respuesta.
# Si el proveedor no está contemplado, devuelve un mensaje de error.

def ai_module(payload: Model_ai, ai_prompt: str, internal_data: list | dict | None):
    prompt = build_prompt(payload, ai_prompt, internal_data)

    if payload.ai.startswith("llama"):
        return llama(payload, ai_prompt, prompt, internal_data)

    elif payload.ai.startswith("gemini"):
        return gemini(payload, ai_prompt, prompt, internal_data)

    else:
        return "{Error: Error ai_module}"