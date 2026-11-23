# Nutridia

Nutridia es una API que identifica alimentos a partir de texto o imágenes y devuelve su información nutricional.

Utiliza una base de datos local de USDA FoodData Central y permite elegir entre Gemini, mediante la API de Google, o Llama, ejecutado localmente con GPU NVIDIA. Para reconocer imágenes con modelos locales utiliza LLaVA.

La instalación de esta versión es manual. Docker queda pendiente para una versión futura.

## Funcionamiento

La IA interpreta la petición e identifica los alimentos y sus cantidades. Después, Nutridia busca sus nutrientes en PostgreSQL.

Si no encuentra una coincidencia exacta, busca nombres similares mediante `pg_trgm` y solicita a la IA que seleccione entre los candidatos. Los nutrientes ausentes se completan mediante estimaciones. Si algún valor continúa sin completarse, se sustituye por cero por decisión de diseño.

La respuesta agrupa los nutrientes en macronutrientes, minerales y vitaminas.

## Requisitos

Las instrucciones siguientes están orientadas a Windows y PowerShell. El entorno de desarrollo utiliza Python 3.13 y PostgreSQL 18.

Necesitas:

- Python 3.13.
- PostgreSQL 18, con la extensión `pg_trgm` disponible.
- Las dependencias incluidas en `requirements.txt`.
- Una clave de Google para utilizar Gemini.
- Una GPU NVIDIA compatible, su controlador y CUDA Toolkit para ejecutar Llama por GPU.
- Las herramientas de compilación de C++ de Visual Studio para compilar `llama-cpp-python` con CUDA.
- Un modelo GGUF de texto y, para imágenes locales, un modelo LLaVA compatible con `Llava15ChatHandler` y su codificador visual correspondiente.

Gemini no utiliza la GPU del ordenador. Sin embargo, la aplicación importa ambos proveedores al arrancar, por lo que también necesita tener instaladas las dependencias de Llama.

Los modelos no están incluidos en el repositorio. Su compatibilidad y la memoria de vídeo necesaria dependen de los archivos elegidos.

## Instalación de las dependencias

Descarga el proyecto y abre una terminal de desarrollo de Visual Studio con PowerShell en su carpeta principal, donde se encuentra `requirements.txt`.

Crea y activa el entorno virtual:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Con el controlador NVIDIA, CUDA Toolkit y las herramientas de C++ instalados, indica que Llama debe compilarse con CUDA e instala las dependencias:

```powershell
$env:CMAKE_ARGS = "-DGGML_CUDA=ON"

python -m pip install --no-cache-dir --no-binary=llama-cpp-python -r requirements.txt

Remove-Item Env:CMAKE_ARGS
```

La compilación puede tardar. La versión de CUDA Toolkit debe ser compatible con la GPU, el controlador y el compilador de C++ utilizados.

El código configura Llama con `n_gpu_layers=-1`, solicitando la carga de las capas en GPU. Instalar una versión de `llama-cpp-python` sin CUDA no proporciona ese soporte.

## Configuración de `.env`

En la carpeta principal, copia la plantilla:

```powershell
Copy-Item .env.example .env
```

Edita `.env` con la configuración del equipo donde se ejecutará Nutridia. No cambies los nombres de las variables.

| Variable | Para qué se utiliza |
| --- | --- |
| `DATABASE_URL` | Conexión a PostgreSQL: usuario, contraseña, servidor y nombre de la base. |
| `LLAMA_MODEL_PATH` | Ubicación del modelo GGUF de texto. |
| `LLAVA_MODEL_PATH` | Ubicación del modelo GGUF de LLaVA. |
| `LLAVA_CLIP_PATH` | Ubicación del codificador visual de ese modelo. |
| `USDA_CSV_DIR` | Carpeta con los CSV, utilizada al reconstruir la base desde USDA. |
| `POSTGRES_TABLESPACE_DIR` | Carpeta del tablespace, utilizada por el script de creación de la base. |

Cada usuario debe poner las ubicaciones de sus propios archivos. No necesita reproducir las carpetas del equipo de desarrollo.

Por ejemplo, si guarda los tres modelos dentro de una carpeta `models` en la raíz del proyecto, puede utilizar:

```dotenv
LLAMA_MODEL_PATH=./models/Llama.gguf
LLAVA_MODEL_PATH=./models/Llava.gguf
LLAVA_CLIP_PATH=./models/codificador_vision.gguf
```

Esas rutas relativas funcionan arrancando la aplicación desde la carpeta principal del proyecto. Los nombres deben coincidir con los archivos reales; renombrar un modelo no cambia su compatibilidad.

Para la conexión, la estructura es:

