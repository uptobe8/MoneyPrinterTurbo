from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
import requests
from moviepy import AudioFileClip

ROOT = Path.cwd()
OUT = ROOT / "storage" / "testimonial_v1_assets_v3"
OUT.mkdir(parents=True, exist_ok=True)

WS_KEY = os.environ["WAVESPEED_API_KEY"].strip()
PEXELS_KEY = os.environ["PEXELS_API_KEY"].strip()
WS_BASE = "https://api.wavespeed.ai/api/v3"
HEADERS = {"Authorization": f"Bearer {WS_KEY}", "Content-Type": "application/json"}
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

REF_IMAGES = {
    "scene1": "https://d2h7xmz5gqybh9.cloudfront.net/output/31e5f02e-6aca-488c-af24-37631d897577-u2_cda3fad8-7448-4e5b-b052-bd4fabf98729.jpeg",
    "scene3": "https://d2h7xmz5gqybh9.cloudfront.net/output/a9d5e62d-fa38-43b7-93aa-955183a183ff-u1_61081073-b148-4ef5-b567-6deef3f94f78.jpeg",
    "scene5": "https://d2h7xmz5gqybh9.cloudfront.net/output/d3ea50df-afd8-43c6-ae07-8c3ac8f57689-u1_2f98ae1d-0064-471e-8de8-48a9f761201b.jpeg",
}

SCENES = [
    ("scene1", 6.0, "Este piso llevaba muchísimo tiempo abandonado… y tenía una deuda que parecía imposible de resolver."),
    ("scene2", 9.0, "La comunidad ya no sabía qué hacer. Cada mes que pasaba, el problema iba creciendo."),
    ("scene3", 9.0, "Pero nos pusimos manos a la obra y, en solo seis meses, conseguimos solucionarlo todo. Hoy ese piso ya no tiene ninguna deuda."),
    ("scene4", 7.0, "Y ahora viven aquí una pareja joven con sus dos niños. Da gusto ver cómo un problema tan grande se ha convertido en un nuevo comienzo."),
    ("scene5", 4.0, "Para mí, eso es lo más bonito de este trabajo."),
]

DIRECT_PROMPTS = {
    "scene1": "Natural Spanish female property manager, about 50, speaking sincerely to camera in an apartment building entrance, subtle breathing and hand gestures, warm natural light, documentary testimonial, restrained emotion, realistic face motion, gentle handheld camera feel.",
    "scene3": "Same Spanish female property manager speaking directly to camera from her office, authentic satisfied smile, subtle breathing, natural eye contact and small hand gestures, warm daylight, documentary testimonial, realistic facial motion, no acting exaggeration.",
    "scene5": "Same Spanish female property manager in a close-up, speaking directly to camera with quiet pride and restrained emotion, slight spontaneous smile, natural breathing and eye movement, warm cinematic daylight, highly realistic documentary testimonial.",
}


def request_json(method: str, url: str, **kwargs):
    r = requests.request(method, url, timeout=kwargs.pop("timeout", 60), **kwargs)
    if not r.ok:
        body = r.text[:4000]
        raise RuntimeError(f"HTTP {r.status_code} from {url}: {body}")
    return r.json()


def wait_prediction(prediction_id: str, timeout: int = 1800):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = request_json(
            "GET",
            f"{WS_BASE}/predictions/{prediction_id}/result",
            headers={"Authorization": f"Bearer {WS_KEY}"},
            timeout=30,
        )
        data = body.get("data", body)
        status = data.get("status")
        if status == "completed":
            outputs = data.get("outputs") or []
            if not outputs:
                raise RuntimeError(f"Prediction {prediction_id} completed without outputs")
            return outputs[0]
        if status in {"failed", "cancelled", "timeout", "deleted"}:
            raise RuntimeError(f"Prediction {prediction_id} failed: {json.dumps(data, ensure_ascii=False)[:4000]}")
        time.sleep(3)
    raise TimeoutError(f"Prediction {prediction_id} timed out")


def ws_run(model: str, payload: dict, timeout: int = 1800):
    waits = [12, 20, 30, 45, 60]
    for attempt in range(len(waits) + 1):
        r = requests.post(f"{WS_BASE}/{model}", headers=HEADERS, json=payload, timeout=60)
        if r.status_code == 429 and attempt < len(waits):
            time.sleep(waits[attempt])
            continue
        if not r.ok:
            raise RuntimeError(f"WaveSpeed {model} HTTP {r.status_code}: {r.text[:4000]}")
        data = r.json().get("data", r.json())
        pid = data.get("id")
        if not pid:
            raise RuntimeError(f"WaveSpeed {model} returned no prediction id: {r.text[:2000]}")
        return wait_prediction(pid, timeout)
    raise RuntimeError(f"WaveSpeed {model} remained rate limited")


def download(url: str, path: Path):
    with requests.get(url, stream=True, timeout=300) as r:
        if not r.ok:
            raise RuntimeError(f"Download HTTP {r.status_code}: {url}")
        with path.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
    if path.stat().st_size < 1000:
        raise RuntimeError(f"Invalid download {path}")


