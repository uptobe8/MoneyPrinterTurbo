from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import requests
from moviepy import AudioFileClip, VideoFileClip
import imageio_ffmpeg

ROOT = Path.cwd()
OUT = ROOT / "storage" / "testimonial_v1_assets"
OUT.mkdir(parents=True, exist_ok=True)

WS_KEY = os.environ["WAVESPEED_API_KEY"].strip()
PEXELS_KEY = os.environ["PEXELS_API_KEY"].strip()
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
WS_BASE = "https://api.wavespeed.ai/api/v3"
HEADERS = {"Authorization": f"Bearer {WS_KEY}", "Content-Type": "application/json"}

SCENES = [
    ("scene1", 6.0, "Este piso llevaba muchísimo tiempo abandonado… y tenía una deuda que parecía imposible de resolver.", "neutral"),
    ("scene2", 9.0, "La comunidad ya no sabía qué hacer. Cada mes que pasaba, el problema iba creciendo.", "neutral"),
    ("scene3", 9.0, "Pero nos pusimos manos a la obra y, en solo seis meses, conseguimos solucionarlo todo. Hoy ese piso ya no tiene ninguna deuda.", "happy"),
    ("scene4", 7.0, "Y ahora viven aquí una pareja joven con sus dos niños. Da gusto ver cómo un problema tan grande se ha convertido en un nuevo comienzo.", "happy"),
    ("scene5", 4.0, "Para mí, eso es lo más bonito de este trabajo.", "happy"),
]


def wait_prediction(prediction_id: str, timeout: int = 1200):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(
            f"{WS_BASE}/predictions/{prediction_id}/result",
            headers={"Authorization": f"Bearer {WS_KEY}"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json().get("data", r.json())
        status = data.get("status")
        if status == "completed":
            outputs = data.get("outputs") or []
            if not outputs:
                raise RuntimeError(f"WaveSpeed task {prediction_id} completed without output")
            return outputs[0]
        if status in {"failed", "cancelled", "timeout", "deleted"}:
            raise RuntimeError(f"WaveSpeed task {prediction_id} failed: {data.get('error')}")
        time.sleep(3)
    raise TimeoutError(f"WaveSpeed task {prediction_id} did not finish")


def ws_run(model: str, payload: dict, timeout: int = 1200):
    r = requests.post(f"{WS_BASE}/{model}", headers=HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json().get("data", r.json())
    pid = data.get("id")
    if not pid:
        raise RuntimeError(f"WaveSpeed did not return prediction id: {r.text[:500]}")
    return wait_prediction(pid, timeout=timeout)


def download(url: str, path: Path):
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
    if not path.exists() or path.stat().st_size < 1000:
        raise RuntimeError(f"Downloaded file is invalid: {path}")


def upload_media(path: Path):
    with path.open("rb") as f:
        r = requests.post(
            f"{WS_BASE}/media/upload/binary",
            headers={"Authorization": f"Bearer {WS_KEY}"},
            files={"file": (path.name, f)},
            timeout=300,
        )
    r.raise_for_status()
    data = r.json().get("data", r.json())
    url = data.get("download_url")
    if not url:
        raise RuntimeError(f"WaveSpeed upload did not return download_url: {r.text[:500]}")
    return url


def run_ffmpeg(args: list[str]):
    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args]
    subprocess.run(cmd, check=True)


def audio_duration(path: Path):
    clip = AudioFileClip(str(path))
    d = float(clip.duration)
    clip.close()
    return d


def atempo_chain(rate: float):
    factors = []
    while rate > 2.0:
        factors.append(2.0)
        rate /= 2.0
    while rate < 0.5:
        factors.append(0.5)
        rate /= 0.5
    factors.append(rate)
    return ",".join(f"atempo={x:.8f}" for x in factors)


def fit_audio(src: Path, dst: Path, target: float):
    dur = audio_duration(src)
    rate = dur / target
    filt = atempo_chain(rate) + ",apad"
    run_ffmpeg(["-i", str(src), "-filter:a", filt, "-t", f"{target:.3f}", "-ar", "44100", "-ac", "1", str(dst)])


def normalize_video(src: Path, dst: Path, target: float):
    run_ffmpeg([
        "-stream_loop", "-1", "-i", str(src), "-t", f"{target:.3f}",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(dst),
    ])


def pexels_clip(query: str, dst: Path):
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_KEY},
        params={"query": query, "orientation": "portrait", "per_page": 30},
        timeout=60,
    )
    r.raise_for_status()
    videos = r.json().get("videos") or []
    candidates = []
    for video in videos:
        for vf in video.get("video_files") or []:
            w = vf.get("width") or 0
            h = vf.get("height") or 0
            link = vf.get("link")
            if link and h > w and h >= 960:
                candidates.append((w * h, link))
    if not candidates:
        raise RuntimeError(f"No portrait Pexels clip found for {query}")
    candidates.sort(reverse=True)
    download(candidates[0][1], dst)


