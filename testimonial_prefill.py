import os
import runpy
import streamlit as st

from app.config import config

SUBJECT = "Testimonio de una administradora de fincas extremeña que recupera una vivienda cerrada con deudas y devuelve tranquilidad a la comunidad."

SCRIPT = """Mira, este piso llevaba años cerrado, con muchas deudas… y yo ya no sabía por dónde cogerlo.

Pero nos pusimos manos a la obra: hablando claro, ordenando papeles y buscando una solución de verdad.

Y en solo seis meses, deuda cero. Cuando me lo confirmaron… se me saltaron las lágrimas.

Ahora vive aquí una pareja joven con sus dos niños, y el bloque ha vuelto a tener vida.

Eso es lo bonito: recuperar una vivienda, devolver tranquilidad y ver felices a los vecinos. Ha merecido la pena."""

TERMS = """administradora de fincas española de 48 años en oficina cálida del interior de Extremadura, pasillo de edificio residencial antiguo y cuidado en Extremadura, administradora recibiendo una llamada positiva en oficina cálida, familia joven con dos niños entrando en su nuevo hogar, administradora saliendo del edificio al atardecer en una calle tranquila de Extremadura"""

MATERIALS = [
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-1.mp4",
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-2.mp4",
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-3.mp4",
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-4.mp4",
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-5.mp4",
]

config.app["video_source"] = "local"
config.app["llm_provider"] = "pollinations"
config.app["script_generation_backend"] = "local"
config.app["match_materials_to_script"] = True
config.app["subtitle_provider"] = "edge"
config.ui["language"] = "es"
config.ui["video_language"] = "es-ES"
config.ui["paragraph_number"] = 5
config.ui["video_concat_mode"] = "sequential"
config.ui["video_transition_mode"] = "FadeIn"
config.ui["video_aspect_local"] = "9:16"
config.ui["video_fit_mode"] = "cover"
config.ui["video_clip_duration"] = 8
config.ui["video_clip_speed"] = 1.0
config.ui["video_count"] = 1
config.ui["voice_mode"] = "tts"
config.ui["tts_server"] = "azure-tts-v1"
config.ui["voice_name"] = "es-ES-ElviraNeural-Female"
config.ui["voice_volume"] = 1.0
config.ui["voice_rate"] = 1.1
config.ui["bgm_type"] = ""
config.ui["bgm_volume"] = 0.0
config.ui["subtitle_enabled"] = False
config.ui["open_task_folder_on_completion"] = False

st.session_state.setdefault("ui_language", "es")
st.session_state.setdefault("video_subject", SUBJECT)
st.session_state.setdefault("video_script", SCRIPT)
st.session_state.setdefault("video_terms", TERMS)
st.session_state.setdefault("match_materials_to_script", True)
st.session_state.setdefault(
    "local_video_materials",
    [{"provider": "local", "url": path, "duration": 12} for path in MATERIALS],
)

runpy.run_path("/MoneyPrinterTurbo/webui/Main.py", run_name="__main__")
