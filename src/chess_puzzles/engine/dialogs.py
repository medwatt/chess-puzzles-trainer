from __future__ import annotations

from dataclasses import replace
import tkinter as tk
from tkinter import messagebox, ttk

from chess_puzzles.constants import ENGINE_CONFIG_DIALOG_GEOMETRY
from chess_puzzles.engine.config import EngineConfig, EngineDefinition, new_engine_definition


class EngineConfigDialog(tk.Toplevel):
    COLUMNS = ("default", "name", "command", "threads", "time", "depth")

    def __init__(self, parent: tk.Misc, config: EngineConfig) -> None:
        super().__init__(parent, name="engineconfig", class_="ChessPuzzlesEngineConfig")
        self.title("Configure Engines")
        self.geometry(ENGINE_CONFIG_DIALOG_GEOMETRY)
        self.transient(parent)
        self.config_data = config
        self.result: EngineConfig | None = None
        self._build_table()
        self._build_buttons()
        self._populate()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def show_modal(self) -> EngineConfig | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _build_table(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.table = ttk.Treeview(frame, columns=self.COLUMNS, show="headings", selectmode="browse")
        headings = {"default": "Default", "name": "Name", "command": "Command", "threads": "CPUs", "time": "Time", "depth": "Depth"}
        for column in self.COLUMNS:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=110, stretch=column == "command")
        self.table.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.table.bind("<Double-1>", lambda _event: self._edit_selected())

    def _build_buttons(self) -> None:
        footer = ttk.Frame(self)
        footer.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(footer, text="New", command=self._new_engine).pack(side=tk.LEFT)
        ttk.Button(footer, text="Edit", command=self._edit_selected).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(footer, text="Delete", command=self._delete_selected).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(footer, text="Set as Default", command=self._set_default).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(footer, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(footer, text="OK", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

    def _populate(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)
        for engine in self.config_data.engines:
            self.table.insert(
                "",
                tk.END,
                iid=engine.engine_id,
                values=(
                    "Yes" if engine.engine_id == self.config_data.default_engine_id else "",
                    engine.name,
                    engine.command,
                    engine.threads,
                    f"{engine.time_limit_seconds:g}s",
                    engine.depth,
                ),
            )

    def _selected_engine(self) -> EngineDefinition | None:
        selection = self.table.selection()
        if not selection:
            return None
        engine_id = selection[0]
        return next((engine for engine in self.config_data.engines if engine.engine_id == engine_id), None)

    def _new_engine(self) -> None:
        engine = EngineEditDialog(self, None).show_modal()
        if engine is None:
            return
        engines = (*self.config_data.engines, engine)
        default_id = self.config_data.default_engine_id or engine.engine_id
        self.config_data = EngineConfig(engines=engines, default_engine_id=default_id)
        self._populate()

    def _edit_selected(self) -> None:
        engine = self._selected_engine()
        if engine is None:
            return
        updated = EngineEditDialog(self, engine).show_modal()
        if updated is None:
            return
        self.config_data = replace(
            self.config_data,
            engines=tuple(updated if item.engine_id == engine.engine_id else item for item in self.config_data.engines),
        )
        self._populate()

    def _delete_selected(self) -> None:
        engine = self._selected_engine()
        if engine is None or not messagebox.askyesno("Delete engine", f"Delete {engine.name}?", parent=self):
            return
        engines = tuple(item for item in self.config_data.engines if item.engine_id != engine.engine_id)
        default_id = self.config_data.default_engine_id
        if default_id == engine.engine_id:
            default_id = engines[0].engine_id if engines else ""
        self.config_data = EngineConfig(engines=engines, default_engine_id=default_id)
        self._populate()

    def _set_default(self) -> None:
        engine = self._selected_engine()
        if engine is None:
            return
        self.config_data = replace(self.config_data, default_engine_id=engine.engine_id)
        self._populate()

    def _accept(self) -> None:
        self.result = self.config_data
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class EngineEditDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, engine: EngineDefinition | None) -> None:
        super().__init__(parent, name="engineedit", class_="ChessPuzzlesEngineEdit")
        self.title("Edit Engine" if engine else "New Engine")
        self.transient(parent)
        self.resizable(False, False)
        self.engine = engine
        self.result: EngineDefinition | None = None
        self.name_var = tk.StringVar(value=engine.name if engine else "")
        self.command_var = tk.StringVar(value=engine.command if engine else "")
        self.threads_var = tk.IntVar(value=engine.threads if engine else 1)
        self.time_var = tk.DoubleVar(value=engine.time_limit_seconds if engine else 1.0)
        self.depth_var = tk.IntVar(value=engine.depth if engine else 16)

        form = ttk.Frame(self, padding=12)
        form.pack(fill=tk.BOTH, expand=True)
        self._entry(form, "Name", self.name_var, 0)
        self._entry(form, "Command", self.command_var, 1, width=52)
        self._spinbox(form, "CPUs", self.threads_var, 2, 1, 256)
        self._spinbox(form, "Time per move (seconds)", self.time_var, 3, 0.1, 300.0, increment=0.1)
        self._spinbox(form, "Depth", self.depth_var, 4, 1, 128)
        footer = ttk.Frame(self)
        footer.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(footer, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(footer, text="OK", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

    def show_modal(self) -> EngineDefinition | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int, width: int = 32) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable, width=width).grid(row=row, column=1, sticky="ew", pady=4)

    def _spinbox(self, parent: ttk.Frame, label: str, variable: tk.Variable, row: int, from_: float, to: float, increment: float = 1.0) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Spinbox(parent, textvariable=variable, from_=from_, to=to, increment=increment, width=10).grid(row=row, column=1, sticky="w", pady=4)

    def _accept(self) -> None:
        name = self.name_var.get().strip()
        command = self.command_var.get().strip()
        if not name or not command:
            messagebox.showerror("Invalid engine", "Engine name and command are required.", parent=self)
            return
        if self.engine is None:
            self.result = new_engine_definition(name, command, self.threads_var.get(), self.time_var.get(), self.depth_var.get())
        else:
            self.result = replace(
                self.engine,
                name=name,
                command=command,
                threads=self.threads_var.get(),
                time_limit_seconds=self.time_var.get(),
                depth=self.depth_var.get(),
            ).with_validated_values()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()