print("Generating consistent protagonist frames")
base_image_url = ws_run(
    "wavespeed-ai/z-image/turbo",
    {
        "prompt": "Hyperrealistic cinematic vertical photograph of a Spanish female property manager age 48 to 52 from inland Extremadura, warm trustworthy face, medium brown shoulder-length hair, beige blazer over white blouse, dark jeans, simple professional style, walking naturally inside the entrance hall of a Spanish apartment building with old metal mailboxes and traditional ceramic tile details, warm natural daylight, candid real testimonial look, subtle handheld documentary feel, realistic skin texture, no text, no logos, no glamour retouching, vertical 9:16 composition",
        "size": "768*1365",
        "seed": 1981,
        "output_format": "jpeg",
    },
)
scene3_image_url = ws_run(
    "wavespeed-ai/z-image-turbo/image-to-image",
    {
        "image": base_image_url,
        "prompt": "same woman, identical face hair age clothing and identity, seated naturally at a modest property management office desk in inland Extremadura, looking directly at camera, warm relieved smile, hands making a subtle natural explanatory gesture, folders and laptop on desk, natural window light, candid documentary testimonial frame, realistic skin, no text, vertical 9:16",
        "size": "768*1365",
        "strength": 0.35,
        "seed": 1981,
        "output_format": "jpeg",
    },
)
scene5_image_url = ws_run(
    "wavespeed-ai/z-image-turbo/image-to-image",
    {
        "image": base_image_url,
        "prompt": "same woman, identical face hair age clothing and identity, close-up portrait in the same Spanish apartment building entrance hall, looking directly at camera, visibly proud and gently emotional, subtle sincere smile, warm natural light, shallow cinematic depth of field, realistic skin, candid documentary testimonial, no text, vertical 9:16",
        "size": "768*1365",
        "strength": 0.3,
        "seed": 1981,
        "output_format": "jpeg",
    },
)

print("Generating natural Spanish voice")
voice_files = {}
for name, target, text, emotion in SCENES:
    url = ws_run(
        "minimax/speech-2.6-turbo",
        {
            "text": text,
            "voice_id": "Calm_Woman",
            "speed": 0.96,
            "volume": 1,
            "pitch": -1,
            "emotion": emotion,
            "english_normalization": False,
            "sample_rate": 44100,
            "bitrate": 128000,
            "channel": "1",
            "format": "mp3",
            "language_boost": "Spanish",
        },
    )
    raw = OUT / f"{name}-raw.mp3"
    fitted = OUT / f"{name}-voice.wav"
    download(url, raw)
    fit_audio(raw, fitted, target)
    voice_files[name] = fitted

print("Generating lip-synced testimonial scenes")
image_urls = {"scene1": base_image_url, "scene3": scene3_image_url, "scene5": scene5_image_url}
for name in ("scene1", "scene3", "scene5"):
    audio_url = upload_media(voice_files[name])
    video_url = ws_run(
        "wavespeed-ai/wan-2.2/speech-to-video",
        {"image": image_urls[name], "audio": audio_url, "resolution": "480p"},
        timeout=1800,
    )
    raw = OUT / f"{name}-s2v-raw.mp4"
    download(video_url, raw)
    target = next(s[1] for s in SCENES if s[0] == name)
    normalize_video(raw, OUT / f"{name}.mp4", target)

print("Downloading narrative-matched B-roll")
pexels_clip("apartment building mailboxes paperwork documents property management", OUT / "scene2-raw.mp4")
pexels_clip("young family parents two children entering apartment building new home", OUT / "scene4-raw.mp4")
normalize_video(OUT / "scene2-raw.mp4", OUT / "scene2.mp4", 9.0)
normalize_video(OUT / "scene4-raw.mp4", OUT / "scene4.mp4", 7.0)

print("Building exact 35-second voice track")
concat_file = OUT / "audio-concat.txt"
concat_file.write_text("\n".join(f"file '{voice_files[f'scene{i}'].as_posix()}'" for i in range(1, 6)) + "\n", encoding="utf-8")
full_audio = OUT / "full-voice.wav"
run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_file), "-c:a", "pcm_s16le", str(full_audio)])

manifest = {
    "clips": [str(OUT / f"scene{i}.mp4") for i in range(1, 6)],
    "audio": str(full_audio),
    "script": "\n\n".join(scene[2] for scene in SCENES),
}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False))
