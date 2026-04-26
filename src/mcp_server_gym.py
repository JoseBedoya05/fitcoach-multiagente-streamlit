
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# ----------------------------------------------------------------------
#  Carga de datos estructurados (JSON) desde la carpeta data/
# ----------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

GYM       = json.loads((DATA_DIR / "gym_context.json").read_text(encoding="utf-8"))
CLIENTS   = json.loads((DATA_DIR / "client_profiles.json").read_text(encoding="utf-8"))
EXERCISES = json.loads((DATA_DIR / "exercise_db.json").read_text(encoding="utf-8"))
NUTRI     = json.loads((DATA_DIR / "nutrition_db.json").read_text(encoding="utf-8"))

CLIENT_MAP = {c["id"]: c for c in CLIENTS}

# Memoria en caliente para el histórico de medidas (reinicia por sesión).
PROGRESS: dict[str, list[dict[str, Any]]] = defaultdict(list)

# ----------------------------------------------------------------------
#  Instancia del servidor MCP
# ----------------------------------------------------------------------
mcp = FastMCP("fitcoach-gym", json_response=True)


# ======================================================================
#  RESOURCES
# ======================================================================
@mcp.resource("gym://overview")
def gym_overview() -> str:
    """Informacion general del gimnasio, temas y filosofia."""
    return json.dumps(GYM, ensure_ascii=False)


@mcp.resource("client://{client_id}")
def client_profile(client_id: str) -> str:
    """Perfil completo de un cliente por ID (C1..C4)."""
    prof = CLIENT_MAP.get(client_id.upper())
    if not prof:
        return json.dumps({"error": f"cliente {client_id} no existe"})
    return json.dumps(prof, ensure_ascii=False)


@mcp.resource("exercises://catalog")
def exercises_catalog() -> str:
    """Catalogo completo de ejercicios con nivel, impacto y contraindicaciones."""
    return json.dumps(EXERCISES, ensure_ascii=False)


# ======================================================================
#  PROMPTS
# ======================================================================
@mcp.prompt()
def adaptive_trainer(client_id: str, pregunta: str) -> str:
    """Prompt de sistema del Entrenador, adaptado al cliente."""
    c = CLIENT_MAP.get(client_id.upper(), {})
    return (
        f"Eres el Entrenador Personal de {c.get('name','el cliente')}. "
        f"Perfil: {c.get('age','?')} anios, objetivo '{c.get('goal','?')}', "
        f"frecuencia {c.get('weekly_frequency','?')} dias/semana, "
        f"restricciones {c.get('restrictions',[])}. "
        f"Respondes de forma profesional, practica y adaptada a ese perfil. "
        f"Pregunta del cliente: {pregunta}"
    )


@mcp.prompt()
def nutrition_coach(client_id: str, pregunta: str) -> str:
    """Prompt de sistema del Nutricionista, con datos del cliente pre-cargados."""
    c = CLIENT_MAP.get(client_id.upper(), {})
    return (
        f"Eres Nutricionista Deportivo de {c.get('name','el cliente')}. "
        f"Peso {c.get('weight_kg','?')}kg, altura {c.get('height_cm','?')}cm, "
        f"%grasa {c.get('body_fat_pct','?')}%, objetivo '{c.get('goal','?')}'. "
        f"Responde con cifras concretas (kcal, gramos de macros) cuando sea posible. "
        f"Pregunta: {pregunta}"
    )


# ======================================================================
#  TOOLS
# ======================================================================
@mcp.tool()
def get_client(client_id: str) -> dict:
    """Devuelve el perfil estructurado de un cliente."""
    return CLIENT_MAP.get(client_id.upper(), {"error": "cliente no existe"})


