"""Overlay-эффекты: добавляют новые слои поверх статичной картинки.

Техника «ожившего фона» (как в примере с серверной): картинка не двигается,
а сверху мерцают свечения / плывут частицы / пробегает свет.
"""

import random

from engine import effect, kfs, parse_color, detect_bright_spots, detect_led_bars
from lottie.objects.layers import ShapeLayer
from lottie.objects.shapes import (
    Rect, Group, Fill, GradientFill, GradientType, Star, StarType,
)
from lottie.objects.effects import GaussianBlurEffect
from lottie.utils.color import Color


def _spots(ctx):
    """Ручные spots (image-координаты) или авто-детект ярких точек."""
    p = ctx.params
    if p.get("spots"):
        return p["spots"]
    return detect_bright_spots(
        ctx.image_path, count=p.get("count", 12), threshold=p.get("threshold", 0.5))


def _pulse_kfs(frames, phase, rise, fall, peak):
    ks = [(0, 0)]
    if phase > 0:
        ks.append((phase, 0))
    ks.append((phase + rise, peak, "ease_in_out"))
    end = min(frames, phase + rise + fall)
    ks.append((end, 0, "ease_in_out"))
    if end < frames:
        ks.append((frames, 0))
    return ks


def _blink_kfs(frames, phase, rise, fall, peak):
    ks = [(0, 0)]
    if phase > 0:
        ks.append((phase, 0))
    ks.append((phase + rise, peak, "ease_in_out"))
    end = min(frames, phase + rise + fall)
    ks.append((end, 0, "ease_in_out"))
    if end < frames:
        ks.append((frames, 0))
    return ks


def _rects(ctx):
    """Ручные rects или авто-детект LED-полосок."""
    p = ctx.params
    if p.get("rects"):
        return p["rects"]
    return detect_led_bars(
        ctx.image_path,
        threshold=p.get("threshold", 130),
        min_w=p.get("min_w", 15),
        max_w=p.get("max_w", 120),
        max_h=p.get("max_h", 50),
        max_area=p.get("max_area", 3500),
        max_count=p.get("count", 20),
        min_dist=p.get("min_dist", 28),
    )


@effect("rect_blink", "overlay",
        "Мигание прямоугольных LED-индикаторов на шкафах (как в эталоне). "
        "Авто-детект полосок или ручные rects. "
        "params: count, threshold, rise, peak, seed, rects")
def rect_blink(ctx):
    p = ctx.params
    rng = random.Random(p.get("seed", 11))
    rise = p.get("rise", max(8, round(ctx.frames * 0.22)))
    fall = p.get("fall", rise)
    peak = p.get("peak", 100)
    pad_x = p.get("pad_x", 1.15)
    pad_y = p.get("pad_y", 1.3)
    for i, r in enumerate(_rects(ctx)):
        x = r["x"] + ctx.ox
        y = r["y"] + ctx.oy
        rw = r.get("w", p.get("width", 80)) * pad_x
        rh = r.get("h", p.get("height", 12)) * pad_y
        col = p.get("color") or r.get("color", "#10a6ff")
        L = ctx.rect_blink_layer(x, y, rw, rh, col, name=f"led_{i}")
        phase = r.get("phase", rng.uniform(0, max(1, ctx.frames - rise - fall)))
        kfs(L.transform.opacity, _blink_kfs(ctx.frames, phase, rise, fall, peak))
        ctx.add_overlay(L)


@effect("ambient_pulse", "overlay",
        "Лёгкая пульсация атмосферы на весь кадр; params: color, peak")
def ambient_pulse(ctx):
    p = ctx.params
    peak = p.get("peak", 15)
    L = ctx.rect_layer(ctx.canvas_w, ctx.canvas_h, p.get("color", "#0a3060"), name="ambient")
    f = ctx.frames
    mid = round(f * 0.64)
    kfs(L.transform.opacity, [(0, 0), (mid, peak, "ease_in_out"), (f, 0, "ease_in_out")])
    ctx.add_overlay(L)


@effect("glow_spots", "overlay",
        "Мерцающие свечения на ярких точках PNG. Авто-детект или ручные spots. "
        "params: count, radius, peak, color, seed, spots")
def glow_spots(ctx):
    p = ctx.params
    rng = random.Random(p.get("seed", 7))
    r0 = p.get("radius", 55)
    peak = p.get("peak", 90)
    rise, fall = p.get("rise", 6), p.get("fall", 7)
    override = p.get("color")
    for s in _spots(ctx):
        x = s["x"] + ctx.ox
        y = s["y"] + ctx.oy
        col = override or s.get("color", [0.3, 0.9, 0.5])
        r = s.get("r", r0)
        pk = s.get("peak", peak)
        L = ctx.glow_layer(x, y, r, col, name="glow")
        phase = rng.uniform(0, max(1, ctx.frames - (rise + fall)))
        kfs(L.transform.opacity, _pulse_kfs(ctx.frames, phase, rise, fall, pk))
        ctx.add_overlay(L)


@effect("flicker_spots", "overlay",
        "Резкое неоновое мигание точек (hold-кадры). params: count, peak, color, seed")
def flicker_spots(ctx):
    p = ctx.params
    rng = random.Random(p.get("seed", 3))
    r0 = p.get("radius", 45)
    peak = p.get("peak", 85)
    override = p.get("color")
    for s in _spots(ctx):
        x = s["x"] + ctx.ox
        y = s["y"] + ctx.oy
        col = override or s.get("color", [0.3, 0.9, 0.5])
        L = ctx.glow_layer(x, y, s.get("r", r0), col, name="flick")
        pattern = [(0, 0, "hold")]
        t = rng.uniform(2, 6)
        on = False
        while t < ctx.frames - 2:
            on = not on
            pattern.append((t, peak if on else 0, "hold"))
            t += rng.uniform(2, 7)
        pattern.append((ctx.frames, 0, "hold"))
        kfs(L.transform.opacity, pattern)
        ctx.add_overlay(L)


