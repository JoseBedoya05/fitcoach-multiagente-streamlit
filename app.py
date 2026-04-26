from __future__ import annotations

import hashlib
import io
import os
import re
import tempfile
import unicodedata
import wave
from pathlib import Path

try:
    import audioop  # Disponible en Python 3.11; permite medir energía RMS del audio WAV.
except Exception:  # pragma: no cover
    audioop = None

import streamlit as st

# -----------------------------------------------------------------------------
# Configuración inicial
# -----------------------------------------------------------------------------
# Permite leer variables desde Streamlit Cloud secrets.
try:
    if "OPENAI_API_KEY" in st.secrets and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    if "LLM_MODEL" in st.secrets:
        os.environ["LLM_MODEL"] = st.secrets["LLM_MODEL"]
    if "TRANSCRIPTION_MODEL" in st.secrets:
        os.environ["TRANSCRIPTION_MODEL"] = st.secrets["TRANSCRIPTION_MODEL"]
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
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Parámetros de audio
# -----------------------------------------------------------------------------
MIN_AUDIO_DURATION_SECONDS = 1.0
MIN_AUDIO_RMS_RATIO = 0.0015
TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "whisper-1")

SPURIOUS_TRANSCRIPT_PATTERNS = [
    "subtitulos realizados por la comunidad de amara.org",
    "subtítulos realizados por la comunidad de amara.org",
    "subtitulado por la comunidad de amara.org",
    "amara.org",
    "gracias por ver el video",
    "gracias por ver",
]

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
        .soft-note {
            padding: 0.8rem 1rem;
            border-left: 4px solid rgba(52, 211, 153, 0.80);
            border-radius: 0.7rem;
            background: rgba(52, 211, 153, 0.08);
            margin: 0.5rem 0 1rem;
        }
        .warning-note {
            padding: 0.8rem 1rem;
            border-left: 4px solid rgba(245, 158, 11, 0.90);
            border-radius: 0.7rem;
            background: rgba(245, 158, 11, 0.08);
            margin: 0.5rem 0 1rem;
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
# Utilidades de audio y transcripción
# -----------------------------------------------------------------------------
def _audio_to_bytes(audio_value) -> bytes:
    """Convierte el valor de st.audio_input a bytes sin depender del cursor interno."""
    if audio_value is None:
        return b""
    if hasattr(audio_value, "getvalue"):
        return audio_value.getvalue()
    return audio_value.read()


def capturar_audio_microfono(*, label: str, key: str, help_text: str = ""):
    """Captura audio del micrófono con compatibilidad entre versiones de Streamlit."""
    if hasattr(st, "audio_input"):
        return st.audio_input(
            label,
            sample_rate=16000,
            key=key,
            help=help_text,
        )

    if hasattr(st, "experimental_audio_input"):
        st.info(
            "Tu versión de Streamlit usa `st.experimental_audio_input`. "
            "La app seguirá funcionando, pero se recomienda actualizar Streamlit."
        )
        return st.experimental_audio_input(
            label,
            key=key,
            help=help_text,
        )

    st.error(
        "La versión instalada de Streamlit no soporta captura de audio desde micrófono. "
        "Actualiza `streamlit` en requirements.txt, por ejemplo: `streamlit>=1.45.1`."
    )
    return None


def _normalizar_texto_validacion(texto: str) -> str:
    texto = texto.strip().lower()
    texto = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    texto = re.sub(r"\s+", " ", texto)
    return texto


def es_transcripcion_espuria(texto: str) -> bool:
    """Detecta frases típicas alucinadas por transcriptores cuando hay silencio."""
    if not texto or not texto.strip():
        return True
    texto_norm = _normalizar_texto_validacion(texto)
    patrones_norm = [_normalizar_texto_validacion(p) for p in SPURIOUS_TRANSCRIPT_PATTERNS]
    return any(p in texto_norm for p in patrones_norm)


def analizar_audio_wav(audio_bytes: bytes) -> dict:
    """Calcula duración y energía RMS de un WAV grabado desde el navegador."""
    info = {
        "is_wav": False,
        "duration_seconds": None,
        "sample_rate": None,
        "channels": None,
        "sample_width": None,
        "rms_ratio": None,
    }
    if not audio_bytes:
        return info

    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            frames = wav_file.readframes(n_frames)

        duration = n_frames / float(sample_rate) if sample_rate else 0.0
        rms_ratio = None
        if audioop is not None and frames and sample_width:
            rms = audioop.rms(frames, sample_width)
            max_amplitude = float(2 ** (8 * sample_width - 1))
            rms_ratio = rms / max_amplitude if max_amplitude else None

        info.update(
            {
                "is_wav": True,
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "sample_width": sample_width,
                "rms_ratio": rms_ratio,
            }
        )
        return info
    except Exception:
        return info


def validar_audio_para_transcripcion(audio_bytes: bytes) -> tuple[bool, str, dict]:
    """Valida duración y volumen mínimo para evitar transcribir silencio."""
    if not audio_bytes or len(audio_bytes) < 1500:
        return False, "No se detectó audio suficiente. Graba de nuevo hablando cerca del micrófono.", {}

    info = analizar_audio_wav(audio_bytes)
    if info.get("is_wav"):
        duration = info.get("duration_seconds") or 0.0
        rms_ratio = info.get("rms_ratio")

        if duration < MIN_AUDIO_DURATION_SECONDS:
            return (
                False,
                f"El audio dura {duration:.1f} s. Graba al menos {MIN_AUDIO_DURATION_SECONDS:.0f} segundo con voz clara.",
                info,
            )

        if rms_ratio is not None and rms_ratio < MIN_AUDIO_RMS_RATIO:
            return (
                False,
                "El audio parece estar en silencio o con volumen muy bajo. Revisa permisos del micrófono y graba de nuevo.",
                info,
            )

    return True, "", info


def transcribir_audio(audio_value) -> str:
    """Transcribe audio capturado desde micrófono con la API de OpenAI."""
    if audio_value is None:
        return ""

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        st.warning("Para transcribir audio debes configurar OPENAI_API_KEY en variables de entorno o secrets.")
        return ""

    audio_bytes = _audio_to_bytes(audio_value)
    audio_ok, audio_msg, audio_info = validar_audio_para_transcripcion(audio_bytes)

    if audio_info.get("is_wav"):
        duration = audio_info.get("duration_seconds")
        rms_ratio = audio_info.get("rms_ratio")
        if duration is not None:
            nivel = "no disponible" if rms_ratio is None else f"{rms_ratio:.4f}"
            st.caption(f"Audio detectado: {duration:.1f} s · nivel RMS relativo: {nivel}")

    if not audio_ok:
        st.warning(audio_msg)
        return ""

    suffix = Path(getattr(audio_value, "name", "audio.wav")).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        with open(tmp_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model=TRANSCRIPTION_MODEL,
                file=f,
                language="es",
                temperature=0,
                prompt=(
                    "Transcribe únicamente voz hablada en español. "
                    "Si el audio está en silencio, no contiene voz clara o solo hay ruido, "
                    "no inventes subtítulos ni frases genéricas."
                ),
            )

        text = getattr(transcription, "text", "") or ""
        text = text.strip()

        if es_transcripcion_espuria(text):
            st.warning(
                "La transcripción fue descartada porque parece generada por silencio, ruido "
                "o ausencia de voz clara. Graba nuevamente hablando cerca del micrófono."
            )
            return ""

        return text

    except Exception as exc:
        st.error(f"No fue posible transcribir el audio: {exc}")
        return ""
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Utilidades de ejecución multiagente
# -----------------------------------------------------------------------------
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
    st.write("**Modelo transcripción:**", TRANSCRIPTION_MODEL)
    st.write("**MCP runtime:**", "stdio MCP" if USE_MCP_SERVER else "dispatcher local compatible")
    st.write("**RAG store:**", "✅ detectado" if rag_ok else "⚠️ no indexado")

    if st.button("Limpiar memoria del cliente", use_container_width=True):
        clear_memory(client_id)
        st.session_state[state_key] = []
        st.success(f"Memoria de {client_id} eliminada.")

    with st.expander("Perfil del cliente", expanded=False):
        current_client = next(c for c in clients if c["id"] == client_id)
        st.json(current_client)

# -----------------------------------------------------------------------------
# Estado de sesión
# -----------------------------------------------------------------------------
if state_key not in st.session_state:
    st.session_state[state_key] = []

voice_draft_key = f"voice_draft_{client_id}"
audio_hash_key = f"last_audio_hash_{client_id}"
voice_editor_version_key = f"voice_editor_version_{client_id}"

if voice_draft_key not in st.session_state:
    st.session_state[voice_draft_key] = ""
if audio_hash_key not in st.session_state:
    st.session_state[audio_hash_key] = ""
if voice_editor_version_key not in st.session_state:
    st.session_state[voice_editor_version_key] = 0

# -----------------------------------------------------------------------------
# Layout principal
# -----------------------------------------------------------------------------
left_col, right_col = st.columns([0.67, 0.33], gap="large")

with right_col:
    st.subheader("Entrada por voz")
    st.markdown(
        """
        <div class="soft-note">
            Graba la consulta desde el micrófono del dispositivo. Habla al menos 1 segundo, cerca del micrófono y revisa que el navegador tenga permisos de audio.
        </div>
        """,
        unsafe_allow_html=True,
    )

    mic_audio = capturar_audio_microfono(
        label="Grabar consulta en español",
        key=f"mic_audio_{client_id}",
        help_text="Permite el acceso al micrófono en el navegador cuando Streamlit lo solicite.",
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
                st.session_state[voice_draft_key] = transcript
                st.session_state[voice_editor_version_key] += 1
                st.success("Audio transcrito correctamente.")
            else:
                st.info("No se obtuvo texto útil del audio. Intenta grabar de nuevo con voz más clara.")

    edited_voice_text = st.text_area(
        "Texto transcrito editable",
        value=st.session_state[voice_draft_key],
        height=160,
        placeholder="Aquí aparecerá la transcripción del audio...",
        key=f"voice_editor_{client_id}_{st.session_state[voice_editor_version_key]}",
    )

    send_voice = st.button(
        "Enviar audio transcrito",
        type="primary",
        use_container_width=True,
        disabled=not edited_voice_text.strip(),
    )

    if st.button("Borrar transcripción", use_container_width=True):
        st.session_state[voice_draft_key] = ""
        st.session_state[voice_editor_version_key] += 1
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
        st.session_state[voice_draft_key] = ""
        st.session_state[voice_editor_version_key] += 1
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
