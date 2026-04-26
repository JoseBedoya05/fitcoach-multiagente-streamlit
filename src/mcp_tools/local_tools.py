from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import DATA_DIR

GYM = json.loads((DATA_DIR / "gym_context.json").read_text(encoding="utf-8"))
CLIENTS = json.loads((DATA_DIR / "client_profiles.json").read_text(encoding="utf-8"))
EXERCISES = json.loads((DATA_DIR / "exercise_db.json").read_text(encoding="utf-8"))
NUTRI = json.loads((DATA_DIR / "nutrition_db.json").read_text(encoding="utf-8"))

CLIENT_MAP = {c["id"].upper(): c for c in CLIENTS}
PROGRESS: dict[str, list[dict[str, Any]]] = defaultdict(list)


def get_client(client_id: str) -> dict:
    """Devuelve el perfil estructurado de un cliente."""
    return CLIENT_MAP.get(str(client_id).upper(), {"error": f"cliente {client_id} no existe"})


def list_clients() -> list[dict]:
    """Lista perfiles disponibles para la UI."""
    return CLIENTS


def compute_imc(weight_kg: float, height_cm: float) -> dict:
    """Calcula el IMC (kg/m^2) y lo clasifica segun OMS."""
    weight_kg = float(weight_kg)
    height_cm = float(height_cm)
    if height_cm <= 0:
        return {"error": "height_cm debe ser mayor que cero"}
    h = height_cm / 100.0
    imc = round(weight_kg / (h * h), 2)
    if imc < 18.5:
        categoria = "bajo_peso"
    elif imc < 25.0:
        categoria = "normal"
    elif imc < 30.0:
        categoria = "sobrepeso"
    else:
        categoria = "obesidad"
    return {"imc": imc, "categoria": categoria}


def compute_tmb_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity: str = "moderada",
) -> dict:
    """TMB por Mifflin-St Jeor y TDEE segun nivel de actividad."""
    weight_kg = float(weight_kg)
    height_cm = float(height_cm)
    age = int(age)
    gender = str(gender or "").upper()
    if gender.startswith("M"):
        tmb = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        tmb = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    factores = {
        "sedentaria": 1.2,
        "ligera": 1.375,
        "moderada": 1.55,
        "alta": 1.725,
        "muy_alta": 1.9,
    }
    factor = factores.get(str(activity).lower(), 1.55)
    tdee = round(tmb * factor, 0)
    return {"tmb": round(tmb, 0), "tdee": tdee, "factor_actividad": factor}


def _goal_key(goal: str) -> str:
    g = str(goal or "").lower()
    if any(x in g for x in ["hipertrofia", "músculo", "musculo", "volumen", "masa"]):
        return "hipertrofia"
    if any(x in g for x in ["bajar", "peso", "perdida", "pérdida", "definir", "definicion", "definición", "grasa"]):
        return "perdida"
    if any(x in g for x in ["lipo", "post", "cirugia", "cirugía"]):
        return "post_cirugia"
    return "mantenimiento"


def plan_macros(tdee: float, goal: str) -> dict:
    """Calcula kcal objetivo y distribucion en gramos de macronutrientes."""
    tdee = float(tdee)
    goal_key = _goal_key(goal)
    ajuste = NUTRI["kcal_ajuste_pct"].get(goal_key, 0) / 100.0
    kcal = tdee * (1 + ajuste)
    reparto = NUTRI["reparto_macros"].get(goal_key, NUTRI["reparto_macros"]["mantenimiento"])
    return {
        "goal_key": goal_key,
        "kcal_objetivo": round(kcal, 0),
        "proteina_g": round(kcal * reparto["prot"] / 4, 0),
        "carbos_g": round(kcal * reparto["carb"] / 4, 0),
        "grasas_g": round(kcal * reparto["gras"] / 9, 0),
        "reparto_pct": reparto,
        "comidas_por_dia": NUTRI["comidas_por_dia_recomendadas"].get(goal_key, 3),
    }


def recommend_exercises(category: str, restricciones: list[str] | None = None) -> list[dict]:
    """Devuelve ejercicios aptos filtrando los que tengan contraindicaciones."""
    restricciones = restricciones or []
    resultado = []
    cat = str(category or "").upper()
    for nombre, info in EXERCISES.items():
        excluir = False
        contraindicados = info.get("contraindicado", [])
        # Reglas duras para bajo impacto.
        if cat in {"BAJAR", "POST_CIRUGIA", "OBESIDAD"} and info.get("impacto") == "alto":
            excluir = True
        for r in restricciones:
            r_low = str(r).lower()
            for c in contraindicados:
                c_low = str(c).lower()
                if r_low in c_low or c_low in r_low:
                    excluir = True
                    break
            if excluir:
                break
        if not excluir:
            resultado.append({"ejercicio": nombre, **info})
    return resultado


def register_measurement(client_id: str, weight_kg: float, body_fat_pct: float, note: str = "") -> dict:
    """Registra una medida puntual del cliente en el historico en memoria de proceso."""
    entry = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "weight_kg": float(weight_kg),
        "body_fat_pct": float(body_fat_pct),
        "note": note,
    }
    PROGRESS[str(client_id).upper()].append(entry)
    return {
        "ok": True,
        "total_registros": len(PROGRESS[str(client_id).upper()]),
        "last": entry,
    }


def list_progress(client_id: str) -> list:
    """Lista el historico de medidas del cliente en memoria de proceso."""
    return PROGRESS.get(str(client_id).upper(), [])


def detect_risk(client_id: str) -> dict:
    """Detecta estancamiento o perdida demasiado rapida."""
    log = PROGRESS.get(str(client_id).upper(), [])
    if len(log) < 2:
        return {"risk": "insuficientes_datos"}
    first, last = log[0], log[-1]
    dw = last["weight_kg"] - first["weight_kg"]
    if abs(dw) < 0.2 and len(log) >= 4:
        return {"risk": "estancamiento", "delta_peso_kg": dw}
    if dw < -1.5 and len(log) <= 3:
        return {"risk": "perdida_muy_rapida", "delta_peso_kg": dw}
    return {"risk": "ok", "delta_peso_kg": dw}
