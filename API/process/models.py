from pydantic import BaseModel

# Valida los campos y tipos de la petición de entrada.

class Model_ai(BaseModel):
    ai: str
    api_key_ai: str
    language: str
    mode: str
    prompt_type: str
    prompt: str