@mcp.tool()
def compute_imc(weight_kg: float, height_cm: float) -> dict:
    """Calcula el IMC (kg/m^2) y lo clasifica segun OMS."""
    h = height_cm / 100.0
    imc = round(weight_kg / (h * h), 2)
    if imc < 18.5:   categoria = "bajo_peso"
    elif imc < 25.0: categoria = "normal"
    elif imc < 30.0: categoria = "sobrepeso"
    else:            categoria = "obesidad"
    return {"imc": imc, "categoria": categoria}


@mcp.tool()
def compute_tmb_tdee(weight_kg: float, height_cm: float, age: int,
                     gender: str, activity: str = "moderada") -> dict:
    """TMB por Mifflin-St Jeor y TDEE segun nivel de actividad."""
    if gender.upper().startswith("M"):
        tmb = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        tmb = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    factores = {"sedentaria": 1.2, "ligera": 1.375, "moderada": 1.55,
                "alta": 1.725, "muy_alta": 1.9}
    factor = factores.get(activity, 1.55)
    tdee = round(tmb * factor, 0)
    return {"tmb": round(tmb, 0), "tdee": tdee, "factor_actividad": factor}


@mcp.tool()
def plan_macros(tdee: float, goal: str) -> dict:
    """Calcula kcal objetivo y distribucion en gramos de macronutrientes."""
    goal_key = goal.lower()
    ajuste = NUTRI["kcal_ajuste_pct"].get(goal_key, 0) / 100.0
    kcal = tdee * (1 + ajuste)
    reparto = NUTRI["reparto_macros"].get(goal_key, NUTRI["reparto_macros"]["mantenimiento"])
    return {
        "kcal_objetivo": round(kcal, 0),
        "proteina_g": round(kcal * reparto["prot"] / 4, 0),
        "carbos_g":   round(kcal * reparto["carb"] / 4, 0),
        "grasas_g":   round(kcal * reparto["gras"] / 9, 0),
        "reparto_pct": reparto,
        "comidas_por_dia": NUTRI["comidas_por_dia_recomendadas"].get(goal_key, 3)
    }


@mcp.tool()
def recommend_exercises(category: str, restricciones: list[str] = []) -> list:
    """Devuelve ejercicios aptos filtrando los que tengan contraindicaciones."""
    resultado = []
    for nombre, info in EXERCISES.items():
        excluir = False
        for r in restricciones:
            for c in info["contraindicado"]:
                if r.lower() in c.lower() or c.lower() in r.lower():
                    excluir = True
                    break
            if excluir:
                break
        if not excluir:
            resultado.append({"ejercicio": nombre, **info})
    return resultado


@mcp.tool()
def register_measurement(client_id: str, weight_kg: float,
                         body_fat_pct: float, note: str = "") -> dict:
    """Registra una medida puntual del cliente en el historico."""
    entry = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "weight_kg": weight_kg,
        "body_fat_pct": body_fat_pct,
        "note": note
    }
    PROGRESS[client_id.upper()].append(entry)
    return {"ok": True,
            "total_registros": len(PROGRESS[client_id.upper()]),
            "last": entry}


@mcp.tool()
def list_progress(client_id: str) -> list:
    """Lista el historico de medidas del cliente."""
    return PROGRESS.get(client_id.upper(), [])


@mcp.tool()
def detect_risk(client_id: str) -> dict:
    """Detecta estancamiento o perdida demasiado rapida."""
    log = PROGRESS.get(client_id.upper(), [])
    if len(log) < 2:
        return {"risk": "insuficientes_datos"}
    first, last = log[0], log[-1]
    dw = last["weight_kg"] - first["weight_kg"]
    if abs(dw) < 0.2 and len(log) >= 4:
        return {"risk": "estancamiento", "delta_peso_kg": dw}
    if dw < -1.5 and len(log) <= 3:
        return {"risk": "perdida_muy_rapida", "delta_peso_kg": dw}
    return {"risk": "ok", "delta_peso_kg": dw}


# ======================================================================
#  ENTRYPOINT - se ejecuta cuando se invoca como subproceso
# ======================================================================
if __name__ == "__main__":
    mcp.run(transport="stdio")
