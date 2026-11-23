import csv
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from .models import Base, Food, Portion, NutrientUnit
from ..config import DATABASE_URL

TABLESPACE_DIR = os.environ["POSTGRES_TABLESPACE_DIR"]

# Crea el tablespace nutridia si no existe y recrea la base de datos configurada.
# Elimina la base anterior y todos sus datos, cerrando las conexiones activas.

def crear_db_en_d():
    os.makedirs(TABLESPACE_DIR, exist_ok=True)

    loc = TABLESPACE_DIR.replace("\\", "/")

    url = make_url(DATABASE_URL)

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")

    with admin.connect() as conn:
        existe = conn.execute(
            text("SELECT 1 FROM pg_tablespace WHERE spcname = 'nutridia'")
        ).scalar()

        if not existe:
            conn.execute(text(f"CREATE TABLESPACE nutridia LOCATION '{loc}'"))

        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))

        conn.execute(text(f'CREATE DATABASE "{url.database}" TABLESPACE nutridia'))

    admin.dispose()

CSV_DIR = os.environ["USDA_CSV_DIR"]

FOOD_FILE = os.path.join(CSV_DIR, "food.csv")
FOOD_NUTRIENT_FILE = os.path.join(CSV_DIR, "food_nutrient.csv")
NUTRIENT_FILE = os.path.join(CSV_DIR, "nutrient.csv")
FOOD_PORTION_FILE = os.path.join(CSV_DIR, "food_portion.csv")
MEASURE_UNIT_FILE = os.path.join(CSV_DIR, "measure_unit.csv")

# Número máximo de registros por lote de inserción.

BATCH_SIZE = 5000

# Relaciona los identificadores de nutrientes USDA con las columnas de foods.

NUTRIENTS_MAP = {
    1008: "calories",
    1003: "protein",
    1004: "fat",
    1005: "carbs",
    1018: "alcohol",
    1079: "fiber",
    2000: "sugars",
    1258: "sat_fat",
    1253: "cholesterol",
    1093: "sodium",
    1092: "potassium",
    1087: "calcium",
    1089: "iron",
    1090: "magnesium",
    1162: "vit_c",
    1104: "vit_a",
    1114: "vit_d",
    1177: "folate",
    1178: "vit_b12",
}

# Convierte el valor a float; devuelve None si no se puede convertir.

def to_float(value):
    try:
        return float(value)
    
    except (TypeError, ValueError):
        return None

# Lee los nutrientes seleccionados de food_nutrient.csv y los agrupa por alimento.

def load_nutrients():
    food_data = {}

    with open(FOOD_NUTRIENT_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            nutrient_id = int(row["nutrient_id"])

            if nutrient_id not in NUTRIENTS_MAP:
                continue

            fdc_id = int(row["fdc_id"])

            food_data.setdefault(fdc_id, {})[NUTRIENTS_MAP[nutrient_id]] = to_float(
                row.get("amount")
            )
    return food_data

# Relaciona cada identificador de alimento con su descripción en food.csv.

def load_names():
    food_names = {}

    with open(FOOD_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            food_names[int(row["fdc_id"])] = row["description"]

    return food_names

# Obtiene las unidades de los nutrientes seleccionados desde nutrient.csv.
# Avisa y omite aquellos cuya unidad no se encuentra.

def load_nutrient_units():
    units_by_id = {}

    with open(NUTRIENT_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            nutrient_id = int(row["id"])

            if nutrient_id in NUTRIENTS_MAP:
                units_by_id[nutrient_id] = row["unit_name"]

    rows = []

    for nutrient_id, column_name in NUTRIENTS_MAP.items():
        unit = units_by_id.get(nutrient_id)

        if unit is None:
            print(f"   AVISO: no se encontró unidad para nutrient_id={nutrient_id} ({column_name})")

            continue

        rows.append({"name": column_name, "unit": unit})

    return rows

# Relaciona los identificadores de unidades de porción con sus nombres.

def load_measure_units():
    units = {}

    with open(MEASURE_UNIT_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            units[int(row["id"])] = row["name"]

    return units

# Recrea la base de datos, habilita pg_trgm y crea las tablas.
# Carga los CSV de USDA e inserta las unidades de nutrientes.
# Inserta los alimentos y sus porciones por lotes.

def main():
    print("Creando base de datos en D:\\Nutridia\\API\\db\\database ")

    crear_db_en_d()

    engine = create_engine(DATABASE_URL)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))

    print("Recreando esquema")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    print("Leyendo food_nutrient.csv (esto tarda un poco, es el archivo grande)")
    food_data = load_nutrients()

    print("Leyendo food.csv (nombres)")
    food_names = load_names()

    print("Leyendo measure_unit.csv")
    measure_units = load_measure_units()

    print("Leyendo nutrient.csv (unidades)")
    nutrient_unit_rows = load_nutrient_units()

    Session = sessionmaker(bind=engine)
    session = Session()

    if nutrient_unit_rows:
        session.bulk_insert_mappings(NutrientUnit, nutrient_unit_rows)

        session.commit()

        print(f"   {len(nutrient_unit_rows)} unidades de nutrientes insertadas.")

    print("Insertando foods")

    valid_ids = set()
    batch = []

    for fdc_id, nutrients_dict in food_data.items():
        name = food_names.get(fdc_id)

        if not name:
            continue

        row = {"id": fdc_id, "name": name}

        for key in NUTRIENTS_MAP.values():
            row[key] = nutrients_dict.get(key)

        batch.append(row)
        valid_ids.add(fdc_id)

        if len(batch) >= BATCH_SIZE:
            session.bulk_insert_mappings(Food, batch)
            session.commit()
            batch.clear()

    if batch:
        session.bulk_insert_mappings(Food, batch)
        session.commit()

    print(f"   {len(valid_ids)} alimentos insertados.")

    print("Leyendo e insertando food_portion.csv")

    portion_batch = []
    portion_count = 0
    skipped = 0

    with open(FOOD_PORTION_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            fdc_id_raw = (row.get("fdc_id") or "").strip()

            if not fdc_id_raw:
                skipped += 1

                continue

            try:
                fdc_id = int(fdc_id_raw)

            except ValueError:
                skipped += 1

                continue

            if fdc_id not in valid_ids:
                continue

            measure_unit_id = row.get("measure_unit_id")
            unit_name = None

            if measure_unit_id:
                try:
                    unit_name = measure_units.get(int(measure_unit_id))

                except ValueError:
                    unit_name = None

            portion_batch.append(
                {
                    "food_id": fdc_id,
                    "amount": to_float(row.get("amount")),
                    "measure_unit": unit_name,
                    "gram_weight": to_float(row.get("gram_weight")),
                    "description": row.get("portion_description") or row.get("modifier"),
                }
            )

            portion_count += 1

            if len(portion_batch) >= BATCH_SIZE:
                session.bulk_insert_mappings(Portion, portion_batch)
                session.commit()
                portion_batch.clear()

    if portion_batch:
        session.bulk_insert_mappings(Portion, portion_batch)
        session.commit()

    print(f"   {portion_count} porciones insertadas, {skipped} filas saltadas por fdc_id vacío o inválido.")

    session.close()

    print("Base de datos creada en Postgres.")


if __name__ == "__main__":
    main()