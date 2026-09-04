from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any, Protocol


class BoardRenderBackend(Protocol):
    def clear_tag(self, tag: str) -> None: ...

    def rectangle(
        self,
        tag: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        fill: str = "",
        outline: str = "",
        width: float = 1,
        stipple: str = "",
    ) -> object: ...

    def oval(
        self,
        tag: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        fill: str = "",
        outline: str = "",
        width: float = 1,
    ) -> object: ...

    def line(
        self,
        tag: str,
        points: tuple[float, ...],
        *,
        fill: str,
        width: float,
        capstyle: str | None = None,
    ) -> object: ...

    def polygon(
        self,
        tag: str,
        points: tuple[float, ...],
        *,
        fill: str = "",
        outline: str = "",
        width: float = 1,
    ) -> object: ...

    def text(
        self,
        tag: str,
        x: float,
        y: float,
        *,
        text: str,
        fill: str,
        font: tuple[str, int, str] | tuple[str, int],
        anchor: str = "center",
    ) -> object: ...

    def image(self, tag: str, x: float, y: float, image: object, *, anchor: str = "center") -> object: ...

    def raise_tag(self, tag: str) -> None: ...


@dataclass(slots=True)
class MemoryCanvasBackend:
    """Small retained backend used by tests and non-GUI render planning."""

    operations: list[tuple[str, tuple[object, ...], dict[str, object]]]

    def __init__(self) -> None:
        self.operations = []

    def clear_tag(self, tag: str) -> None:
        self.operations.append(("clear", (tag,), {}))

    def rectangle(self, tag: str, x1: float, y1: float, x2: float, y2: float, **options: object) -> object:
        item = ("rectangle", (tag, x1, y1, x2, y2), options)
        self.operations.append(item)
        return item

    def oval(self, tag: str, x1: float, y1: float, x2: float, y2: float, **options: object) -> object:
        item = ("oval", (tag, x1, y1, x2, y2), options)
        self.operations.append(item)
        return item

    def line(self, tag: str, points: tuple[float, ...], **options: object) -> object:
        item = ("line", (tag, points), options)
        self.operations.append(item)
        return item

    def polygon(self, tag: str, points: tuple[float, ...], **options: object) -> object:
        item = ("polygon", (tag, points), options)
        self.operations.append(item)
        return item

    def text(self, tag: str, x: float, y: float, **options: object) -> object:
        item = ("text", (tag, x, y), options)
        self.operations.append(item)
        return item

    def image(self, tag: str, x: float, y: float, image: object, **options: object) -> object:
        item = ("image", (tag, x, y, image), options)
        self.operations.append(item)
        return item

    def raise_tag(self, tag: str) -> None:
        self.operations.append(("raise", (tag,), {}))


class TkCanvasBackend:
    """Adapter onto a real Tk canvas.

    ``options`` is ``Any`` only here, at the tkinter boundary: these are Tk
    item options forwarded verbatim, and tkinter types each one individually
    (``activedash``, ``activefill``, ... ). Declaring them ``object`` -- the
    honest type for "whatever the caller passed" -- makes every forwarded call
    an error against those per-option stubs. The protocol above keeps the
    checked ``object`` signature that the rest of the app is written against.
    """

    def __init__(self, canvas: tk.Canvas) -> None:
        self._canvas = canvas

    def clear_tag(self, tag: str) -> None:
        self._canvas.delete(tag)

    def rectangle(self, tag: str, x1: float, y1: float, x2: float, y2: float, **options: Any) -> int:
        return self._canvas.create_rectangle(x1, y1, x2, y2, tags=(tag,), **options)

    def oval(self, tag: str, x1: float, y1: float, x2: float, y2: float, **options: Any) -> int:
        return self._canvas.create_oval(x1, y1, x2, y2, tags=(tag,), **options)

    def line(self, tag: str, points: tuple[float, ...], **options: Any) -> int:
        if options.get("capstyle") is None:
            options.pop("capstyle", None)
        return self._canvas.create_line(*points, tags=(tag,), **options)

    def polygon(self, tag: str, points: tuple[float, ...], **options: Any) -> int:
        return self._canvas.create_polygon(*points, tags=(tag,), **options)

    def text(self, tag: str, x: float, y: float, **options: Any) -> int:
        return self._canvas.create_text(x, y, tags=(tag,), **options)

    def image(self, tag: str, x: float, y: float, image: object, **options: Any) -> int:
        return self._canvas.create_image(x, y, image=image, tags=(tag,), **options)

    def raise_tag(self, tag: str) -> None:
        self._canvas.tag_raise(tag)