@effect("breathe", "overlay", "Пульсация атмосферного цвета во весь кадр; params: color, peak")
def breathe(ctx):
    p = ctx.params
    L = ctx.rect_layer(ctx.canvas_w, ctx.canvas_h, p.get("color", "#1060a6"), name="breathe")
    peak = p.get("peak", 15)
    f = ctx.frames
    kfs(L.transform.opacity, [(0, 0), (f / 2, peak), (f, 0)])
    ctx.add_overlay(L)


@effect("vignette", "overlay", "Пульсирующая виньетка по краям; params: color, base, peak")
def vignette(ctx):
    p = ctx.params
    c = parse_color(p.get("color", "#000000"))
    r, g, b = c[0], c[1], c[2]
    layer = ShapeLayer()
    layer.name = "vignette"
    grp = Group()
    rc = Rect()
    rc.size.value = [ctx.canvas_w, ctx.canvas_h]
    rc.position.value = [0, 0]
    gf = GradientFill()
    gf.gradient_type = GradientType.Radial
    gf.colors.set_stops([(0.0, Color(r, g, b, 0)), (0.5, Color(r, g, b, 0)), (1.0, Color(r, g, b, 1))])
    gf.start_point.value = [0, 0]
    gf.end_point.value = [0, max(ctx.canvas_w, ctx.canvas_h) / 2]
    grp.add_shape(rc)
    grp.add_shape(gf)
    layer.add_shape(grp)
    layer.transform.position.value = [ctx.cx, ctx.cy]
    layer.in_point, layer.out_point = 0, ctx.frames
    base, peak = p.get("base", 35), p.get("peak", 60)
    if p.get("pulse", True):
        f = ctx.frames
        kfs(layer.transform.opacity, [(0, base), (f / 2, peak), (f, base)])
    else:
        layer.transform.opacity.value = peak
    ctx.add_overlay(layer)


@effect("light_sweep", "overlay", "Пробегающий луч света; params: color, width, angle, peak")
def light_sweep(ctx):
    p = ctx.params
    width = p.get("width", 160)
    L = ctx.rect_layer(width, ctx.canvas_h * 1.6, p.get("color", "#bfe9ff"), name="light_sweep")
    blur = GaussianBlurEffect()
    blur.effects[0].value.value = width * 0.4
    L.effects = [blur]
    L.transform.rotation.value = p.get("angle", 18)
    L.transform.opacity.value = p.get("peak", 40)
    kfs(L.transform.position,
        [(0, [-width, ctx.cy]), (ctx.frames, [ctx.canvas_w + width, ctx.cy])], "linear")
    ctx.add_overlay(L)


@effect("particles", "overlay", "Плывущие вверх частицы/пыль; params: count, color, seed")
def particles(ctx):
    p = ctx.params
    rng = random.Random(p.get("seed", 11))
    n = p.get("count", 18)
    col = p.get("color", "#bfe0ff")
    smin, smax = p.get("size_min", 3), p.get("size_max", 8)
    for _ in range(n):
        x = rng.uniform(0, ctx.canvas_w)
        size = rng.uniform(smin, smax)
        drift = rng.uniform(-25, 25)
        L = ctx.glow_layer(0, 0, size, col, name="dust")
        kfs(L.transform.position,
            [(0, [x, ctx.canvas_h + 20]), (ctx.frames, [x + drift, -20])], "linear")
        pk = rng.uniform(30, 70)
        kfs(L.transform.opacity, [(0, 0), (ctx.frames * 0.5, pk), (ctx.frames, 0)])
        ctx.add_overlay(L)


@effect("sparkles", "overlay", "Искры-звёздочки, вспыхивающие в случайных точках; params: count, color, size, seed")
def sparkles(ctx):
    p = ctx.params
    rng = random.Random(p.get("seed", 5))
    n = p.get("count", 14)
    col = p.get("color", "#ffffff")
    size = p.get("size", 14)
    for _ in range(n):
        x = rng.uniform(ctx.ox, ctx.ox + ctx.img_w)
        y = rng.uniform(ctx.oy, ctx.oy + ctx.img_h)
        L = ShapeLayer()
        L.name = "spark"
        grp = Group()
        st = Star()
        st.star_type = StarType.Star
        st.points.value = 4
        st.outer_radius.value = size
        st.inner_radius.value = size * 0.35
        st.rotation.value = 0
        st.position.value = [0, 0]
        grp.add_shape(st)
        grp.add_shape(Fill(parse_color(col)))
        L.add_shape(grp)
        L.transform.position.value = [x, y]
        L.in_point, L.out_point = 0, ctx.frames
        phase = rng.uniform(0, max(1, ctx.frames - 8))
        o = [(0, 0)]
        s = [(0, [40, 40])]
        if phase > 0:
            o.append((phase, 0))
            s.append((phase, [40, 40]))
        o += [(phase + 4, 100, "ease_out"), (phase + 8, 0, "ease_in")]
        s += [(phase + 4, [100, 100], "ease_out"), (phase + 8, [40, 40], "ease_in")]
        if phase + 8 < ctx.frames:
            o.append((ctx.frames, 0))
            s.append((ctx.frames, [40, 40]))
        kfs(L.transform.opacity, o)
        kfs(L.transform.scale, s)
        ctx.add_overlay(L)
