#!/usr/bin/env python3
"""Генератор Lottie-анимаций из PNG (движок — python-lottie).

Покрывает формат Lottie в режиме авто-генерации: transform-эффекты, layer-эффекты
(ty 20-33) и overlay-сцены («оживший фон»). Экспорт: JSON / dotLottie / HTML.

API:
    generate_animation(image, effect="pulse", duration=2, fps=30, loop=True,
                       output="out.json", fmt="json", params={...})
    animate_png(image, animation="glow_spots", fps=60, loop=True, count=14)

CLI:
    python generator.py -i assets/server_room.jpg -e server_room -o output/s.json
    python generator.py -i assets/flower_1.png -e glow_spots --param count=16 color=#33ff88
    python generator.py --list
    python generator.py -i a.png -e pulse --format dotlottie -o out.lottie
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import build, export, REGISTRY, COMBOS  # noqa: E402
import effects  # noqa: E402,F401  (наполняет REGISTRY)
from spec import generate_from_spec, build_from_spec  # noqa: E402,F401


def generate_animation(image, effect="fade_in", duration=2.0, fps=30, loop=True,
                       output=None, fmt="json", params=None, name=None):
    """Собирает анимацию; при output — экспортирует. Возвращает объект Animation."""
    an = build(image, effect, duration=duration, fps=fps, loop=loop,
               params=params, name=name)
    if output:
        export(an, output, fmt)
    return an


def animate_png(image, animation="fade_in", fps=30, loop=True, duration=2.0,
                output=None, fmt="json", **params):
    """Псевдоним в стиле ТЗ: animate_png(image, animation, fps, loop, **params)."""
    return generate_animation(image, effect=animation, duration=duration, fps=fps,
                              loop=loop, output=output, fmt=fmt, params=params or None)


def catalog():
    """Эффекты, сгруппированные по категориям, + комбо."""
    cats = {}
    for name, meta in sorted(REGISTRY.items()):
        cats.setdefault(meta["category"], []).append((name, meta["doc"]))
    return cats, COMBOS


def _parse_params(pairs):
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise SystemExit(f"Некорректный --param '{p}', ожидается key=value")
        k, v = p.split("=", 1)
        try:
            out[k] = int(v)
        except ValueError:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="PNG -> Lottie авто-генератор (python-lottie)")
    ap.add_argument("--image", "-i", help="путь к PNG/JPG")
    ap.add_argument("--effect", "-e", default="fade_in",
                    help="эффект/комбо (через запятую — сочетание)")
    ap.add_argument("--duration", "-d", type=float, default=2.0, help="длительность, сек")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--loop", action="store_true", default=True)
    ap.add_argument("--no-loop", dest="loop", action="store_false")
    ap.add_argument("--format", "-f", default="json",
                    choices=["json", "dotlottie", "html", "svg", "tgs", "gif"],
                    help="формат экспорта (gif — для мобильного просмотра)")
    ap.add_argument("--gif-width", type=int, default=360,
                    help="ширина GIF в px (только --format gif)")
    ap.add_argument("--gif-fps", type=int, default=12,
                    help="FPS GIF (только --format gif)")
    ap.add_argument("--output", "-o", help="путь вывода (по умолч. output/<имя>.<ext>)")
    ap.add_argument("--name")
    ap.add_argument("--param", action="append", help="параметр key=value (можно многократно)")
    ap.add_argument("--list", action="store_true", help="показать каталог эффектов")
    ap.add_argument("--spec", "-s",
                    help="директивная сборка по JSON-спеке (regions | sequence)")
    ap.add_argument("--player", help="куда записать HTML-плеер с триггером (для --spec)")
    args = ap.parse_args(argv)

    if args.spec:
        import json
        spec = json.loads(open(args.spec, encoding="utf-8").read())
        ext = {"json": "json", "dotlottie": "lottie", "html": "html",
               "svg": "svg", "tgs": "tgs", "gif": "gif"}[args.format]
        stem = args.name or spec.get("name") or os.path.splitext(os.path.basename(args.spec))[0]
        output = args.output or os.path.join("output", f"{stem}.{ext}")
        generate_from_spec(spec, output=output, fmt=args.format, player=args.player,
                           gif_width=args.gif_width, gif_fps=args.gif_fps)
        print(f"OK -> {output}" + (f"  (player: {args.player})" if args.player else ""))
        return

    if args.list:
        cats, combos = catalog()
        for cat in ("transform", "layer", "overlay", "misc"):
            if cat not in cats:
                continue
            print(f"\n[{cat}]")
            for name, doc in cats[cat]:
                print(f"  {name:22} {doc}")
        print("\n[combos]")
        for name, parts in sorted(combos.items()):
            print(f"  {name:22} = {' + '.join(parts)}")
        return

    if not args.image:
        ap.error("нужен --image (или --list)")

    effect = [e.strip() for e in args.effect.split(",")] if "," in args.effect else args.effect
    ext = {"json": "json", "dotlottie": "lottie", "html": "html",
           "svg": "svg", "tgs": "tgs", "gif": "gif"}[args.format]
    output = args.output or os.path.join(
        "output", f"{args.name or os.path.splitext(os.path.basename(args.image))[0]}.{ext}")

    an = build(image=args.image, effect=effect, duration=args.duration,
               fps=args.fps, loop=args.loop,
               params=_parse_params(args.param), name=args.name)
    if args.format == "gif":
        export(an, output, "gif", max_width=args.gif_width, fps=args.gif_fps)
    else:
        export(an, output, args.format)
    print(f"OK -> {output}")


if __name__ == "__main__":
    main()
