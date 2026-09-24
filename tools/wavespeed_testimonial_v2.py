from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg
import requests
from moviepy import AudioFileClip
from pydub import AudioSegment
from pydub.silence import detect_silence

ROOT = Path.cwd()
OUT = ROOT / "storage" / "testimonial_v1_assets"
OUT.mkdir(parents=True, exist_ok=True)

WS_KEY = os.environ["WAVESPEED_API_KEY"].strip()
PEXELS_KEY = os.environ["PEXELS_API_KEY"].strip()
WS_BASE = "https://api.wavespeed.ai/api/v3"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
HEADERS = {"Authorization": f"Bearer {WS_KEY}", "Content-Type": "application/json"}

BASE_IMAGE_URL = "https://d2h7xmz5gqybh9.cloudfront.net/output/31e5f02e-6aca-488c-af24-37631d897577-u2_cda3fad8-7448-4e5b-b052-bd4fabf98729.jpeg"
SCENE3_IMAGE_URL = "https://d2h7xmz5gqybh9.cloudfront.net/output/a9d5e62d-fa38-43b7-93aa-955183a183ff-u1_61081073-b148-4ef5-b567-6deef3f94f78.jpeg"
SCENE5_IMAGE_URL = "https://d2h7xmz5gqybh9.cloudfront.net/output/d3ea50df-afd8-43c6-ae07-8c3ac8f57689-u1_2f98ae1d-0064-471e-8de8-48a9f761201b.jpeg"

SCENES = [
    ("scene1", 6.0, "Este piso llevaba muchísimo tiempo abandonado… y tenía una deuda que parecía imposible de resolver."),
    ("scene2", 9.0, "La comunidad ya no sabía qué hacer. Cada mes que pasaba, el problema iba creciendo."),
    ("scene3", 9.0, "Pero nos pusimos manos a la obra y, en solo seis meses, conseguimos solucionarlo todo. Hoy ese piso ya no tiene ninguna deuda."),
    ("scene4", 7.0, "Y ahora viven aquí una pareja joven con sus dos niños. Da gusto ver cómo un problema tan grande se ha convertido en un nuevo comienzo."),
    ("scene5", 4.0, "Para mí, eso es lo más bonito de este trabajo."),
]


def run_ffmpeg(args: list[str]):
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def wait_prediction(prediction_id: str, timeout: int = 1800):
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
                raise RuntimeError("WaveSpeed completed without output")
            return outputs[0]
        if status in {"failed", "cancelled", "timeout", "deleted"}:
            raise RuntimeError(f"WaveSpeed task failed: {data.get('error')}")
        time.sleep(3)
    raise TimeoutError("WaveSpeed task timed out")


def ws_run(model: str, payload: dict, timeout: int = 1800):
    waits = [12, 20, 30, 45, 60, 90]
    last = None
    for attempt in range(len(waits) + 1):
        r = requests.post(f"{WS_BASE}/{model}", headers=HEADERS, json=payload, timeout=60)
        last = r
        if r.status_code == 429 and attempt < len(waits):
            header = r.headers.get("Retry-After", "").strip()
            try:
                delay = max(float(header), waits[attempt])
            except Exception:
                delay = waits[attempt]
            print(f"WaveSpeed rate limited; retrying after {int(delay)} seconds")
            time.sleep(delay)
            continue
        r.raise_for_status()
        data = r.json().get("data", r.json())
        pid = data.get("id")
        if not pid:
            raise RuntimeError("WaveSpeed did not return prediction id")
        return wait_prediction(pid, timeout=timeout)
    raise RuntimeError(f"WaveSpeed request failed with HTTP {last.status_code if last else 'unknown'}")


def download(url: str, path: Path):
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
    if path.stat().st_size < 1000:
        raise RuntimeError(f"Invalid download: {path.name}")


