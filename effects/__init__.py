"""Авто-регистрация всех модулей эффектов.

Каждый *.py, вызывающий @effect(...), подхватывается автоматически.
Новый эффект = новый файл (или новая функция в существующем).
"""

from importlib import import_module
from pathlib import Path

for _f in sorted(Path(__file__).parent.glob("*.py")):
    if _f.stem != "__init__":
        import_module(f"{__name__}.{_f.stem}")
