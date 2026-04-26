from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

# Permite leer OPENAI_API_KEY desde Streamlit Cloud secrets.
try:
    if "OPENAI_API_KEY" in st.secrets and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    if "LLM_MODEL" in st.secrets:
        os.environ["LLM_MODEL"] = st.secrets["LLM_MODEL"]
except Exception:
    pass

from src.config import LLM_MODEL, RAG_STORE_DIR, USE_MCP_SERVER
from src.core.multiagent_runner import run_multiagent
from src.mcp_tools.local_tools import list_clients
from src.memory.client_memory import clear_memory, load_recent_episodes


st.set_page_config(
    page_title="FitCoach AI | Sistema Multiagente MCP",
    page_icon="🏋️",
    layout="wide",
)


def transcribir_audio(audio_file) -> str:
    """Transcribe audio con Whisper API de OpenAI si hay API key."""
    if audio_file is None:
        return ""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("Para transcribir audio debes configurar OPENAI_API_KEY.")
        return ""

    from openai import OpenAI

    suffix = Path(audio_file.name).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name

    try:
        client = OpenAI(api_key=api_key)
        with open(tmp_path, "rb") as f:
            tr = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="es",
            )
        return tr.text.strip()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


st.title("🏋️ FitCoach AI — Sistema Multiagente con MCP")
st.caption("Coordinador + agentes especializados + herramientas MCP + RAG + memoria episódica por cliente.")

clients = list_clients()
client_labels = {
    c["id"]: f"{c['id']} — {c['name']} · {c.get('goal', 'Sin objetivo')}"
    for c in clients
}
label_to_id = {v: k for k, v in client_labels.items()}

with st.sidebar:
    st.header("Configuración")

    selected_label = st.selectbox(
        "Cliente",
        options=list(client_labels.values()),
        index=0,
    )
    client_id = label_to_id[selected_label]

    agent_name = st.radio(
        "Agente",
        ["Coordinador", "Entrenador", "Nutricionista", "Analista"],
        index=0,
    )

    model = st.text_input("Modelo LLM", value=os.getenv("LLM_MODEL", LLM_MODEL))
    use_memory = st.toggle("Usar memoria episódica", value=True)
    show_trace = st.toggle("Mostrar trazabilidad", value=True)

    st.divider()
    st.subheader("Estado")
    st.write("**OpenAI API key:**", "✅ configurada" if os.getenv("OPENAI_API_KEY") else "⚠️ no configurada")
    st.write("**MCP runtime:**", "stdio MCP" if USE_MCP_SERVER else "dispatcher local compatible")
    st.write("**RAG store:**", "✅ detectado" if RAG_STORE_DIR.exists() and any(RAG_STORE_DIR.iterdir()) else "⚠️ no indexado")

    if st.button("Limpiar memoria del cliente"):
        clear_memory(client_id)
        st.session_state.messages = []
        st.success(f"Memoria de {client_id} eliminada.")

    with st.expander("Perfil del cliente"):
        c = next(c for c in clients if c["id"] == client_id)
        st.json(c)

# Estado de chat separado por cliente
state_key = f"messages_{client_id}"
if state_key not in st.session_state:
    st.session_state[state_key] = []

st.subheader(f"Chat con {selected_label}")

if use_memory:
    episodes = load_recent_episodes(client_id, n=8)
    if episodes:
        with st.expander("Memoria reciente del cliente"):
            for ep in episodes:
                st.markdown(f"**{ep.get('role','')} / {ep.get('agent','')}** · {ep.get('ts','')}")
                st.write(ep.get("content", "")[:600])

for message in st.session_state[state_key]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.expander("Entrada por audio opcional"):
    audio_file = st.file_uploader(
        "Sube un audio en español para transcribirlo con Whisper",
        type=["wav", "mp3", "m4a", "ogg", "webm"],
    )
    if st.button("Transcribir audio"):
        texto_audio = transcribir_audio(audio_file)
        if texto_audio:
            st.session_state["prefill_prompt"] = texto_audio
            st.success("Audio transcrito. Copia el texto al chat o úsalo como referencia.")
            st.write(texto_audio)

prefill = st.session_state.pop("prefill_prompt", "") if "prefill_prompt" in st.session_state else ""
prompt = st.chat_input("Escribe tu consulta al sistema multiagente...")

if prompt or prefill:
    user_text = prompt or prefill

    st.session_state[state_key].append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.status("Ejecutando Coordinador / agente seleccionado...", expanded=False):
            result = run_multiagent(
                user_input=user_text,
                client_id=client_id,
                agent_name=agent_name,
                model=model,
                use_memory=use_memory,
            )

        respuesta = result.get("respuesta", "")
        st.markdown(respuesta)

        if show_trace:
            with st.expander("Trazabilidad de ejecución"):
                st.write("**Agente:**", result.get("agente"))
                st.write("**Memoria usada:**", result.get("memoria_usada"))
                st.write("**Tools / subagentes invocados:**")
                st.json(result.get("trace", []))

    st.session_state[state_key].append({"role": "assistant", "content": respuesta})
