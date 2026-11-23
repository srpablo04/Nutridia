from llama_cpp import Llama
from llama_cpp.llama_chat_format import Llava15ChatHandler
from ...process.models import Model_ai
import json
import base64
import os
from ...config import AI_DIR

# Codifica la imagen en base64 y devuelve una URL de datos con prefijo JPEG.

def imagen_a_base64(ruta):
    with open(ruta, "rb") as f:
        datos_base64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{datos_base64}"

# Carga el modelo local y configura el contexto según la tarea.
# Para imágenes, utiliza LLaVA con su codificador visual.

def llm(ai_prompt: str):
    handler = None
    context = 4096
    model = os.environ["LLAMA_MODEL_PATH"]

    if ai_prompt == "schema_image":
        model = os.environ["LLAVA_MODEL_PATH"]
        handler = Llava15ChatHandler(
            clip_model_path=os.environ["LLAVA_CLIP_PATH"],
            verbose=False
        )
        context = 1024

    llm = Llama(
        model_path=model,
        chat_handler=handler,
        n_ctx=context,
        n_gpu_layers=-1,
        verbose=False
    )

    return llm

# Carga el esquema JSON correspondiente al tipo de tarea.

def open_json(schema):
    with (AI_DIR / "schema.json").open(encoding="utf-8") as f:
        datos = json.load(f)

    json_schema = {
        "type": "json_object",
        "schema": datos["schema"]["properties"][schema]
    }
    
    return json_schema

# Prepara los mensajes con datos internos, imagen o texto.
# Ejecuta el modelo local con el esquema de salida y devuelve su respuesta.

def llama(payload: Model_ai, ai_prompt: str, prompt: str, trgm: list | dict | None):
    LLM = llm(ai_prompt)

    if trgm is not None:
        content = json.dumps(trgm, ensure_ascii=False)

        historial = [
            {"role": "system", "content": f"{prompt}"},
            {"role": "user", "content":content}
        ]

    else:
        if ai_prompt == "schema_image":
            img_b64 = imagen_a_base64(payload.prompt)
            historial = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{prompt}"},
                        {"type": "image_url", "image_url": {"url": img_b64}}
                    ]
                }
            ]

        else:
            content = payload.prompt

            historial = [
                    {"role": "system", "content": f"{prompt}"},
                    {"role": "user", "content":content}
                ]

    json_schema = open_json(ai_prompt)

    respuesta = LLM.create_chat_completion(
        messages=historial,
        response_format=json_schema,
        temperature = 0,
        max_tokens=2000
        )

    return respuesta["choices"][0]["message"]["content"]