```text
postgresql+psycopg://USUARIO:CONTRASEÑA@SERVIDOR/NOMBRE_BASE
```

Los caracteres reservados de una URL que aparezcan en la contraseña deben codificarse. Un punto normal no necesita codificación.

La clave de Gemini se recibe en cada petición, en `api_key_ai`; no se carga desde `.env`.

### Qué ocurre con el tablespace

`POSTGRES_TABLESPACE_DIR` se conserva porque `API/db/crear_db.py` la necesita.

En el equipo de desarrollo apunta a `D:/Nutridia/API/db/database`. Eso no obliga a otros usuarios a utilizar esa ruta.

- Si restauras una copia de la base con las instrucciones siguientes, PostgreSQL utiliza el almacenamiento de tu instalación y la API no consulta esta variable.
- Si ejecutas `crear_db.py`, debes configurar una ruta absoluta válida para tu equipo, con los permisos necesarios para PostgreSQL.

Lo mismo ocurre con `USDA_CSV_DIR`: se utiliza al reconstruir la base, no al consultar una base ya restaurada.

`.env` contiene la configuración local y queda excluido de Git. `.env.example` se distribuye con valores de ejemplo. Guarda ambos sin añadirles `.txt`.

## Base de datos

Nutridia ya dispone de una base preparada en el entorno de desarrollo. No es necesario reconstruir sus datos desde los CSV para cada instalación.

La carpeta `API/db/database` contiene archivos internos del tablespace de PostgreSQL. Para trasladar la base a otra instalación se necesita una exportación; copiar únicamente esa carpeta no constituye una restauración completa.

### Preparar la copia para distribuirla

Este apartado corresponde a quien publica el proyecto y se realiza una vez por cada versión de la base que quiera compartir.

El respaldo todavía debe generarse y distribuirse. El siguiente comando crea un archivo nuevo llamado `nutridia.dump` a partir de la base existente; no borra ni modifica sus datos.

En PowerShell, desde la carpeta donde quieras guardar el archivo:

```powershell
& "$env:ProgramFiles\PostgreSQL\18\bin\pg_dump.exe" `
    --host localhost `
    --username postgres `
    --dbname sqlalchemy_3 `
    --format custom `
    --no-tablespaces `
    --file nutridia.dump
```

Introduce la contraseña de PostgreSQL cuando se solicite.

Si PostgreSQL está instalado en otra ubicación, ajusta la ruta del ejecutable. El archivo generado debe facilitarse junto al proyecto o mediante una descarga separada, según su tamaño.

### Restaurar la copia en otro equipo

Estos comandos presuponen que has recibido `nutridia.dump`, tienes PostgreSQL iniciado y todavía no existe una base llamada `sqlalchemy_3` en esa instalación.

Desde la carpeta que contiene el archivo, crea la base de destino:

```powershell
& "$env:ProgramFiles\PostgreSQL\18\bin\createdb.exe" `
    --host localhost `
    --username postgres `
    sqlalchemy_3
```

Restaura los datos:

```powershell
& "$env:ProgramFiles\PostgreSQL\18\bin\pg_restore.exe" `
    --host localhost `
    --username postgres `
    --dbname sqlalchemy_3 `
    --no-owner `
    --no-privileges `
    --no-tablespaces `
    --exit-on-error `
    --single-transaction `
    nutridia.dump
```

La restauración recupera las tablas, los datos, los índices y la extensión `pg_trgm` incluida en la exportación. Las opciones utilizadas evitan depender del propietario y del tablespace originales.

PostgreSQL guarda los datos en el almacenamiento de la instalación de destino. No necesita que exista `D:/Nutridia/API/db/database`.

Después, configura `DATABASE_URL` en `.env` con el usuario, contraseña, servidor y base que acabas de utilizar.

Si ya existe una base con ese nombre, utiliza otro nombre tanto en los comandos como en `DATABASE_URL`. No borres una base existente para seguir estas instrucciones.

### Reconstrucción desde los CSV

Esta es una alternativa a restaurar la copia preparada.

