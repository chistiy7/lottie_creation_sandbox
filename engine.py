"""Движок авто-генерации Lottie поверх python-lottie.

Покрывает объектный формат Lottie (слои, шейпы, эффекты, ключевые кадры) и даёт
слой авто-генерации: из PNG + имени эффекта собирается готовая анимация и
экспортируется в JSON / dotLottie / HTML.

Эффекты регистрируются декоратором @effect(name, category) в пакете effects/.
Каждый эффект мутирует live-объекты python-lottie через контекст Ctx.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lottie.objects import Animation
from lottie.objects.layers import ImageLayer, ShapeLayer
from lottie.objects.assets import Image
from lottie.objects.shapes import Ellipse, Rect, Fill, Group, TransformShape
from lottie.objects.effects import GaussianBlurEffect
from lottie.objects import easing
from lottie.utils.color import Color
from lottie.exporters import exporters as _EXPORTERS


# ---------------------------------------------------------------------------
# Хелперы: цвет, easing, ключевые кадры
# ---------------------------------------------------------------------------

def parse_color(c) -> Color:
    """hex '#rrggbb' | (r,g,b) 0-1 или 0-255 | Color -> Color."""
    if isinstance(c, Color):
        return c
    if isinstance(c, str):
        h = c.lstrip("#")
        return Color(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)))
    if isinstance(c, (list, tuple)):
        vals = list(c[:3])
        if max(vals) > 1:
            vals = [v / 255 for v in vals]
        return Color(*vals)
    raise ValueError(f"Не понял цвет: {c!r}")


EASE = {
    "linear": easing.Linear,
    "ease_in": easing.EaseIn,
    "ease_out": easing.EaseOut,
    "ease_in_out": easing.Sigmoid,
    "hold": easing.Hold,
}


def ease(name="ease_in_out"):
    return EASE.get(name, easing.Sigmoid)()


def kfs(prop, keyframes, default_ease="ease_in_out"):
    """Применяет список ключевых кадров к свойству python-lottie.

    keyframes: список (time, value) или (time, value, ease_name).
    """
    for k in keyframes:
        t, v = k[0], k[1]
        e = k[2] if len(k) > 2 else default_ease
        prop.add_keyframe(round(t), v, ease(e))
    return prop


# ---------------------------------------------------------------------------
# Реестр эффектов
# ---------------------------------------------------------------------------

REGISTRY: dict[str, dict] = {}
COMBOS: dict[str, list[str]] = {
    # transform
    "fade_scale":  ["fade_in", "scale"],
    "fade_rotate": ["fade_in", "rotate"],
    "pop":         ["fade_in", "scale"],
    "pop_spin":    ["fade_in", "scale", "spin"],
    # scene / «оживший фон»
    "scene_tech":  ["glow_spots", "breathe"],
    "scene_alive": ["glow_spots", "breathe", "particles"],
    "neon":        ["flicker_spots", "breathe"],
    "cinematic":   ["glow_spots", "vignette", "light_sweep"],
    "server_room": ["glow_spots", "breathe", "vignette"],
    # layer-fx combos
    "dreamy":      ["gaussian_blur_pulse", "breathe"],
    "spotlight":   ["drop_shadow", "vignette"],
}


def effect(name, category="misc", doc=""):
    def deco(fn):
        REGISTRY[name] = {"fn": fn, "category": category, "doc": doc or (fn.__doc__ or "").strip()}
        return fn
    return deco


def resolve_effects(spec):
    if isinstance(spec, (list, tuple)):
        out = []
        for e in spec:
            out += resolve_effects(e)
        return out
    if spec in COMBOS:
        return COMBOS[spec]
    if spec in REGISTRY:
        return [spec]
    raise ValueError(
        f"Неизвестный эффект '{spec}'.\n"
        f"  эффекты: {sorted(REGISTRY)}\n"
        f"  комбо:   {sorted(COMBOS)}"
    )


# ---------------------------------------------------------------------------
# Детекция ярких точек (авто-режим свечений) — только Pillow
# ---------------------------------------------------------------------------

def detect_bright_spots(path, count=12, threshold=0.5, min_dist_frac=0.045):
    """Находит самые яркие пятна (LED/огни). Возвращает точки в координатах PNG."""
    from PIL import Image as PILImage

    im = PILImage.open(path).convert("RGB")
    W, H = im.size
    scale = max(1, max(W, H) // 320)
    sw, sh = max(1, W // scale), max(1, H // scale)
    small = im.resize((sw, sh))
    px = list(small.getdata())

    def lum(c):
        return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255

    cands = []
    for i, c in enumerate(px):
        l = lum(c)
        if l >= threshold:
            cands.append((l, i % sw, i // sw, c))
    cands.sort(reverse=True)

    min_dist = max(4, int(min(sw, sh) * min_dist_frac))
    picked = []
    for l, x, y, c in cands:
        if all((x - ox) ** 2 + (y - oy) ** 2 >= min_dist ** 2 for _, ox, oy, _ in picked):
            picked.append((l, x, y, c))
            if len(picked) >= count:
                break

    return [{
        "x": (x + 0.5) * scale, "y": (y + 0.5) * scale,
        "color": [c[0] / 255, c[1] / 255, c[2] / 255], "bright": l,
    } for l, x, y, c in picked]


# ---------------------------------------------------------------------------
# Контекст, передаваемый в эффекты
# ---------------------------------------------------------------------------

@dataclass
class Ctx:
    an: Animation
    img_layer: ImageLayer
    frames: int
    fps: int
    img_w: int
    img_h: int
    canvas_w: int
    canvas_h: int
    cx: float
    cy: float
    ox: float                       # смещение картинки в холсте (=pad)
    oy: float
    image_path: str
    loop: bool = True
    params: dict = field(default_factory=dict)
    overlays: list = field(default_factory=list)   # shape-слои поверх картинки

    # --- строительные примитивы для overlay-эффектов ---
    def add_overlay(self, layer):
        self.overlays.append(layer)
        return layer

    def glow_layer(self, x, y, r, color, name="glow"):
        """Мягкое свечение = залитый эллипс + gaussian blur. Без анимации opacity."""
        layer = ShapeLayer()
        layer.name = name
        grp = Group()
        el = Ellipse()
        el.size.value = [2 * r, 2 * r]
        el.position.value = [0, 0]
        fill = Fill(parse_color(color))
        grp.add_shape(el)
        grp.add_shape(fill)
        layer.add_shape(grp)
        layer.transform.position.value = [x, y]
        blur = GaussianBlurEffect()
        blur.effects[0].value.value = max(8, r * 0.7)
        layer.effects = [blur]
        layer.in_point, layer.out_point = 0, self.frames
        return layer

    def rect_layer(self, w, h, color, name="overlay", x=None, y=None):
        """Прямоугольник во весь холст (или заданный) со сплошной заливкой."""
        layer = ShapeLayer()
        layer.name = name
        grp = Group()
        rc = Rect()
        rc.size.value = [w, h]
        rc.position.value = [0, 0]
        fill = Fill(parse_color(color))
        grp.add_shape(rc)
        grp.add_shape(fill)
        layer.add_shape(grp)
        layer.transform.position.value = [self.cx if x is None else x,
                                          self.cy if y is None else y]
        layer.in_point, layer.out_point = 0, self.frames
        return layer


# ---------------------------------------------------------------------------
# Сборка и экспорт
# ---------------------------------------------------------------------------

def new_scene(image, duration=2.0, fps=30, loop=True, params=None,
              name=None, padding_ratio=0.0):
    """Готовит Animation + базовый ImageLayer + Ctx (слои ещё не добавлены).

    Возвращает (an, ctx). База лежит в ctx.img_layer; overlay-эффекты кладут свои
    слои в ctx.overlays. Завершается через finalize(an, ctx).
    """
    params = params or {}
    frames = max(1, round(duration * fps))

    src = Image().load(str(image))
    iw, ih = src.width, src.height

    pad = round(max(iw, ih) * padding_ratio) if padding_ratio else 0
    cw, ch = iw + 2 * pad, ih + 2 * pad

    an = Animation(frames, fps)
    an.width, an.height = cw, ch
    an.name = name or Path(image).stem
    an.assets.append(src)

    base = ImageLayer(src.id)
    base.name = an.name
    base.transform.anchor_point.value = [iw / 2, ih / 2]
    base.transform.position.value = [cw / 2, ch / 2]
    base.in_point, base.out_point = 0, frames
    base.effects = []

    ctx = Ctx(an=an, img_layer=base, frames=frames, fps=fps,
              img_w=iw, img_h=ih, canvas_w=cw, canvas_h=ch,
              cx=cw / 2, cy=ch / 2, ox=pad, oy=pad,
              image_path=str(image), loop=loop, params=params)
    return an, ctx


def finalize(an, ctx, extra_layers=None):
    """Собирает слои сцены: overlay поверх базовой картинки, проставляет индексы.

    extra_layers — дополнительные слои (например кадры flipbook) вместо/вместе с
    базовой картинкой; кладутся под overlay, порядок сохраняется.
    """
    base_layers = extra_layers if extra_layers is not None else [ctx.img_layer]
    layers = ctx.overlays + base_layers
    for i, layer in enumerate(layers):
        layer.index = i
        an.add_layer(layer)
    return an


def build(image, effect_spec, duration=2.0, fps=30, loop=True,
          params=None, name=None, padding_ratio=None):
    effs = resolve_effects(effect_spec)

    # Padding нужно только transform-эффектам (чтобы scale/rotate не обрезались).
    # Для overlay/layer-сцен холст = размеру картинки (без пустых полей).
    if padding_ratio is None:
        has_transform = any(REGISTRY[e]["category"] == "transform" for e in effs)
        padding_ratio = 0.2 if has_transform else 0.0

    an, ctx = new_scene(image, duration=duration, fps=fps, loop=loop,
                        params=params, name=name, padding_ratio=padding_ratio)

    for eff in effs:
        REGISTRY[eff]["fn"](ctx)

    return finalize(an, ctx)


_FMT_SLUG = {
    "json": "lottie", "lottie": "lottie", "lottie-json": "lottie",
    "dotlottie": "dotlottie", "archive": "dotlottie",
    "html": "html", "svg": "svg", "tgs": "tgs",
    "gif": "gif",
}


def export(an, path, fmt="json", **kwargs):
    if fmt == "gif":
        from export_gif import export_gif
        return export_gif(an, path, **kwargs)

    slug = _FMT_SLUG.get(fmt, fmt)
    exporter = _EXPORTERS.get(slug)
    if exporter is None:
        raise ValueError(f"Нет экспортёра '{fmt}'. Доступно: {sorted(_FMT_SLUG)}")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    exporter.process(an, str(path))
    return path
