"""Импорт координат и таймингов LED-слоёв из эталонного Lottie JSON."""

from __future__ import annotations

import json
from pathlib import Path


def _opacity_kfs(layer):
    o = layer.get("ks", {}).get("o", {})
    if not o.get("a"):
        return []
    k = o.get("k", [])
    if not isinstance(k, list):
        return []
    return [(int(f["t"]), float(f["s"][0])) for f in k]


def _timing_from_kfs(kfs):
    """(phase, rise, fall) из ключей opacity 0→peak→0."""
    if len(kfs) < 3:
        return 0, 11, 11
    peak = max(kfs, key=lambda x: x[1])
    start = kfs[0]
    phase = start[0]
    rise = max(1, peak[0] - phase)
    fall = max(1, kfs[-1][0] - peak[0])
    return phase, rise, fall


def placements_from_lottie(path, led_effect="rect_blink", ambient_effect="ambient_pulse",
                           ambient_peak_max=50):
    """Извлекает placements/globals из Lottie (как withoutbaCK / withbaCK).

    Координаты — layer.ks.p (центр слоя в пикселях холста).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    placements = []
    globals_ = []
    fps = data.get("fr", 24)
    op = data.get("op", 50)

    for layer in data.get("layers", []):
        if layer.get("ty") != 4:
            continue
        pos = layer["ks"]["p"]["k"]
        x, y = float(pos[0]), float(pos[1])
        kfs = _opacity_kfs(layer)
        if not kfs:
            continue
        peak = max(v for _, v in kfs)
        if peak <= ambient_peak_max:
            phase, rise, fall = _timing_from_kfs(kfs)
            globals_.append({
                "effect": ambient_effect,
                "params": {"peak": int(peak), "phase": phase, "rise": rise, "fall": fall},
            })
            continue
        phase, rise, fall = _timing_from_kfs(kfs)
        placements.append({
            "effect": led_effect,
            "x": round(x, 3),
            "y": round(y, 3),
            "params": {"phase": phase, "rise": rise, "fall": fall, "peak": int(peak)},
        })

    return {
        "type": "regions",
        "fps": fps,
        "duration": round(op / fps, 4),
        "loop": True,
        "include_background": False,
        "placements": placements,
        "globals": globals_,
        "canvas": {"w": data.get("w"), "h": data.get("h")},
    }


def import_to_spec(lottie_path, image_path, output_path, name=None):
    """Сохраняет spec JSON с координатами из эталонного Lottie."""
    spec = placements_from_lottie(lottie_path)
    spec["image"] = str(image_path)
    spec["name"] = name or Path(image_path).stem + "_overlay"
    Path(output_path).write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return spec