def upload_media(path: Path):
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    ticket_body = request_json(
        "POST",
        f"{WS_BASE}/media/uploads",
        headers=HEADERS,
        json={"filename": path.name, "size": path.stat().st_size, "content_type": content_type},
        timeout=60,
    )
    ticket = ticket_body.get("data", ticket_body)
    upload = ticket.get("upload") or {}
    upload_url = upload.get("url")
    upload_headers = upload.get("headers") or {}
    download_url = ticket.get("download_url")
    if not upload_url or not download_url:
        raise RuntimeError(f"Invalid WaveSpeed upload ticket: {json.dumps(ticket)[:2000]}")
    with path.open("rb") as f:
        r = requests.put(upload_url, headers=upload_headers, data=f, timeout=300)
    if not r.ok:
        raise RuntimeError(f"WaveSpeed media PUT HTTP {r.status_code}: {r.text[:2000]}")
    return download_url


def run_ffmpeg(args: list[str]):
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def audio_duration(path: Path):
    clip = AudioFileClip(str(path))
    value = float(clip.duration)
    clip.close()
    return value


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
    rate = max(dur / target, 0.01)
    run_ffmpeg([
        "-i", str(src),
        "-filter:a", atempo_chain(rate) + ",apad",
        "-t", f"{target:.3f}",
        "-ar", "44100", "-ac", "1", "-b:a", "128k", str(dst),
    ])


def normalize_video(src: Path, dst: Path, target: float):
    run_ffmpeg([
        "-stream_loop", "-1", "-i", str(src), "-t", f"{target:.3f}",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(dst),
    ])


def generate_voice(name: str, text: str, target: float):
    payload = {
        "text": text,
        "voice_id": "Calm_Woman",
        "speed": 0.94,
        "volume": 1,
        "pitch": -1,
        "emotion": "neutral",
        "english_normalization": False,
        "sample_rate": 44100,
        "bitrate": 128000,
        "channel": "1",
        "format": "mp3",
        "language_boost": "Spanish",
    }
    url = ws_run("minimax/speech-2.6-turbo", payload)
    raw = OUT / f"{name}-raw.mp3"
    fitted = OUT / f"{name}-voice.mp3"
    download(url, raw)
    fit_audio(raw, fitted, target)
    return fitted


def pexels_clip(query: str, dst: Path):
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_KEY},
        params={"query": query, "orientation": "portrait", "per_page": 40},
        timeout=60,
    )
    if not r.ok:
        raise RuntimeError(f"Pexels HTTP {r.status_code}: {r.text[:2000]}")
    candidates = []
    for video in r.json().get("videos") or []:
        for vf in video.get("video_files") or []:
            w, h, link = vf.get("width") or 0, vf.get("height") or 0, vf.get("link")
            if link and h > w and h >= 960:
                candidates.append((w * h, link))
    if not candidates:
        raise RuntimeError(f"No Pexels clip found for {query}")
    candidates.sort(reverse=True)
    download(candidates[0][1], dst)


voice_files = {}
for name, target, text in SCENES:
    print(f"VOICE {name}", flush=True)
    voice_files[name] = generate_voice(name, text, target)

for name in ("scene1", "scene3", "scene5"):
    print(f"REFERENCE {name}", flush=True)
    local_ref = OUT / f"{name}-reference.jpeg"
    download(REF_IMAGES[name], local_ref)
    image_url = upload_media(local_ref)
    audio_url = upload_media(voice_files[name])
    print(f"SPEECH_VIDEO {name}", flush=True)
    video_url = ws_run(
        "wavespeed-ai/wan-2.2/speech-to-video",
        {
            "image": image_url,
            "audio": audio_url,
            "prompt": DIRECT_PROMPTS[name],
            "resolution": "480p",
            "seed": 42,
        },
        timeout=1800,
    )
    raw = OUT / f"{name}-raw.mp4"
    download(video_url, raw)
    target = next(x[1] for x in SCENES if x[0] == name)
    normalize_video(raw, OUT / f"{name}.mp4", target)

print("BROLL scene2", flush=True)
pexels_clip("old apartment building mailboxes administrative paperwork documents Spain", OUT / "scene2-raw.mp4")
normalize_video(OUT / "scene2-raw.mp4", OUT / "scene2.mp4", 9.0)

print("BROLL scene4", flush=True)
pexels_clip("young parents two children entering apartment building new home happy family", OUT / "scene4-raw.mp4")
normalize_video(OUT / "scene4-raw.mp4", OUT / "scene4.mp4", 7.0)

concat = OUT / "audio-concat.txt"
concat.write_text("\n".join(f"file '{voice_files[f'scene{i}'].as_posix()}'" for i in range(1, 6)) + "\n", encoding="utf-8")
full_audio = OUT / "full-voice.wav"
run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat), "-c:a", "pcm_s16le", str(full_audio)])

manifest = {
    "clips": [str(OUT / f"scene{i}.mp4") for i in range(1, 6)],
    "audio": str(full_audio),
    "script": "\n\n".join(scene[2] for scene in SCENES),
}
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False), flush=True)
