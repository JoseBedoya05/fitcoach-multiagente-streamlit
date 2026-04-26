# FitCoach AI — Sistema Multiagente con MCP y Streamlit

Repositorio preparado para desplegar en GitHub y ejecutar una UI en Streamlit a partir del proyecto original del notebook **Agente entrenador**.

El sistema implementa una arquitectura multiagente para un gimnasio:

- **Coordinador**: orquesta el flujo y delega tareas.
- **Agente Entrenador**: recomienda rutinas y ejercicios.
- **Agente Nutricionista**: calcula TMB, TDEE, kcal objetivo y macros.
- **Agente Analista**: calcula línea base, IMC, riesgos y seguimiento.
- **Tools MCP**: servidor compatible en `src/mcp_server_gym.py`.
- **RAG**: búsqueda documental opcional con ChromaDB.
- **Memoria episódica**: histórico por cliente en `memory/C{id}.jsonl`.

---

## 1. Estructura del repositorio

```text
.
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── src/
│   ├── agents/
│   ├── core/
│   ├── llm/
│   ├── mcp_tools/
│   ├── memory/
│   ├── rag/
│   └── mcp_server_gym.py
│
├── data/
│   ├── client_profiles.json
│   ├── exercise_db.json
│   ├── gym_context.json
│   ├── nutrition_db.json
│   └── ft_data/
│
├── docs/
│   └── README.md
│
├── rag_store/
│   └── README.md
│
├── memory/
├── outputs/
├── reports/
├── notebooks/
│   └── Agente_entrenador_original.ipynb
│
└── scripts/
    ├── build_rag_index.py
    ├── check_project.py
    └── git_setup_colab.py
```

---

## 2. Instalación local

Crea un entorno virtual:

```bash
python -m venv .venv
```

Actívalo:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Instala dependencias:

```bash
pip install -r requirements.txt
```

---

## 3. Configurar variables de entorno

Copia el archivo de ejemplo:

```bash
cp .env.example .env
```

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edita `.env` y agrega tu clave:

```text
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o
LLM_MODEL_FAST=gpt-4o-mini
USE_MCP_SERVER=false
ENABLE_RAG=true
```

> `USE_MCP_SERVER=false` es la opción recomendada para Streamlit Cloud porque usa el dispatcher local compatible con las tools del servidor MCP.  
> `USE_MCP_SERVER=true` invoca el servidor MCP por `stdio`.

---

## 4. Ejecutar la aplicación Streamlit

```bash
streamlit run app.py
```

La UI abrirá en:

```text
http://localhost:8501
```

---

## 5. Ejecutar sin API key

La app también abre sin `OPENAI_API_KEY`. En ese caso genera una respuesta demo determinística usando las tools locales:

- perfil del cliente;
- IMC;
- TMB/TDEE;
- macros;
- ejercicios aptos.

Para activar el sistema multiagente real con LLM, configura `OPENAI_API_KEY`.

---

## 6. Probar el servidor MCP

El servidor MCP original quedó disponible en:

```text
src/mcp_server_gym.py
```

Puedes ejecutarlo así:

```bash
python src/mcp_server_gym.py
```

En la app, por defecto se usa un dispatcher local para que Streamlit sea más estable. Si quieres forzar MCP real por `stdio`, cambia en `.env`:

```text
USE_MCP_SERVER=true
```

---

## 7. Reconstruir el RAG

Por tamaño, los PDFs y el vectorstore no se incluyen en GitHub. Para reconstruir:

1. Copia documentos en `docs/` con esta estructura:

```text
docs/
├── ENTRENADOR/
├── NUTRICION/
├── RENDIMIENTO/
└── CLIENTES/
    ├── HIPERTROFIA/
    ├── BAJAR/
    ├── OBESIDAD/
    └── POST_CIRUGIA/
```

2. Ejecuta:

```bash
python scripts/build_rag_index.py
```

Eso generará `rag_store/`, que está excluido por `.gitignore`.

---

## 8. Subir a GitHub

Desde la carpeta del proyecto:

```bash
git init
git add .
git commit -m "Carga inicial FitCoach AI Streamlit MCP"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

No subas:

- `.env`;
- `rag_store/`;
- PDFs completos;
- modelos pesados;
- archivos `.pkl`, `.joblib`, `.pt`, `.safetensors`.

---

## 9. Desplegar en Streamlit Community Cloud

1. Sube este repo a GitHub.
2. Entra a Streamlit Community Cloud.
3. Crea una nueva app.
4. Selecciona:
   - Repository: tu repositorio.
   - Branch: `main`.
   - Main file path: `app.py`.
5. En **Secrets**, agrega:

```toml
OPENAI_API_KEY = "sk-..."
LLM_MODEL = "gpt-4o"
LLM_MODEL_FAST = "gpt-4o-mini"
```

6. Despliega.

---

## 10. Archivos excluidos del ZIP original

El ZIP original incluía documentos PDF duplicados y un vectorstore Chroma pesado. Esta versión los deja fuera para que GitHub sea limpio y mantenible.

Se conservó:

- código base del servidor MCP;
- JSONs estructurados;
- notebook original;
- datos pequeños de fine-tuning;
- informe inicial;
- estructura modular para Streamlit;
- scripts de validación y reconstrucción RAG.

---

## 11. Comando rápido de validación

```bash
python scripts/check_project.py
```

Luego:

```bash
streamlit run app.py
```
