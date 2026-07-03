"""Layer-эффекты Lottie (массив ef на слое-картинке): ty 20-33.

Значения эффектов задаются как ev.value.value = X (статично) или
kfs(ev.value, [...]) (анимация). Многие поддерживают param pulse.
"""

from engine import effect, kfs, parse_color
from lottie.objects.effects import (
    TintEffect, TritoneEffect, FillEffect, DropShadowEffect,
    GaussianBlurEffect, RadialWipeEffect, TwirlEffect, SpherizeEffect,
)


@effect("tint", "layer", "Тонирование тени->света в цвет; param color, amount, pulse")
def tint(ctx):
    p = ctx.params
    e = TintEffect()
    e.effects[0].value.value = parse_color(p.get("dark", "#000000"))
    e.effects[1].value.value = parse_color(p.get("color", "#3fa9ff"))
    amt = p.get("amount", 60)
    if p.get("pulse"):
        f = ctx.frames
        kfs(e.effects[2].value, [(0, 0), (f / 2, amt), (f, 0)])
    else:
        e.effects[2].value.value = amt
    ctx.img_layer.effects.append(e)


@effect("tritone", "layer", "Три-тон: highlights/midtones/shadows; param hi, mid, lo")
def tritone(ctx):
    p = ctx.params
    e = TritoneEffect()
    e.effects[0].value.value = parse_color(p.get("hi", "#ffffff"))
    e.effects[1].value.value = parse_color(p.get("mid", "#3f7fd0"))
    e.effects[2].value.value = parse_color(p.get("lo", "#001020"))
    ctx.img_layer.effects.append(e)


@effect("fill", "layer", "Заливка цветом поверх слоя; param color, opacity(0-1)")
def fill(ctx):
    p = ctx.params
    e = FillEffect()
    e.effects[2].value.value = parse_color(p.get("color", "#3fa9ff"))
    e.effects[6].value.value = p.get("opacity", 0.4)
    ctx.img_layer.effects.append(e)


@effect("drop_shadow", "layer", "Тень; param color, opacity(0-255), angle, distance, softness")
def drop_shadow(ctx):
    p = ctx.params
    e = DropShadowEffect()
    e.effects[0].value.value = parse_color(p.get("color", "#000000"))
    e.effects[1].value.value = p.get("opacity", 128)
    e.effects[2].value.value = p.get("angle", 135)
    e.effects[3].value.value = p.get("distance", 12)
    e.effects[4].value.value = p.get("softness", 20)
    ctx.img_layer.effects.append(e)


@effect("glow", "layer", "Внешнее свечение (мягкий цветной ореол); param color, softness")
def glow(ctx):
    p = ctx.params
    e = DropShadowEffect()
    e.effects[0].value.value = parse_color(p.get("color", "#7fd0ff"))
    e.effects[1].value.value = p.get("opacity", 255)
    e.effects[2].value.value = 0
    e.effects[3].value.value = 0
    e.effects[4].value.value = p.get("softness", 45)
    ctx.img_layer.effects.append(e)


@effect("gaussian_blur", "layer", "Статичное размытие; param amount")
def gaussian_blur(ctx):
    e = GaussianBlurEffect()
    e.effects[0].value.value = ctx.params.get("amount", 12)
    ctx.img_layer.effects.append(e)


@effect("gaussian_blur_pulse", "layer", "Размытие-«дыхание» 0->amount->0 (цикл)")
def gaussian_blur_pulse(ctx):
    amt = ctx.params.get("amount", 18)
    f = ctx.frames
    e = GaussianBlurEffect()
    kfs(e.effects[0].value, [(0, 0), (f / 2, amt), (f, 0)])
    ctx.img_layer.effects.append(e)


@effect("radial_wipe", "layer", "Круговое проявление слоя; param angle")
def radial_wipe(ctx):
    e = RadialWipeEffect()
    kfs(e.effects[0].value, [(0, 100), (ctx.frames, 0)])          # completion 100->0 = reveal
    e.effects[1].value.value = ctx.params.get("angle", 0)
    e.effects[2].value.value = [ctx.cx, ctx.cy]
    ctx.img_layer.effects.append(e)


@effect("twirl", "layer", "Закручивание; param angle, radius (цикл 0->angle->0)")
def twirl(ctx):
    ang = ctx.params.get("angle", 60)
    f = ctx.frames
    e = TwirlEffect()
    kfs(e.effects[0].value, [(0, 0), (f / 2, ang), (f, 0)])
    e.effects[1].value.value = ctx.params.get("radius", 50)
    e.effects[2].value.value = [ctx.cx, ctx.cy]
    ctx.img_layer.effects.append(e)


@effect("spherize", "layer", "Сферическая выпуклость-«дыхание»; param amount")
def spherize(ctx):
    amt = ctx.params.get("amount", 35)
    f = ctx.frames
    e = SpherizeEffect()
    kfs(e.effects[0].value, [(0, 0), (f / 2, amt), (f, 0)])
    e.effects[1].value.value = [ctx.cx, ctx.cy]
    ctx.img_layer.effects.append(e)
