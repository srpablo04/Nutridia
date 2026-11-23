from ..process.models import Model_ai
from ..ai.ai_process import ai_module
from ..db.db import db_process
import json
import asyncio

# Delega en el módulo de IA la petición de reconocimiento de imagen.

def image(payload: Model_ai, ai_prompt: str, internal_data: list | None):
    result = ai_module(payload, ai_prompt, internal_data)

    return result

# Registra en notes los nutrientes que faltaban y solicita estimaciones por 100 g.
# Aplica las estimaciones por nombre de alimento y convierte los None restantes en 0.

def final_verification(payload, verification):
    nones = []
    for item in verification:
        solo_none = {}
        for nutriente, valor in item["values"].items():
            if valor is None:
                solo_none[nutriente] = None
        item["notes"] = list(solo_none)
        nones.append({"usda_name": item["usda_name"], "values": solo_none})

    estimado = ai_module(payload, "schema_verification", nones)

    if isinstance(estimado, str):
        estimado = json.loads(estimado)

    estimados = {
        est["usda_name"].strip().casefold(): est
        for est in estimado["item"]
    }

    for item in verification:
        est = estimados.get(
            item["usda_name"].strip().casefold(),
            {"values": []},
        )

        for v in est["values"]:
            nutriente = v["nutrient"]
            if nutriente in item["values"] and item["values"][nutriente] is None:
                if v["value"] is not None:
                    item["values"][nutriente] = v["value"]

    for item in verification:
        for nutriente in item["notes"]:
            if item["values"][nutriente] is None:
                item["values"][nutriente] = 0

    return verification

# Construye la respuesta final agrupando los nutrientes por categoría.
# Conserva los valores por 100 g y utiliza amount=1 si no se indicó cantidad.

def build_final(request, verification):
    if isinstance(request, str):
        request = json.loads(request)

    final = {"item": []}

    for food, nut in zip(request["item"], verification):
        v = nut["values"]

        final["item"].append({
            "id": nut["id"],
            "name": food["name"],
            "usda_name": nut["usda_name"],
            "weight": nut["weight"],
            "amount": food["amount"] if food["amount"] is not None else 1,
            "usda": nut["usda"],
            "macros": {
                "calories": v["calories"],
                "protein": v["protein"],
                "fat": v["fat"],
                "carbs": v["carbs"],
                "alcohol": v["alcohol"],
                "fiber": v["fiber"],
                "sugars": v["sugars"],
                "sat_fat": v["sat_fat"],
                "cholesterol": v["cholesterol"],
            },
            "minerals": {
                "sodium": v["sodium"],
                "potassium": v["potassium"],
                "calcium": v["calcium"],
                "iron": v["iron"],
                "magnesium": v["magnesium"],
            },
            "vitamins": {
                "vit_c": v["vit_c"],
                "vit_a": v["vit_a"],
                "vit_d": v["vit_d"],
                "vit_b12": v["vit_b12"],
                "folate": v["folate"],
            },
            "notes": nut["notes"],
        })

    return final

# Identifica los alimentos con IA, consulta sus nutrientes y completa los datos faltantes.
# Devuelve {"item": []} si no se detectan alimentos.

def internal_process(payload: Model_ai):
    request = ai_module(payload, "schema_request", None)

    if isinstance(request, str):
        request = json.loads(request)

    if request.get("error") or not request.get("item"):
        return {"item": []}

    verification = db_process(payload, request)
    final = final_verification(payload, verification)

    return build_final(request, final)

# Valida la entrada y, si contiene una imagen, obtiene su descripción con IA.
# Selecciona el procesamiento según el modo solicitado.

def process(info: dict):
    payload = Model_ai(**info)

    if payload.prompt_type == "image":
        payload.prompt = json.loads(image(payload, "schema_image", None))["resultado"]

    if payload.mode == "fast":
        return asyncio.run(async_response(payload))

    return internal_process(payload)

# Divide el texto por comas y combina los resultados en una única respuesta.
# Procesa las partes en secuencia con Llama y en paralelo con Gemini.
# Devuelve food_not_found si el resultado conjunto no contiene alimentos.

async def async_response(payload: Model_ai):
    base_data = payload.model_dump()

    parts = [p.strip() for p in payload.prompt.split(",") if p.strip()]

    if payload.ai.startswith("llama"):
        # Llama carga el modelo entero en la GPU en cada llamada: de uno en uno
        results = []
        for sub in parts:
            results.append(await async_process(base_data, sub))
    else:
        results = await asyncio.gather(*(async_process(base_data, sub) for sub in parts))

    final = {"item": []}
    for item_json in results:
        final["item"].extend(item_json["item"])

    if not final["item"]:
        return {"error": True, "status": "food_not_found", "message": "No food detected"}

    return final

# Crea un payload para cada fragmento y ejecuta internal_process en un hilo auxiliar.

async def async_process(base_data: dict, subprompt: str):
    info = Model_ai(**{**base_data, "prompt": subprompt})
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, internal_process, info)