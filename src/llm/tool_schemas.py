from __future__ import annotations

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_client",
            "description": "Devuelve el perfil estructurado de un cliente por ID, por ejemplo C1, C2, C3 o C4.",
            "parameters": {
                "type": "object",
                "properties": {"client_id": {"type": "string"}},
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_imc",
            "description": "Calcula el IMC y su categoria OMS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "weight_kg": {"type": "number"},
                    "height_cm": {"type": "number"},
                },
                "required": ["weight_kg", "height_cm"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_tmb_tdee",
            "description": "Calcula TMB por Mifflin-St Jeor y TDEE con factor de actividad.",
            "parameters": {
                "type": "object",
                "properties": {
                    "weight_kg": {"type": "number"},
                    "height_cm": {"type": "number"},
                    "age": {"type": "integer"},
                    "gender": {"type": "string"},
                    "activity": {
                        "type": "string",
                        "enum": ["sedentaria", "ligera", "moderada", "alta", "muy_alta"],
                        "default": "moderada",
                    },
                },
                "required": ["weight_kg", "height_cm", "age", "gender"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_macros",
            "description": "Calcula kcal objetivo y gramos de proteina, carbohidratos y grasas segun objetivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tdee": {"type": "number"},
                    "goal": {"type": "string"},
                },
                "required": ["tdee", "goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_exercises",
            "description": "Recomienda ejercicios aptos filtrando por categoria y restricciones medicas/de impacto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "restricciones": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_measurement",
            "description": "Registra una medida de seguimiento del cliente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "weight_kg": {"type": "number"},
                    "body_fat_pct": {"type": "number"},
                    "note": {"type": "string"},
                },
                "required": ["client_id", "weight_kg", "body_fat_pct"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_progress",
            "description": "Lista el histórico de medidas del cliente.",
            "parameters": {
                "type": "object",
                "properties": {"client_id": {"type": "string"}},
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_risk",
            "description": "Detecta riesgo de estancamiento o perdida de peso muy rapida con base en el histórico.",
            "parameters": {
                "type": "object",
                "properties": {"client_id": {"type": "string"}},
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Recupera evidencia documental desde ChromaDB, con filtros opcionales por categoria o subcategoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 4},
                    "categoria": {"type": "string"},
                    "subcategoria": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
]

SUBAGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "ask_trainer",
            "description": "Delega al Agente Entrenador para rutinas, progresión, técnica y adaptaciones de ejercicio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "task": {"type": "string"},
                },
                "required": ["client_id", "task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_nutritionist",
            "description": "Delega al Agente Nutricionista para kcal, TDEE, macros, comidas y recomendaciones nutricionales.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "task": {"type": "string"},
                },
                "required": ["client_id", "task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_analyst",
            "description": "Delega al Agente Analista para línea base, IMC, riesgos, seguimiento y métricas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "task": {"type": "string"},
                },
                "required": ["client_id", "task"],
            },
        },
    },
]