Descarga los CSV desde [USDA FoodData Central](https://fdc.nal.usda.gov/download-datasets). El importador necesita estos archivos de una misma distribución:

```text
food.csv
food_nutrient.csv
nutrient.csv
food_portion.csv
measure_unit.csv
```

Configura `USDA_CSV_DIR` y `POSTGRES_TABLESPACE_DIR` en `.env`.

La carpeta del tablespace debe estar vacía al crearlo y la cuenta que ejecuta PostgreSQL debe tener permisos sobre ella. El usuario de la conexión necesita permisos para crear bases, tablespaces y la extensión.

Ejecuta desde la raíz del proyecto:

```powershell
python -m API.db.crear_db
```

**Este script elimina y recrea la base indicada en `DATABASE_URL`, incluidos sus datos anteriores.** No se ejecuta para arrancar la API ni después de restaurar una copia ya preparada.

Si ya existe un tablespace llamado `nutridia`, el script lo reutiliza. Cambiar la ruta de `.env` no mueve automáticamente ese tablespace.

La carga puede tardar y consumir bastante memoria.

## Arrancar Nutridia

Con el entorno virtual activado, PostgreSQL iniciado y `.env` configurado, ejecuta desde la carpeta principal:

```powershell
python -m uvicorn API.app:app --reload
```

La documentación interactiva estará en:

```text
http://127.0.0.1:8000/docs
```

El endpoint de análisis es `POST /`.

La restauración o importación de la base se hace al preparar la instalación. No hay que repetirla cada vez que se inicia Nutridia.

## Uso

### Texto con Gemini

```json
{
  "ai": "gemini-3.5-flash-lite",
  "api_key_ai": "TU_CLAVE_DE_GEMINI",
  "language": "es",
  "mode": "fast",
  "prompt_type": "text",
  "prompt": "Comí 2 manzanas y una pera."
}
```

El modelo debe estar disponible para la cuenta de Google utilizada. Las cuotas y la disponibilidad dependen del proveedor.

### Texto con Llama

```json
{
  "ai": "llama",
  "api_key_ai": "",
  "language": "es",
  "mode": "fast",
  "prompt_type": "text",
  "prompt": "Comí 2 manzanas y una pera."
}
```

Llama utiliza los archivos configurados en `.env`. No necesita una clave de API, pero el campo se mantiene porque el modelo de entrada lo exige.

### Imágenes

Para cualquiera de los proveedores, cambia `prompt_type` a `image` y utiliza en `prompt` la ruta de la imagen.

Por ejemplo, si tienes `images/comida.jpg` dentro del proyecto:

```json
{
  "ai": "llama",
  "api_key_ai": "",
  "language": "es",
  "mode": "economy",
  "prompt_type": "image",
  "prompt": "./images/comida.jpg"
}
```

La ruta corresponde al equipo donde se ejecuta la API. Este endpoint no sube un archivo desde el cliente.

El código declara el contenido de la imagen como JPEG, por lo que los ejemplos utilizan ese formato.

### Modos

- `fast` divide el texto por comas y reúne los resultados. Con Gemini procesa los fragmentos en paralelo; con Llama los procesa en secuencia.
- `economy` procesa el texto completo sin esa división. Puede realizar varias llamadas a la IA durante el análisis.

## Respuesta

Cada alimento incluye:

| Campo | Significado |
| --- | --- |
| `id` | Identificador USDA del registro encontrado; `null` si no hay coincidencia. |
| `name` | Nombre del alimento en el idioma solicitado. |
| `usda_name` | Nombre seleccionado en USDA o nombre conservado si no se encuentra. |
| `weight` | Peso en gramos por unidad de la porción seleccionada. Usa 100 si no hay información disponible. |
| `amount` | Cantidad detectada; usa 1 cuando llega como `null`. |
| `usda` | Indica si se encontró un registro en la base local. |
| `macros`, `minerals`, `vitamins` | Información nutricional por 100 g. |
| `notes` | Nutrientes que faltaban originalmente, antes de solicitar estimaciones. |

Los nutrientes se devuelven **por 100 g**. No están multiplicados por `weight` ni por `amount`.

Las calorías se expresan en kcal. Los demás nutrientes conservan las unidades correspondientes a USDA, recogidas en `nutrient_units`.

`usda: true` indica que se encontró el alimento en la base, pero algunos de sus nutrientes pueden haberse completado mediante IA.

Un cero puede corresponder al valor del nutriente o a un dato que no se consiguió completar. `notes` identifica los campos originalmente ausentes, aunque después se hayan estimado o sustituido por cero.

Si no se detectan alimentos, `fast` devuelve:

```json
{
  "error": true,
  "status": "food_not_found",
  "message": "No food detected"
}
```

En `economy`, devuelve:

```json
{
  "item": []
}
```

## Limitaciones actuales

La identificación de alimentos y las estimaciones pueden contener errores. El resultado depende del modelo utilizado y, en imágenes, de lo que se pueda reconocer visualmente.

La instalación con GPU depende de la compatibilidad entre el hardware, el controlador, CUDA y `llama-cpp-python`. No se ha validado en todos los equipos.

Los errores de autenticación, disponibilidad o cuotas de Gemini se reciben desde Google. La aplicación todavía puede propagarlos como errores de la petición.

La API se ejecuta localmente y esta versión no incorpora autenticación ni una configuración de publicación en Internet.