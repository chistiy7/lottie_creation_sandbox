"""Экспорт Lottie-анимации в GIF (для мобильного просмотра)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


_RENDER_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0a1628; display: flex; align-items: center; justify-content: center; }
  #wrap { line-height: 0; }
</style>
</head>
<body><div id="wrap"><div id="anim"></div></div>
<script>
const DATA = __LOTTIE__;
window.anim = lottie.loadAnimation({
  container: document.getElementById('anim'),
  renderer: 'svg',
  loop: false,
  autoplay: false,
  animationData: DATA,
});
window.ready = new Promise(r => anim.addEventListener('DOMLoaded', r));
</script></body></html>
"""


def export_gif(an, path, *, max_width=360, fps=12, frame_step=None, optimize=True):
    """Рендерит Animation в GIF через headless Chromium + lottie-web.

    max_width — уменьшение для мобильного (меньше вес файла).
    fps — целевой FPS GIF; по умолчанию min(15, fps анимации).
    frame_step — шаг кадров (1 = каждый кадр).
    """
    from playwright.sync_api import sync_playwright

    data = an.to_dict()
    src_fps = int(data.get("fr", 30))
    total = int(data.get("op", 60))
    aw, ah = int(data["w"]), int(data["h"])

    scale = min(1.0, max_width / aw) if max_width else 1.0
    vw, vh = max(1, int(aw * scale)), max(1, int(ah * scale))

    out_fps = fps or min(12, src_fps)
    step = frame_step or max(1, round(src_fps / out_fps))
    frame_ms = int(1000 / (src_fps / step))

    frames = list(range(0, total, step))
    if not frames or frames[-1] != total - 1:
        frames.append(total - 1)

    html = _RENDER_HTML.replace("__LOTTIE__", json.dumps(data, ensure_ascii=False))

    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "render.html"
        html_path.write_text(html, encoding="utf-8")

        shots: list[Path] = []
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(
                viewport={"width": vw + 20, "height": vh + 20},
                device_scale_factor=1,
            )
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.wait_for_function("window.ready")
            page.evaluate(
                """([w,h]) => {
                    const wrap = document.getElementById('wrap');
                    wrap.style.width = w + 'px';
                    wrap.style.height = h + 'px';
                    const svg = document.querySelector('#anim svg');
                    if (svg) { svg.style.width = w + 'px'; svg.style.height = h + 'px'; }
                }""",
                [vw, vh],
            )

            for i, frame in enumerate(frames):
                page.evaluate(f"anim.goToAndStop({frame}, true)")
                shot = Path(tmp) / f"f{i:04d}.png"
                page.locator("#wrap").screenshot(path=str(shot))
                shots.append(shot)

            browser.close()

        images = [Image.open(s).convert("RGB") for s in shots]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        images[0].save(
            path,
            save_all=True,
            append_images=images[1:],
            duration=frame_ms,
            loop=0,
            optimize=True,
        )

    if optimize and shutil.which("ffmpeg"):
        tmp = Path(path).with_suffix(".tmp.gif")
        Path(path).rename(tmp)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(tmp),
                "-vf",
                (
                    f"fps={out_fps},scale={vw}:-1:flags=lanczos,"
                    "split[s0][s1];[s0]palettegen=max_colors=128[p];"
                    "[s1][p]paletteuse=dither=bayer:bayer_scale=3"
                ),
                str(path),
            ],
            check=True,
            capture_output=True,
        )
        tmp.unlink(missing_ok=True)

    return path
