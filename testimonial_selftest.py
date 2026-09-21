import json
import os
import uuid

from app.models import const
from app.models.schema import MaterialInfo, VideoParams
from app.services import state as sm
from app.services import task

SUBJECT = "Testimonio de una administradora de fincas extremeña que recupera una vivienda cerrada con deudas y devuelve tranquilidad a la comunidad."
SCRIPT = """Mira, este piso llevaba años cerrado, con muchas deudas… y yo ya no sabía por dónde cogerlo.

Pero nos pusimos manos a la obra: hablando claro, ordenando papeles y buscando una solución de verdad.

Y en solo seis meses, deuda cero. Cuando me lo confirmaron… se me saltaron las lágrimas.

Ahora vive aquí una pareja joven con sus dos niños, y el bloque ha vuelto a tener vida.

Eso es lo bonito: recuperar una vivienda, devolver tranquilidad y ver felices a los vecinos. Ha merecido la pena."""

MATERIAL_PATHS = [
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-1.mp4",
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-2.mp4",
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-3.mp4",
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-4.mp4",
    "/MoneyPrinterTurbo/storage/local_videos/testimonial-scene-5.mp4",
]


materials = [MaterialInfo(provider="local", url=p, duration=12) for p in MATERIAL_PATHS]
params = VideoParams(
    video_subject=SUBJECT,
    video_script=SCRIPT,
    video_terms="",
    video_aspect="9:16",
    video_fit_mode="cover",
    video_concat_mode="sequential",
    video_transition_mode="FadeIn",
    video_clip_duration=8,
    video_clip_speed=1.0,
    match_materials_to_script=True,
    video_count=1,
    video_source="local",
    video_materials=materials,
    video_language="es-ES",
    voice_name="es-ES-ElviraNeural-Female",
    voice_volume=1.0,
    voice_rate=1.1,
    bgm_type="",
    bgm_volume=0.0,
    subtitle_enabled=False,
    paragraph_number=5,
)
task_id = str(uuid.uuid4())
sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=0, video_subject=SUBJECT)
result = task.start(task_id, params)
state = sm.state.get_task(task_id)
print(json.dumps({"result": result, "state": state}, ensure_ascii=False, default=str))
if not result or not result.get("videos") or state.get("state") != const.TASK_STATE_COMPLETE:
    raise SystemExit(1)
for path in result["videos"]:
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise SystemExit(1)
print("TESTIMONIAL_SELFTEST_OK")
