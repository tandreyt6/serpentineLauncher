from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from universal_gui.pack.format import build_pack
from Core.configuration.settings import THEME_UPDATE_SUFFIX


def main() -> None:
    for name, destination in (("serpantine-night", "assets/themes"), ("serpantine-day", "themes")):
        folder = ROOT / destination
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (name + ".ugtheme")
        pending = target.with_suffix(target.suffix + THEME_UPDATE_SUFFIX)
        try:
            build_pack(ROOT / "theme_sources" / name, target)
            pending.unlink(missing_ok=True)
            print(target)
        except PermissionError:
            build_pack(ROOT / "theme_sources" / name, pending)
            print(str(pending) + " (active theme will update on restart)")


if __name__ == "__main__":
    main()
