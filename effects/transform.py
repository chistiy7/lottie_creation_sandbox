"""Transform-эффекты: анимируют трансформ базового слоя-картинки.

Каналы: opacity, rotation, scale, position (якорь = центр изображения).
"""

from engine import effect, kfs


def _tr(ctx):
    return ctx.img_layer.transform


@effect("fade_in", "transform", "Плавное появление (opacity 0->100)")
def fade_in(ctx):
    kfs(_tr(ctx).opacity, [(0, 0, "ease_out"), (ctx.frames, 100)])


@effect("fade_out", "transform", "Плавное исчезновение (opacity 100->0)")
def fade_out(ctx):
    kfs(_tr(ctx).opacity, [(0, 100, "ease_in"), (ctx.frames, 0)])


@effect("scale", "transform", "Масштаб-появление from_scale->to_scale")
def scale(ctx):
    a = ctx.params.get("from_scale", 60)
    b = ctx.params.get("to_scale", 100)
    kfs(_tr(ctx).scale, [(0, [a, a], "ease_out"), (ctx.frames, [b, b])])


@effect("pulse", "transform", "Пульсация масштаба (бесшовный цикл), param amount")
def pulse(ctx):
    amp = ctx.params.get("amount", 10)
    f = ctx.frames
    kfs(_tr(ctx).scale, [(0, [100, 100]), (f / 2, [100 + amp, 100 + amp]), (f, [100, 100])])


@effect("rotate", "transform", "Покачивание маятником ±angle (цикл)")
def rotate(ctx):
    ang = ctx.params.get("angle", 10)
    f = ctx.frames
    kfs(_tr(ctx).rotation, [(0, 0), (f / 4, ang), (f / 2, 0), (3 * f / 4, -ang), (f, 0)])


@effect("spin", "transform", "Полный оборот 360*turns (цикл)")
def spin(ctx):
    t = ctx.params.get("turns", 1)
    kfs(_tr(ctx).rotation, [(0, 0, "linear"), (ctx.frames, 360 * t, "linear")])


@effect("translate", "transform", "Выезд из смещения (dx, dy) в центр")
def translate(ctx):
    dx = ctx.params.get("dx", 0)
    dy = ctx.params.get("dy", -40)
    kfs(_tr(ctx).position,
        [(0, [ctx.cx + dx, ctx.cy + dy], "ease_out"), (ctx.frames, [ctx.cx, ctx.cy])])


@effect("float", "transform", "Вертикальное парение ±dy (бесшовный цикл)")
def float_(ctx):
    dy = ctx.params.get("dy", 15)
    f = ctx.frames
    kfs(_tr(ctx).position,
        [(0, [ctx.cx, ctx.cy - dy]), (f / 2, [ctx.cx, ctx.cy + dy]), (f, [ctx.cx, ctx.cy - dy])])


@effect("shake", "transform", "Быстрая тряска поворотом ±angle, param shakes")
def shake(ctx):
    ang = ctx.params.get("angle", 6)
    n = ctx.params.get("shakes", 6)
    f = ctx.frames
    ks = [(f * k / n, 0 if k in (0, n) else (ang if k % 2 else -ang)) for k in range(n + 1)]
    kfs(_tr(ctx).rotation, ks)


@effect("bounce", "transform", "Отскок сверху с затуханием")
def bounce(ctx):
    f = ctx.frames
    amp = ctx.params.get("amount", 60)
    cx, cy = ctx.cx, ctx.cy
    kfs(_tr(ctx).position, [
        (0, [cx, cy - amp], "ease_in"),
        (f * 0.4, [cx, cy], "ease_out"),
        (f * 0.6, [cx, cy - amp * 0.3], "ease_in"),
        (f * 0.8, [cx, cy], "ease_out"),
        (f, [cx, cy]),
    ])


@effect("swing", "transform", "Затухающее качание (маятник, entrance)")
def swing(ctx):
    f = ctx.frames
    ang = ctx.params.get("angle", 18)
    kfs(_tr(ctx).rotation, [
        (0, ang, "ease_out"), (f * 0.3, -ang * 0.6), (f * 0.55, ang * 0.35),
        (f * 0.78, -ang * 0.15), (f, 0),
    ])
