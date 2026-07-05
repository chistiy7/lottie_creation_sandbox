"""Директивная сборка Lottie по спецификации (JSON/dict).

Два сценария, покрывающие «не-авто» задачи:

  A. regions  — одна картинка, а эффекты расставлены вручную кликами/промтом:
     {"image": "a.png", "fps":30, "duration":2, "loop":true,
      "globals":   [{"effect":"breathe", "params":{...}}],
      "placements":[{"effect":"glow_spots","x":120,"y":80,"params":{"radius":40}}]}
     x,y — координаты в пикселях ИСХОДНОЙ картинки (0,0 = левый верх).

  B. sequence — карусель PNG -> один Lottie-флипбук (напр. трескающийся орех):
     {"type":"sequence","fps":12,"loop":true,"trigger":"tap",
      "frames":[{"image":"n0.png","hold":8,"fade":0}, {"image":"n1.png","hold":6}],
      "segments":{"crack":[0,3]}}
     Кадры складываются во времени; fade>0 => кроссфейд соседних кадров.

Оба режима переиспользуют примитивы движка (new_scene/finalize, Ctx.*).
Триггер (loop/tap/hover) влияет только на HTML-плеер (write_player_html), не на JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine import (
    new_scene, finalize, export, kfs, REGISTRY, resolve_effects, Ctx,
)
from lottie.objects import Animation
from lottie.objects.layers import ImageLayer
from lottie.objects.assets import Image


# ---------------------------------------------------------------------------
# Сценарий A: расстановка эффектов по регионам одной картинки
# ---------------------------------------------------------------------------

# эффекты, понимающие точку (x,y) через ctx.params["spots"]
_SPOT_EFFECTS = {"glow_spots", "flicker_spots"}
_RECT_EFFECTS = {"rect_blink"}


def _apply(ctx: Ctx, effect_name: str, params: dict, spot=None):
    """Прогоняет один эффект с изолированными params (и опц. одной точкой)."""
    effs = resolve_effects(effect_name)          # раскрывает и комбо
    saved = ctx.params
    for name in effs:
        p = dict(params or {})
        if spot is not None and name in _SPOT_EFFECTS:
            sp = {"x": spot[0], "y": spot[1]}
            if "color" in p:
                sp["color"] = p["color"]
            if "radius" in p:
                sp["r"] = p["radius"]
            if "peak" in p:
                sp["peak"] = p["peak"]
            p["spots"] = [sp]
        if spot is not None and name in _RECT_EFFECTS:
            m = led_mask_near(ctx.image_path, spot[0], spot[1],
                              radius=p.get("snap_radius", 60),
                              threshold=p.get("threshold", 130))
            if m:
                if "phase" in p:
                    m = dict(m, phase=p["phase"])
                p["regions"] = [m]
            else:
                p["regions"] = []
        ctx.params = p
        REGISTRY[name]["fn"](ctx)
    ctx.params = saved


def build_regions(spec: dict) -> Animation:
    image = spec["image"]
    fps = spec.get("fps", 30)
    duration = spec.get("duration", 2.0)
    loop = spec.get("loop", True)
    name = spec.get("name")

    all_effs = []
    for g in spec.get("globals", []):
        all_effs += resolve_effects(g["effect"])
    for pl in spec.get("placements", []):
        all_effs += resolve_effects(pl["effect"])
    has_transform = any(REGISTRY[e]["category"] == "transform" for e in all_effs)
    padding_ratio = spec.get("padding_ratio", 0.2 if has_transform else 0.0)

    an, ctx = new_scene(image, duration=duration, fps=fps, loop=loop,
                        name=name, padding_ratio=padding_ratio)

    for g in spec.get("globals", []):
        _apply(ctx, g["effect"], g.get("params", {}))

    for pl in spec.get("placements", []):
        _apply(ctx, pl["effect"], pl.get("params", {}),
               spot=(pl["x"], pl["y"]))

    return finalize(an, ctx)


# ---------------------------------------------------------------------------
# Сценарий B: последовательность кадров (флипбук)
# ---------------------------------------------------------------------------

def build_sequence(spec: dict) -> Animation:
    frames_spec = spec["frames"]
    if not frames_spec:
        raise ValueError("sequence: пустой список frames")
    fps = spec.get("fps", 12)
    loop = spec.get("loop", True)
    name = spec.get("name", "sequence")
    default_hold = spec.get("hold", 6)
    default_fade = spec.get("fade", 0)

    # 1) грузим ассеты, узнаём размеры холста = max по кадрам
    assets, sizes = [], []
    for fr in frames_spec:
        src = Image().load(str(fr["image"]))
        assets.append(src)
        sizes.append((src.width, src.height))
    cw = max(w for w, _ in sizes)
    ch = max(h for _, h in sizes)

    # 2) тайминг: старт кадра i, длительность hold, перекрытие fade
    starts, holds, fades = [], [], []
    cursor = 0
    for fr in frames_spec:
        hold = fr.get("hold", default_hold)
        fade = fr.get("fade", default_fade)
        starts.append(cursor)
        holds.append(hold)
        fades.append(fade)
        cursor += max(1, hold - fade)          # следующий кадр наступает раньше на fade
    total = starts[-1] + holds[-1]

    an = Animation(total, fps)
    an.width, an.height = cw, ch
    an.name = name

    layers = []
    for i, (src, (w, h)) in enumerate(zip(assets, sizes)):
        an.assets.append(src)
        L = ImageLayer(src.id)
        L.name = f"frame_{i}"
        L.transform.anchor_point.value = [w / 2, h / 2]
        L.transform.position.value = [cw / 2, ch / 2]   # центрируем кадр в холсте
        t0 = starts[i]
        t3 = starts[i] + holds[i]
        fade = fades[i]
        L.in_point, L.out_point = t0, t3
        if fade > 0:
            t1, t2 = t0 + fade, t3 - fade
            kfs(L.transform.opacity,
                [(t0, 0), (t1, 100), (max(t1, t2), 100), (t3, 0)], "ease_in_out")
        else:
            L.transform.opacity.value = 100
        L.effects = []
        layers.append(L)

    # порядок: поздние кадры сверху (в массиве Lottie верхний идёт первым)
    for i, L in enumerate(reversed(layers)):
        L.index = i
        an.add_layer(L)

    return an


# ---------------------------------------------------------------------------
# Единая точка входа
# ---------------------------------------------------------------------------

def build_from_spec(spec) -> Animation:
    if isinstance(spec, (str, Path)):
        spec = json.loads(Path(spec).read_text(encoding="utf-8"))
    kind = spec.get("type", "regions")
    if kind == "sequence":
        return build_sequence(spec)
    if kind in ("regions", "single", "placements"):
        return build_regions(spec)
    raise ValueError(f"Неизвестный type спецификации: {kind!r} (regions|sequence)")


def generate_from_spec(spec, output=None, fmt="json", player=None,
                       gif_width=360, gif_fps=12):
    """Собирает по spec; при output — экспортирует. player=path -> HTML-плеер с триггером."""
    if isinstance(spec, (str, Path)):
        spec = json.loads(Path(spec).read_text(encoding="utf-8"))
    an = build_from_spec(spec)
    if output:
        if fmt == "gif":
            export(an, output, fmt, max_width=gif_width, fps=gif_fps)
        else:
            export(an, output, fmt)
        if player:
            write_player_html(output, player,
                              trigger=spec.get("trigger", "loop"),
                              segments=spec.get("segments"))
    return an


# ---------------------------------------------------------------------------
# HTML-плеер с интерактивностью (триггеры loop/tap/hover)
# ---------------------------------------------------------------------------

_PLAYER_TMPL = """<!doctype html>
<meta charset="utf-8">
<title>__NAME__</title>
<style>
  body{margin:0;background:#1e1f24;display:flex;min-height:100vh;
       align-items:center;justify-content:center}
  #anim{width:min(80vw,80vh);height:min(80vw,80vh);cursor:pointer}
  .tag{position:fixed;top:12px;left:12px;font:12px system-ui;color:#8af;opacity:.7}
</style>
<div class="tag">trigger: __TRIGGER__</div>
<div id="anim"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js"></script>
<script>
const DATA = __DATA__;
const TRIGGER = "__TRIGGER__";
const anim = lottie.loadAnimation({
  container: document.getElementById('anim'),
  renderer: 'svg', autoplay: TRIGGER === 'loop', loop: TRIGGER === 'loop',
  animationData: DATA,
});
const el = document.getElementById('anim');
if (TRIGGER === 'tap'){
  let busy = false;
  el.addEventListener('click', ()=>{ if(busy) return; busy = true;
    anim.goToAndPlay(0, true);
    anim.addEventListener('complete', function h(){ busy=false; anim.removeEventListener('complete', h); });
  });
} else if (TRIGGER === 'hover'){
  el.addEventListener('mouseenter', ()=>anim.goToAndPlay(0, true));
}
</script>
"""


def write_player_html(json_path, out_path, trigger="loop", segments=None):
    data = Path(json_path).read_text(encoding="utf-8")
    html = (_PLAYER_TMPL
            .replace("__DATA__", data)
            .replace("__TRIGGER__", trigger)
            .replace("__NAME__", Path(out_path).stem))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path
