"""Warms the local map for the barrel run: where Blender's Add menu rows are in a maximised window, read off a real screenshot and
checked by eye, with the product's own look of each. A person's checked steps teach the same map as they go. Takes the mouse briefly.

    py -m tests.accuracy.blender_teach
"""
from __future__ import annotations

from PIL import ImageDraw, ImageGrab

from engine import config
from engine.appmap.store import AppMapStore
from engine.dpi import make_dpi_aware
from engine.live import capture
from tests.accuracy import sw_drive as d

ADD = (381, 83, 34, 16)
MESH = (385, 112, 225, 24)
CYLINDER = (640, 254, 200, 24)
SHADING = (2062, 80, 26, 24)
POPOVER = {"MatCap": (2013, 215, 116, 28), "Shadow": (1898, 908, 22, 22), "Cavity": (1925, 982, 22, 22)}


def main() -> int:
    make_dpi_aware()
    d.WINDOW = "Blender"
    store = AppMapStore("Blender", local=config.CACHE / "appmaps-check")
    win = d.win()
    d.front()
    d.hover(1280, 800, settle=0.3)
    d.keys("Esc", settle=0.3)

    def teach(label: str, box: tuple[int, int, int, int]) -> None:
        img, origin = capture.with_popups(d.win().hwnd)
        print(label, store.learn(label, "Blender", box, win.rect, capture.look_of(capture.crop(img, box, origin))), flush=True)

    teach("Add", ADD)
    d.click(ADD[0] + ADD[2] // 2, ADD[1] + ADD[3] // 2, settle=1.0)
    teach("Mesh", MESH)
    d.hover(MESH[0] + 60, MESH[1] + MESH[3] // 2, settle=1.2)
    teach("Cylinder", CYLINDER)
    shot = ImageGrab.grab()
    draw = ImageDraw.Draw(shot)
    for b in (ADD, MESH, CYLINDER):
        draw.rectangle((b[0], b[1], b[0] + b[2], b[1] + b[3]), outline=(255, 0, 0), width=2)
    shot.crop((0, 0, 1100, 500)).save(config.CACHE / "screenshots" / "blender" / "teach.png")
    d.keys("Esc", settle=0.3)
    d.keys("Esc", settle=0.3)
    d.hover(1090, 720, settle=0.4)
    teach("Viewport Shading drop-down", SHADING)
    d.click(SHADING[0] + 12, SHADING[1] + 11, settle=1.2)
    for label, box in POPOVER.items():
        teach(label, box)
    shot = ImageGrab.grab()
    draw = ImageDraw.Draw(shot)
    for b in (SHADING, *POPOVER.values()):
        draw.rectangle((b[0], b[1], b[0] + b[2], b[1] + b[3]), outline=(255, 0, 0), width=2)
    shot.crop((1500, 60, 2560, 1040)).save(config.CACHE / "screenshots" / "blender" / "teach2.png")
    d.hover(1090, 720, settle=0.8)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
