from google import genai
from google.genai import types
from ...process.models import Model_ai
from ...config import AI_DIR
import json

# Lee el archivo de imagen y devuelve su contenido en bytes.

def imagen_a_bytes(ruta):
    with open(ruta, "rb") as f:
        return f.read()

# Crea el cliente de Gemini con la clave recibida en el payload.

def llm(payload: Model_ai):
    return genai.Client(api_key=payload.api_key_ai)

# Carga el esquema JSON correspondiente al tipo de tarea.

def open_json(schema):
    with (AI_DIR / "schema.json").open(encoding="utf-8") as f:
        datos = json.load(f)

    json_schema = {
        "type": "json_object",
        "schema": datos["schema"]["properties"][schema]
    }
    
    return json_schema

# Prepara el contenido según la tarea: datos internos, imagen o texto.
# Llama a Gemini con el esquema de salida y devuelve el texto de la respuesta.

def gemini(payload: Model_ai, ai_prompt: str, prompt: str, trgm: list | dict | None):
    client = llm(payload)
    system = prompt

    if trgm is not None:
        content = json.dumps(trgm, ensure_ascii=False)

    else:
        if ai_prompt == "schema_image":
            img = imagen_a_bytes(payload.prompt)
            system = None
            content = [
                prompt,
                types.Part.from_bytes(data=img, mime_type="image/jpeg")
            ]

        else:
            content = payload.prompt

    json_schema = open_json(ai_prompt)

    respuesta = client.models.generate_content(
        model=payload.ai,
        contents=content,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=json_schema["schema"],
            temperature=0,
            max_output_tokens=2000,
            thinking_config=types.ThinkingConfig(thinking_level="low")
        )
    )

    return respuesta.text