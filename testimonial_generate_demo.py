import json
import shutil
from pathlib import Path

from app.config import config
from app.models.schema import (
    MaterialInfo,
    VideoAspect,
    VideoConcatMode,
    VideoFitMode,
    VideoParams,
    VideoTransitionMode,
)
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

for item in MATERIAL_PATHS:
    if not Path(item).is_file():
        raise SystemExit(f"missing material: {item}")

config.app["subtitle_provider"] = "edge"
config.app["video_source"] = "local"
config.app["match_materials_to_script"] = True

materials = [
    MaterialInfo(provider="local", url=path, duration=12)
    for path in MATERIAL_PATHS
]

params = VideoParams(
    video_subject=SUBJECT,
    video_script=SCRIPT,
    video_terms="administradora de fincas, vivienda cerrada, comunidad de vecinos, familia joven, edificio residencial",
    video_source="local",
    video_materials=materials,
    video_language="es-ES",
    video_aspect=VideoAspect.portrait,
    video_fit_mode=VideoFitMode.cover,
    video_concat_mode=VideoConcatMode.sequential,
    video_transition_mode=VideoTransitionMode.fade_in,
    video_clip_duration=8,
    video_clip_speed=1.0,
    match_materials_to_script=True,
    video_count=1,
    voice_name="es-ES-ElviraNeural-Female",
    voice_volume=1.0,
    voice_rate=1.1,
    bgm_type="",
    bgm_file="",
    bgm_volume=0.0,
    subtitle_enabled=False,
    paragraph_number=5,
)

task_id = "testimonial-demo"
sm.state.update_task(task_id)
result = task.start(task_id=task_id, params=params)
print(json.dumps(result, ensure_ascii=False, default=str, indent=2))

videos = (result or {}).get("videos") or []
if not videos:
    state = sm.state.get_task(task_id)
    print(json.dumps(state, ensure_ascii=False, default=str, indent=2))
    raise SystemExit("MoneyPrinterTurbo did not generate a final video")

source = Path(videos[0])
if not source.is_file() or source.stat().st_size == 0:
    raise SystemExit(f"invalid final video: {source}")

output = Path("/output/testimonial-demo.mp4")
output.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(source, output)
print(f"FINAL_VIDEO={output}")
