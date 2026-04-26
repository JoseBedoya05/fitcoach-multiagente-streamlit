"""
Script opcional para preparar Git desde Colab.

Uso sugerido en una celda:
    !python scripts/git_setup_colab.py
    !git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
    !git push -u origin main

No pongas tokens dentro de este archivo.
"""

import subprocess


def run(cmd):
    print("$", cmd)
    subprocess.run(cmd, shell=True, check=False)


run("git init")
run('git config user.name "Tu Nombre"')
run('git config user.email "tu_correo@example.com"')
run("git add .")
run('git commit -m "Carga inicial FitCoach AI Streamlit MCP"')
run("git branch -M main")
