from __future__ import annotations

import io
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import font as tkfont
from tkinter import ttk

import chess
import chess.pgn

from chess_puzzles.board import BoardPresenter, BoardShortcuts, BoardView
from chess_puzzles.board.annotations import BoardAnnotations
from chess_puzzles.board.board_state import BoardCapabilities
from chess_puzzles.constants import PGN_VIEWER_GEOMETRY, PGN_VIEWER_MINSIZE
from chess_puzzles.pgn.comments import ParsedComment, parse_comment
from chess_puzzles.puzzle import Puzzle
from chess_puzzles.settings.theme_repository import UiTheme
from chess_puzzles.shortcuts import guarded_shortcut


_VARIATION_INDENT_PX = 22


@dataclass(slots=True)
class _ViewNode:
    """One reachable position: the board after a move plus its display state."""

    board: chess.Board
    move: chess.Move | None
    annotations: BoardAnnotations
    parent: int
    children: list[int] = field(default_factory=list)


class PgnViewer(tk.Toplevel):
    """Game viewer with clickable mainline, variations, and comment blocks."""

    def __init__(
        self,
        parent: tk.Misc,
        puzzle: Puzzle,
        pgn_text: str,
        *,
        presenter: BoardPresenter,
        player_color: chess.Color,
        theme: UiTheme,
    ) -> None:
        super().__init__(parent, name="pgnviewer", class_="ChessPuzzlesPgnViewer")
        self.title(f"PGN - {puzzle.title}")
        self.geometry(PGN_VIEWER_GEOMETRY)
        self.minsize(*PGN_VIEWER_MINSIZE)
        # Modeless work window: keep native minimize/maximize controls.
        self._theme = theme
        self.game = chess.pgn.read_game(io.StringIO(pgn_text))
        self._nodes: list[_ViewNode] = []
        self.current_position = 0
        self._at_line_start = True
        self._presenter = presenter

        root = ttk.Frame(self, padding=8)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)
        root.rowconfigure(1, weight=1)

        self.board = BoardView(
            root,
            capabilities=BoardCapabilities(movable_pieces=False, annotations=True, legal_move_hints=False),
        )
        self.board.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        self._presenter.register(self.board)
        self.board.set_orientation(player_color)
        BoardShortcuts(self, self.board).bind()
        self.bind("<Destroy>", self._on_destroy)

        self._title_label = ttk.Label(
            root,
            text=puzzle.title,
            font=("TkDefaultFont", 11, "bold"),
            justify=tk.LEFT,
            anchor=tk.W,
            # width=1 keeps the label from requesting its full single-line text
            # width, which would otherwise widen this column for longer titles
            # and steal width from the board.
            width=1,
        )
        self._title_label.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        text_frame = ttk.Frame(root)
        text_frame.grid(row=1, column=1, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=1,
            font="TkDefaultFont",
            cursor="arrow",
            padx=12,
            pady=10,
            spacing2=2,
            background=self._theme.field_bg,
            foreground=self._theme.field_text,
        )
        scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self._configure_tags()

        controls = ttk.Frame(root)
        controls.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for label, command in (
            ("Start", self.go_start),
            ("Previous", self.previous_move),
            ("Next", self.next_move),
            ("End", self.go_end),
        ):
            ttk.Button(controls, text=label, command=command, takefocus=False).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(controls, text="Close", command=self.destroy, takefocus=False).pack(side=tk.RIGHT)

        self.bind("<Left>", guarded_shortcut(self.previous_move))
        self.bind("<Right>", guarded_shortcut(self.next_move))
        self.bind("<Home>", guarded_shortcut(self.go_start))
        self.bind("<End>", guarded_shortcut(self.go_end))
        self._title_label.bind(
            "<Configure>", lambda event: self._title_label.configure(wraplength=max(180, event.width - 8))
        )

        self._render()
        self.go_start()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self:
            self._presenter.unregister(self.board)

    # --- navigation -----------------------------------------------------

    def go_start(self) -> None:
        self._show_position(0)

    def go_end(self) -> None:
        index = self.current_position
        while self._nodes[index].children:
            index = self._nodes[index].children[0]
        self._show_position(index)

    def previous_move(self) -> None:
        self._show_position(self._nodes[self.current_position].parent)

    def next_move(self) -> None:
        children = self._nodes[self.current_position].children
        if children:
            self._show_position(children[0])

    def _show_position(self, index: int) -> None:
        forward_one = index != self.current_position and self._nodes[index].parent == self.current_position
        self.current_position = index
        node = self._nodes[index]
        if node.move is None:
            self.board.set_position(node.board)
            self.board.set_last_move(None)
        elif forward_one:
            self.board.advance_position(node.board, node.move)
        else:
            self.board.set_position(node.board)
            self.board.set_last_move(node.move)
        self.board.set_annotations(node.annotations)
        self._highlight_current_move()

    def _highlight_current_move(self) -> None:
        self.text.tag_remove("current", "1.0", tk.END)
        ranges = self.text.tag_ranges(f"n{self.current_position}")
        if len(ranges) >= 2:
            self.text.tag_add("current", ranges[0], ranges[1])
            self.text.see(ranges[0])

    # --- rendering ------------------------------------------------------

    def _configure_tags(self) -> None:
        theme = self._theme
        move_font = tkfont.Font(font="TkDefaultFont")
        move_font.configure(weight="bold")
        self.text.tag_configure("num", foreground=theme.muted_text)
        self.text.tag_configure("mv", foreground=theme.accent, font=move_font)
        self.text.tag_configure("var", foreground=theme.muted_text)
        self.text.tag_configure("varmv", foreground=theme.accent)
        self.text.tag_configure(
            "comment",
            foreground=theme.field_text,
            lmargin1=14,
            lmargin2=14,
            spacing1=6,
            spacing3=6,
        )
        self.text.tag_configure("result", foreground=theme.muted_text, spacing1=8)
        for depth in range(1, 9):
            indent = 14 + depth * _VARIATION_INDENT_PX
            self.text.tag_configure(f"d{depth}", lmargin1=indent, lmargin2=indent + 12)
        # Configured last so its colors win over mv/varmv on the active move.
        self.text.tag_configure("current", background=theme.menu_active_bg, foreground=theme.menu_active_text)
        self.text.tag_bind("click", "<Enter>", lambda _event: self.text.configure(cursor="hand2"))
        self.text.tag_bind("click", "<Leave>", lambda _event: self.text.configure(cursor="arrow"))

    def _render(self) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self._nodes.clear()
        self._at_line_start = True
        if self.game is None:
            self.text.insert(tk.END, "No PGN is stored for this puzzle.")
            self.text.configure(state=tk.DISABLED)
            return

        start_board = self.game.board()
        intro = parse_comment(self.game.comment)
        self._nodes.append(
            _ViewNode(
                board=start_board.copy(stack=False),
                move=None,
                annotations=intro.annotations,
                parent=0,
            )
        )
        if intro.prose:
            self._insert(intro.prose + "\n", "comment")
        self._write_line(self.game, start_board, view_parent=0, depth=0)

        result = self.game.headers.get("Result", "*").strip()
        if result and result != "*":
            self._newline()
            self._insert(f"Result: {result}", "result")
        self.text.configure(state=tk.DISABLED)

    def _write_line(self, pgn_parent: chess.pgn.GameNode, board: chess.Board, view_parent: int, depth: int) -> None:
        """Write pgn_parent's principal line; alternatives become sub-lines."""
        need_number = True
        while pgn_parent.variations:
            main_child = pgn_parent.variations[0]
            board_before = board.copy(stack=False)
            view_index, parsed = self._append_move(main_child, board, view_parent, depth, need_number)
            need_number = False

            if parsed.prose:
                if depth == 0:
                    self._newline()
                    self._insert(parsed.prose + "\n", "comment")
                else:
                    self._insert(parsed.inline_prose + " ", "var", f"d{depth}")
                need_number = True

            for alternative in pgn_parent.variations[1:]:
                self._write_alternative(alternative, board_before, view_parent, depth + 1)
                need_number = True

            pgn_parent = main_child
            view_parent = view_index

    def _write_alternative(
        self,
        start_node: chess.pgn.GameNode,
        board_before: chess.Board,
        view_parent: int,
        depth: int,
    ) -> None:
        self._newline()
        self._insert("( ", "var", f"d{depth}")
        board = board_before.copy(stack=False)
        view_index, parsed = self._append_move(start_node, board, view_parent, depth, need_number=True)
        if parsed.prose:
            self._insert(parsed.inline_prose + " ", "var", f"d{depth}")
        self._write_line(start_node, board, view_index, depth)
        self._insert(")", "var", f"d{depth}")
        self._insert("\n")

    def _append_move(
        self,
        pgn_node: chess.pgn.GameNode,
        board: chess.Board,
        view_parent: int,
        depth: int,
        need_number: bool,
    ) -> tuple[int, ParsedComment]:
        """Record the position after pgn_node's move and write the move text."""
        number_text = ""
        if board.turn == chess.WHITE:
            number_text = f"{board.fullmove_number}. "
        elif need_number:
            number_text = f"{board.fullmove_number}... "
        san = board.san(pgn_node.move)
        board.push(pgn_node.move)

        parsed = parse_comment(pgn_node.comment)
        view_index = len(self._nodes)
        self._nodes.append(
            _ViewNode(
                board=board.copy(stack=False),
                move=pgn_node.move,
                annotations=parsed.annotations,
                parent=view_parent,
            )
        )
        self._nodes[view_parent].children.append(view_index)

        depth_tag = (f"d{depth}",) if depth > 0 else ()
        number_tag = "var" if depth > 0 else "num"
        move_tag = "varmv" if depth > 0 else "mv"
        if number_text:
            self._insert(number_text, number_tag, *depth_tag)
        node_tag = f"n{view_index}"
        self._insert(san, move_tag, node_tag, "click", *depth_tag)
        self._insert(" ", number_tag, *depth_tag)
        self.text.tag_bind(node_tag, "<Button-1>", lambda _event, index=view_index: self._show_position(index))
        return view_index, parsed

    def _insert(self, content: str, *tags: str) -> None:
        self.text.insert(tk.END, content, tags)
        self._at_line_start = content.endswith("\n")

    def _newline(self) -> None:
        if not self._at_line_start:
            self._insert("\n")