def upload_media(path: Path):
    waits = [10, 20, 30, 45]
    for attempt in range(len(waits) + 1):
        with path.open("rb") as f:
            r = requests.post(
                f"{WS_BASE}/media/upload/binary",
                headers={"Authorization": f"Bearer {WS_KEY}"},
                files={"file": (path.name, f)},
                timeout=300,
            )
        if r.status_code == 429 and attempt < len(waits):
            time.sleep(waits[attempt])
            continue
        r.raise_for_status()
        data = r.json().get("data", r.json())
        url = data.get("download_url")
        if not url:
            raise RuntimeError("WaveSpeed upload returned no URL")
        return url
    raise RuntimeError("WaveSpeed upload rate limit did not clear")


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
        "-t", f"{target:.3f}", "-ar", "44100", "-ac", "1", str(dst),
    ])


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
        params={"query": query, "orientation": "portrait", "per_page": 40},
        timeout=60,
    )
    r.raise_for_status()
    candidates = []
    for video in r.json().get("videos") or []:
        for vf in video.get("video_files") or []:
            w, h, link = vf.get("width") or 0, vf.get("height") or 0, vf.get("link")
            if link and h > w and h >= 960:
                candidates.append((w * h, link))
    if not candidates:
        raise RuntimeError(f"No Pexels clip found for: {query}")
    candidates.sort(reverse=True)
    download(candidates[0][1], dst)


def generate_full_voice():
    text = " <#1.60#> ".join(scene[2] for scene in SCENES)
    payload = {
        "text": text,
        "voice_id": "Calm_Woman",
        "speed": 0.93,
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
    try:
        url = ws_run("minimax/speech-2.6-turbo", payload)
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 429:
            raise
        print("Speech 2.6 remained rate limited; using Speech 02 Turbo")
        url = ws_run("minimax/speech-02-turbo", payload)
    raw = OUT / "full-raw.mp3"
    download(url, raw)
    return raw


def split_voice(raw: Path):
    audio = AudioSegment.from_file(raw)
    threshold = audio.dBFS - 18
    silences = detect_silence(audio, min_silence_len=900, silence_thresh=threshold, seek_step=10)
    if len(silences) < 4:
        raise RuntimeError(f"Expected four scene pauses, found {len(silences)}")
    pauses = sorted(silences, key=lambda x: x[1] - x[0], reverse=True)[:4]
    pauses.sort()
    cuts = [0] + [int((a + b) / 2) for a, b in pauses] + [len(audio)]
    voice_files = {}
    for index, (name, target, _text) in enumerate(SCENES):
        segment = audio[cuts[index]:cuts[index + 1]]
        trimmed = segment.strip_silence(silence_len=150, silence_thresh=threshold, padding=80)
        raw_segment = OUT / f"{name}-segment.wav"
        trimmed.export(raw_segment, format="wav")
        fitted = OUT / f"{name}-voice.wav"
        fit_audio(raw_segment, fitted, target)
        voice_files[name] = fitted
    return voice_files


print("Generating one natural Spanish voice track")
voice_files = split_voice(generate_full_voice())

print("Generating lip-synced testimonial scenes")
image_urls = {"scene1": BASE_IMAGE_URL, "scene3": SCENE3_IMAGE_URL, "scene5": SCENE5_IMAGE_URL}
for name in ("scene1", "scene3", "scene5"):
    audio_url = upload_media(voice_files[name])
    video_url = ws_run(
        "wavespeed-ai/wan-2.2/speech-to-video",
        {"image": image_urls[name], "audio": audio_url, "resolution": "480p"},
        timeout=1800,
    )
    raw = OUT / f"{name}-s2v-raw.mp4"
    download(video_url, raw)
    target = next(scene[1] for scene in SCENES if scene[0] == name)
    normalize_video(raw, OUT / f"{name}.mp4", target)

print("Downloading matched narrative B-roll")
pexels_clip("old apartment building mailboxes letters paperwork documents", OUT / "scene2-raw.mp4")
pexels_clip("young parents two children entering apartment building new home", OUT / "scene4-raw.mp4")
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
