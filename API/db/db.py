from sqlalchemy import create_engine, text
from ..ai.ai_process import ai_module
from ..process.models import Model_ai
import json
from ..config import DATABASE_URL

engine = create_engine(DATABASE_URL)

# Busca hasta diez nombres de alimentos similares, sin duplicados por mayúsculas.
# Ordena los resultados por similitud mediante pg_trgm.

def search(food: str):
    with engine.connect() as conn:
        return conn.execute(
            text("""
                SELECT name FROM (
                    SELECT DISTINCT ON (lower(name))
                        name,
                        word_similarity(:alimento, name) AS w,
                        similarity(:alimento, name) AS s
                    FROM foods
                    WHERE name %> :alimento
                    ORDER BY lower(name)
                ) t
                ORDER BY w DESC, s DESC
                LIMIT 10
            """),
            {"alimento": food},
        ).scalars().all()

# Obtiene los nutrientes por 100 g del alimento, priorizando el registro más completo.
# Calcula el peso por unidad de la primera porción disponible; usa 100 g si falta.
# Si no encuentra el alimento, devuelve los nutrientes como None y usda=False.

def obtain_nutrients(food: str):
    columnas = [
        "calories", "protein", "fat", "carbs", "alcohol", "fiber", "sugars",
        "sat_fat", "cholesterol", "sodium", "potassium", "calcium", "iron",
        "magnesium", "vit_c", "vit_a", "vit_d", "folate", "vit_b12",
    ]

    with engine.connect() as conn:
        fila = conn.execute(
            text("""
                SELECT * FROM foods
                WHERE lower(name) = lower(:nombre)
                ORDER BY num_nonnulls(
                    calories, protein, fat, carbs, alcohol, fiber, sugars,
                    sat_fat, cholesterol, sodium, potassium, calcium, iron,
                    magnesium, vit_c, vit_a, vit_d, folate, vit_b12
                ) DESC, id
                LIMIT 1
            """),
            {"nombre": food},
        ).mappings().first()

        if not fila:
            return {
                "id": None,
                "usda_name": food,
                "usda": False,
                "weight": 100,
                "values": {c: None for c in columnas},
            }

        peso = conn.execute(
            text("""
                SELECT COALESCE(gram_weight / NULLIF(amount, 0), gram_weight)
                FROM portions
                WHERE food_id = :id AND gram_weight IS NOT NULL
                ORDER BY id
                LIMIT 1
            """),
            {"id": fila["id"]},
        ).scalar()

    values = {c: fila[c] for c in columnas}
    return {
        "id": fila["id"],
        "usda_name": fila["name"],
        "usda": True,
        "weight": float(peso) if peso is not None else 100,
        "values": values,
    }

# Busca cada alimento y solicita a la IA elegir entre los candidatos si no hay coincidencia exacta.
# Comprueba que la opción elegida pertenezca a los candidatos y obtiene sus nutrientes.
# Si no hay una opción válida, conserva el nombre buscado y marca usda=False.

def db_process(payload: Model_ai, request):
    if isinstance(request, str):
        request = json.loads(request)

    verification = []

    for food in request["item"]:
        name = food.get("usda_name") or food["name"]
        trgm = search(name)

        if name.casefold() in [n.casefold() for n in trgm]:
            option = name
        elif trgm:
            selection = json.loads(
                ai_module(
                    payload,
                    "schema_trgm",
                    {"food": name, "options": trgm},
                )
            )

            items = selection.get("item") or []
            candidate = items[0].get("option") if items else None
            option = candidate if candidate in trgm else None
        else:
            option = None

        if option is None:
            nutrients = obtain_nutrients(None)
            nutrients["usda_name"] = name
        else:
            nutrients = obtain_nutrients(option)

        verification.append(nutrients)

    return verification