from __future__ import annotations

import importlib
from pathlib import Path

required_files = [
    "app.py",
    "requirements.txt",
    "src/core/multiagent_runner.py",
    "src/mcp_server_gym.py",
    "data/client_profiles.json",
    "data/exercise_db.json",
    "data/nutrition_db.json",
    "data/gym_context.json",
]

print("Verificando archivos...")
for f in required_files:
    ok = Path(f).exists()
    print(f"{'OK' if ok else 'FALTA'}  {f}")

print("\nVerificando imports principales...")
modules = [
    "streamlit",
    "openai",
    "src.core.multiagent_runner",
    "src.mcp_tools.local_tools",
]
for m in modules:
    try:
        importlib.import_module(m)
        print(f"OK     {m}")
    except Exception as e:
        print(f"FALLA  {m}: {e}")

print("\nListo.")
