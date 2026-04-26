from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import streamlit as st

# -----------------------------------------------------------------------------
# Configuración inicial
# -----------------------------------------------------------------------------
# Permite leer OPENAI_API_KEY y LLM_MODEL desde Streamlit Cloud secrets.
try:
    if "OPENAI_API_KEY" in st.secrets and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    if "LLM_MODEL" in st.secrets:
        os.environ["LLM_MODEL"] = st.secrets["LLM_MODEL"]
except Exception:
    # En ejecución local puede no existir st.secrets o no tener estas claves.
    pass

from src.config import LLM_MODEL, RAG_STORE_DIR, USE_MCP_SERVER
from src.core.multiagent_runner import run_multiagent
from src.mcp_tools.local_tools import list_clients
from src.memory.client_memory import clear_memory, load_recent_episodes


st.set_page_config(
    page_title="FitCoach AI | Sistema Multiagente MCP",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Estilos visuales
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1180px;
        }
        .hero-card {
            padding: 1.4rem 1.6rem;
            border: 1px solid rgba(120, 120, 120, 0.20);
            border-radius: 1.1rem;
            background: linear-gradient(135deg, rgba(52, 211, 153, 0.12), rgba(59, 130, 246, 0.10));
            margin-bottom: 1.2rem;
        }
        .hero-card h1 {
            margin: 0;
            font-size: 2rem;
            letter-spacing: -0.03em;
        }
        .hero-card p {
            margin: 0.45rem 0 0;
            opacity: 0.82;
            font-size: 1rem;
        }
        .metric-card {
            padding: 0.9rem 1rem;
            border: 1px solid rgba(120, 120, 120, 0.20);
            border-radius: 0.9rem;
            background: rgba(250, 250, 250, 0.04);
        }
        .soft-note {
            padding: 0.8rem 1rem;
            border-left: 4px solid rgba(52, 211, 153, 0.80);
            border-radius: 0.7rem;
            background: rgba(52, 211, 153, 0.08);
            margin: 0.5rem 0 1rem;
        }
        div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] h3 {
            letter-spacing: -0.02em;
        }
        .stButton>button {
            border-radius: 0.7rem;
            font-weight: 600;
        }
        textarea {
            border-radius: 0.8rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
def _audio_to_bytes(audio_value) -> bytes:
    """Convierte el valor de st.audio_input a bytes sin depender del cursor interno."""
    if audio_value is None:
        return b""
    if hasattr(audio_value, "getvalue"):
        return audio_value.getvalue()
    return audio_value.read()


def transcribir_audio(audio_value) -> str:
    """Transcribe audio capturado desde el micrófono con Whisper API de OpenAI."""
    if audio_value is None:
        return ""

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("Para transcribir audio debes configurar OPENAI_API_KEY en variables de entorno o secrets.")
        return ""

    audio_bytes = _audio_to_bytes(audio_value)
    if not audio_bytes:
        return ""

    # st.audio_input entrega audio/wav. Se usa .wav para compatibilidad con Whisper.
    suffix = Path(getattr(audio_value, "name", "audio.wav")).suffix or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        with open(tmp_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="es",
            )
        return transcription.text.strip()
    except Exception as exc:
        st.error(f"No fue posible transcribir el audio: {exc}")
        return ""
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def ejecutar_consulta(
    *,
    user_text: str,
    client_id: str,
    agent_name: str,
    model: str,
    use_memory: bool,
    show_trace: bool,
    state_key: str,
) -> None:
    """Agrega la consulta al chat, ejecuta el sistema multiagente y renderiza la respuesta."""
    clean_text = user_text.strip()
    if not clean_text:
        return

    st.session_state[state_key].append({"role": "user", "content": clean_text})

    with st.chat_message("user"):
        st.markdown(clean_text)

    with st.chat_message("assistant"):
        with st.status("Ejecutando Coordinador / agente seleccionado...", expanded=False):
            result = run_multiagent(
                user_input=clean_text,
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


# -----------------------------------------------------------------------------
# Cabecera
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-card">
        <h1>🏋️ FitCoach AI — Sistema Multiagente con MCP</h1>
        <p>Coordinador, agentes especializados, herramientas MCP, RAG y memoria episódica por cliente.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Sidebar de configuración
# -----------------------------------------------------------------------------
clients = list_clients()
if not clients:
    st.error("No hay clientes disponibles. Revisa la fuente de perfiles en src/mcp_tools/local_tools.py.")
    st.stop()

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
    state_key = f"messages_{client_id}"

    agent_name = st.radio(
        "Agente",
        ["Coordinador", "Entrenador", "Nutricionista", "Analista"],
        index=0,
        horizontal=False,
    )

    model = st.text_input("Modelo LLM", value=os.getenv("LLM_MODEL", LLM_MODEL))
    use_memory = st.toggle("Usar memoria episódica", value=True)
    show_trace = st.toggle("Mostrar trazabilidad", value=True)

    st.divider()
    st.subheader("Estado del sistema")

    key_ok = bool(os.getenv("OPENAI_API_KEY"))
    rag_ok = RAG_STORE_DIR.exists() and any(RAG_STORE_DIR.iterdir())

    st.write("**OpenAI API key:**", "✅ configurada" if key_ok else "⚠️ no configurada")
    st.write("**MCP runtime:**", "stdio MCP" if USE_MCP_SERVER else "dispatcher local compatible")
    st.write("**RAG store:**", "✅ detectado" if rag_ok else "⚠️ no indexado")

    if st.button("Limpiar memoria del cliente", use_container_width=True):
        clear_memory(client_id)
        st.session_state[state_key] = []
        st.success(f"Memoria de {client_id} eliminada.")

    with st.expander("Perfil del cliente", expanded=False):
        current_client = next(c for c in clients if c["id"] == client_id)
        st.json(current_client)


# Estado de chat separado por cliente
if state_key not in st.session_state:
    st.session_state[state_key] = []

voice_text_key = f"voice_text_{client_id}"
audio_hash_key = f"last_audio_hash_{client_id}"

if voice_text_key not in st.session_state:
    st.session_state[voice_text_key] = ""
if audio_hash_key not in st.session_state:
    st.session_state[audio_hash_key] = ""


# -----------------------------------------------------------------------------
# Layout principal
# -----------------------------------------------------------------------------
left_col, right_col = st.columns([0.67, 0.33], gap="large")

with right_col:
    st.subheader("Entrada por voz")
    st.markdown(
        """
        <div class="soft-note">
            Graba la consulta desde el micrófono del dispositivo. Al terminar, el audio se transcribe y puedes editarlo antes de enviarlo.
        </div>
        """,
        unsafe_allow_html=True,
    )

    mic_audio = st.audio_input(
        "Grabar consulta en español",
        sample_rate=16000,
        key=f"mic_audio_{client_id}",
        help="Permite el acceso al micrófono en el navegador cuando Streamlit lo solicite.",
    )

    if mic_audio is not None:
        audio_bytes = _audio_to_bytes(mic_audio)
        audio_hash = hashlib.sha256(audio_bytes).hexdigest()

        st.audio(audio_bytes, format="audio/wav")

        if audio_hash != st.session_state[audio_hash_key]:
            with st.spinner("Transcribiendo audio..."):
                transcript = transcribir_audio(mic_audio)
            st.session_state[audio_hash_key] = audio_hash
            if transcript:
                st.session_state[voice_text_key] = transcript
                st.success("Audio transcrito correctamente.")

    edited_voice_text = st.text_area(
        "Texto transcrito editable",
        height=160,
        placeholder="Aquí aparecerá la transcripción del audio...",
        key=voice_text_key,
    )

    send_voice = st.button(
        "Enviar audio transcrito",
        type="primary",
        use_container_width=True,
        disabled=not edited_voice_text.strip(),
    )

    if st.button("Borrar transcripción", use_container_width=True):
        st.session_state[voice_text_key] = ""
        st.rerun()

    st.divider()
    st.subheader("Memoria reciente")
    if use_memory:
        episodes = load_recent_episodes(client_id, n=8)
        if episodes:
            with st.expander("Ver episodios", expanded=False):
                for ep in episodes:
                    st.markdown(f"**{ep.get('role','')} / {ep.get('agent','')}** · {ep.get('ts','')}")
                    st.write(ep.get("content", "")[:600])
        else:
            st.caption("Sin episodios recientes para este cliente.")
    else:
        st.caption("Memoria desactivada para esta ejecución.")


with left_col:
    st.subheader(f"Chat con {selected_label}")

    for message in st.session_state[state_key]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if send_voice:
        ejecutar_consulta(
            user_text=edited_voice_text,
            client_id=client_id,
            agent_name=agent_name,
            model=model,
            use_memory=use_memory,
            show_trace=show_trace,
            state_key=state_key,
        )
        st.session_state[voice_text_key] = ""
        st.rerun()
    prompt = st.chat_input("Escribe tu consulta al sistema multiagente...")
    if prompt:
        ejecutar_consulta(
            user_text=prompt,
            client_id=client_id,
            agent_name=agent_name,
            model=model,
            use_memory=use_memory,
            show_trace=show_trace,
            state_key=state_key,
        )
