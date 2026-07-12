from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from tkinter import filedialog, messagebox

import chess

from chess_puzzles.database.manager import DatabaseManagerDialog
from chess_puzzles.dialogs.choice import ChoiceDialog
from chess_puzzles.engine.config import load_engine_config
from chess_puzzles.mining import MiningCriteria, mined_to_puzzles, save_mining_settings
from chess_puzzles.mining.dialog import BlunderMineDialog
from chess_puzzles.mining.runner import MiningRunDialog
from chess_puzzles.dialogs.repertoire_import import RepertoireImportDialog
from chess_puzzles.dialogs.reset_userdata import ResetUserdataDialog
from chess_puzzles.pgn.exporter import export_puzzles_to_pgn
from chess_puzzles.pgn.repertoire import profile_pgn_file
from chess_puzzles.puzzle import Puzzle
from chess_puzzles.puzzle.tree import MoveTree
from chess_puzzles.lichess import (
    DEFAULT_LICHESS_DATABASE_FILENAME,
    DEFAULT_LICHESS_DATABASE_NAME,
    LichessCsvImporter,
    LichessImportDialog,
    save_lichess_settings,
)
from chess_puzzles.review import DueReview, due_reviews
from chess_puzzles.store import (
    DECK_KIND_REPERTOIRE,
    ContentDatabase,
    ContentMeta,
    FavoriteRef,
    now_iso,
)

if TYPE_CHECKING:
    from chess_puzzles.app.main_window import MainWindow


DATABASE_FILETYPES = (
    ("Puzzle databases", "*.cpdb"),
    ("All files", "*.*"),
)


class MainDatabaseActions:
    def __init__(self, window: MainWindow) -> None:
        self.window = window

    def _database_initialdir(self) -> str:
        return self.window.state.settings.default_database_directory or str(Path.home())

    @staticmethod
    def _puzzle_has_branches(puzzle: Puzzle) -> bool:
        tree = MoveTree.from_pgn_text(puzzle.pgn_text, puzzle.initial_fen)
        return tree is not None and tree.has_branches

    def edit_current_database(self) -> None:
        window = self.window
        if window.favorites_view:
            window._status_var.set("Open a deck to edit it (the favorites view is read-only).")
            return
        if window.database is None:
            selected = filedialog.askopenfilename(
                parent=window.root,
                title="Load database for editing",
                initialdir=self._database_initialdir(),
                filetypes=DATABASE_FILETYPES,
            )
            if not selected:
                return
            try:
                window.database = ContentDatabase.open(selected)
            except Exception as exc:
                messagebox.showerror("Could not load database", str(exc), parent=window.root)
                return
            window.database_path = Path(selected)
        # The dialog writes its edits straight through to the database, so on
        # accept we only need to reload the view at a valid index.
        if DatabaseManagerDialog(window.root, window.database).show_modal():
            window.root.title(f"Chess Puzzles Trainer - {window.database.meta.name}")
            if window.database.count() == 0:
                self.show_empty_state("Database is empty.")
                return
            window.current_index = min(max(window.current_index, 0), window.database.count() - 1)
            window.load_current_puzzle()
            window._status_var.set("Database saved.")

    def create_database_from_pgn(self) -> None:
        window = self.window
        path = filedialog.askopenfilename(
            parent=window.root,
            title="Create database from PGN",
            initialdir=self._database_initialdir(),
            filetypes=(("PGN files", "*.pgn"), ("All files", "*.*")),
        )
        if not path:
            return
        try:
            puzzles = window.loader.load_file(path)
        except Exception as exc:
            messagebox.showerror("Could not load PGN", str(exc), parent=window.root)
            return
        if not puzzles:
            messagebox.showinfo(
                "No puzzles found",
                "The selected PGN did not contain any games.",
                parent=window.root,
            )
            return
        # Variation-rich files (repertoires, annotated courses) can be split
        # so every line becomes its own drillable puzzle. Files without
        # variations import exactly as before, no question asked.
        if any(self._puzzle_has_branches(puzzle) for puzzle in puzzles):
            per_game = "One puzzle per game (variations shown after solving)"
            per_line = "One puzzle per line (drill each variation separately)"
            choice = ChoiceDialog(
                window.root,
                "PGN contains variations",
                "This file has variations. How should it be imported?",
                [per_game, per_line],
                default=per_game,
            ).show_modal()
            if choice is None:
                return
            if choice == per_line:
                try:
                    puzzles = window.loader.load_file(path, split_lines=True)
                except Exception as exc:
                    messagebox.showerror("Could not load PGN", str(exc), parent=window.root)
                    return
        pgn_path = Path(path)
        save_path = self._ask_save_path(f"{pgn_path.stem}.cpdb")
        if not save_path:
            return
        meta = ContentMeta(
            database_id=str(uuid.uuid4()),
            name=pgn_path.stem,
            source_kind="pgn",
            source_path=str(pgn_path),
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        database = self._create_database(save_path, meta, puzzles)
        if database is None:
            return
        self._use_database(database, Path(save_path))
        window._status_var.set(f"Created database with {len(puzzles)} puzzle(s).")

    def import_opening_course(self) -> None:
        """Create a repertoire deck from a course PGN, one puzzle per line.

        The heuristic course profile pre-fills the dialog (trained side,
        chapter/title headers); the user's confirmed choices drive the
        line-split load. The deck is marked ``kind=repertoire`` so training
        policy can treat it as an opening deck."""
        window = self.window
        path = filedialog.askopenfilename(
            parent=window.root,
            title="Import opening course (PGN)",
            initialdir=self._database_initialdir(),
            filetypes=(("PGN files", "*.pgn"), ("All files", "*.*")),
        )
        if not path:
            return
        window.root.configure(cursor="watch")
        window.root.update_idletasks()
        try:
            profile = profile_pgn_file(path)
        except Exception as exc:
            messagebox.showerror("Could not read PGN", str(exc), parent=window.root)
            return
        finally:
            window.root.configure(cursor="")
        if profile.game_count == 0:
            messagebox.showinfo(
                "No games found", "The selected PGN did not contain any games.", parent=window.root
            )
            return
        pgn_path = Path(path)
        choices = RepertoireImportDialog(window.root, pgn_path.stem, profile).show_modal()
        if choices is None:
            return
        try:
            puzzles = window.loader.load_file(path, split_lines=True, choices=choices)
        except Exception as exc:
            messagebox.showerror("Could not load PGN", str(exc), parent=window.root)
            return
        if not puzzles:
            messagebox.showinfo(
                "No puzzles found",
                "The selected PGN did not contain any lines.",
                parent=window.root,
            )
            return
        save_path = self._ask_save_path(f"{pgn_path.stem}.cpdb")
        if not save_path:
            return
        side_name = "White" if choices.trained_side == chess.WHITE else "Black"
        chapters = len({puzzle.theme for puzzle in puzzles if puzzle.theme})
        meta = ContentMeta(
            database_id=str(uuid.uuid4()),
            name=pgn_path.stem,
            description=f"Opening course, trained as {side_name}.",
            source_kind="pgn",
            source_path=str(pgn_path),
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        database = self._create_database(save_path, meta, puzzles)
        if database is None:
            return
        database.set_meta_value("kind", DECK_KIND_REPERTOIRE)
        self._use_database(database, Path(save_path))
        window._status_var.set(
            f"Imported course: {len(puzzles)} line(s) in {chapters} chapter(s), training as {side_name}."
        )

    def open_database(self, database_path: Path | None = None) -> None:
        window = self.window
        path = database_path
        if path is None:
            selected = filedialog.askopenfilename(
                parent=window.root,
                title="Open puzzle database",
                initialdir=self._database_initialdir(),
                filetypes=DATABASE_FILETYPES,
            )
            if not selected:
                return
            path = Path(selected)
        try:
            database = ContentDatabase.open(path)
        except Exception as exc:
            messagebox.showerror("Could not open database", str(exc), parent=window.root)
            return
        self._use_database(database, path)

    def generate_blunder_puzzles(self) -> None:
        window = self.window
        engine = load_engine_config().default_engine
        engine_ok = engine is not None and Path(engine.command).is_file()
        options = BlunderMineDialog(window.root, engine.name if engine_ok else None).show_modal()
        if options is None:
            return
        if not engine_ok:
            # The dialog disables Generate without an engine, but Return can
            # still submit it; refuse rather than crash mid-run.
            messagebox.showerror(
                "No engine", "Configure a UCI engine first (Engines menu).", parent=window.root
            )
            return
        try:
            save_mining_settings(options.to_settings())
        except OSError:
            pass
        criteria = MiningCriteria(rating_min=options.rating_min, rating_max=options.rating_max)
        mined = MiningRunDialog(
            window.root,
            engine_command=engine.command,
            engine_threads=engine.threads,
            engine_options=engine.options,
            csv_path=options.csv_path,
            count=options.count,
            criteria=criteria,
        ).show_modal()
        if not mined:
            window._status_var.set("No blunder puzzles generated.")
            return
        puzzles = mined_to_puzzles(mined)
        default_name = f"blunder_check_{options.rating_min}-{options.rating_max}.cpdb"
        save_path = self._ask_save_path(default_name)
        if not save_path:
            return
        meta = ContentMeta(
            database_id=str(uuid.uuid4()),
            name=Path(save_path).stem,
            description=(
                f"Generated blunder-check deck: rating {options.rating_min}-{options.rating_max}, "
                f"{len(puzzles)} puzzles, engine '{engine.name}'."
            ),
            source_kind="mined",
            source_path=str(options.csv_path),
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        database = self._create_database(save_path, meta, puzzles)
        if database is None:
            return
        self._use_database(database, Path(save_path))
        window._status_var.set(f"Generated {len(puzzles)} blunder puzzle(s).")

    def import_lichess_csv(self) -> None:
        window = self.window
        options = LichessImportDialog(window.root, window.theme_service.current).show_modal()
        if options is None:
            return
        try:
            save_lichess_settings(options.to_settings())
        except OSError:
            pass
        criteria = options.to_criteria()
        importer = LichessCsvImporter()
        window.root.configure(cursor="watch")
        window.root.update_idletasks()
        try:
            puzzles = importer.sample_puzzles(options.csv_path, criteria)
        except Exception as exc:
            messagebox.showerror("Could not import Lichess CSV", str(exc), parent=window.root)
            return
        finally:
            window.root.configure(cursor="")
        if not puzzles:
            messagebox.showinfo(
                "No puzzles found", "No puzzles matched the selected filters.", parent=window.root
            )
            return
        save_path = self._ask_save_path(DEFAULT_LICHESS_DATABASE_FILENAME)
        if not save_path:
            return
        meta = ContentMeta(
            database_id=str(uuid.uuid4()),
            name=DEFAULT_LICHESS_DATABASE_NAME,
            description=importer.default_description(criteria),
            source_kind="lichess",
            source_path=str(options.csv_path),
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        database = self._create_database(save_path, meta, puzzles)
        if database is None:
            return
        self._use_database(database, Path(save_path))
        window._status_var.set(f"Imported {len(puzzles)} Lichess puzzle(s).")

    def _ask_save_path(self, initialfile: str) -> str:
        return filedialog.asksaveasfilename(
            parent=self.window.root,
            title="Save puzzle database",
            initialdir=self._database_initialdir(),
            initialfile=initialfile,
            defaultextension=".cpdb",
            filetypes=DATABASE_FILETYPES,
        )

    def _create_database(
        self, save_path: str, meta: ContentMeta, puzzles
    ) -> ContentDatabase | None:
        window = self.window
        # Overwriting the deck that is currently open: release our handle first so
        # create() can replace the file (the file is locked while open on Windows)
        # and so we never keep a stale handle to the replaced database.
        if window.database is not None and window.database_path == Path(save_path):
            window.database.close()
            window.database = None
            window.database_path = None
        try:
            return ContentDatabase.create(save_path, meta, puzzles)
        except Exception as exc:
            messagebox.showerror("Could not save database", str(exc), parent=window.root)
            return None

    def _use_database(self, database: ContentDatabase, path: Path) -> None:
        self.window.user_store.update_favorite_database_path(database.database_id, str(path))
        self._activate_database(
            database,
            path,
            favorites_view=False,
            start_index=self._resume_index(database),
            title=database.meta.name,
            empty_status="Database is empty.",
        )
        self._remember_recent_database(path)
        self._announce_due_reviews(database)

    def _announce_due_reviews(self, database: ContentDatabase) -> None:
        """Transient status note so a course's due lines have a visible trigger."""
        if database.kind != DECK_KIND_REPERTOIRE:
            return
        due = due_reviews(self.window.user_store.connection, database_id=database.database_id)
        if due:
            self.window._status_var.set(
                f"{len(due)} line(s) due for review — Favorites > Review mistakes (this deck)."
            )

    def _activate_database(
        self,
        database: ContentDatabase,
        path: Path | None,
        *,
        favorites_view: bool,
        review_view: bool = False,
        start_index: int,
        title: str,
        empty_status: str,
    ) -> None:
        window = self.window
        window.cancel_computer_reply()
        window.waiting_for_continue = False
        if window.database is not None and window.database is not database:
            window.database.close()
        window.database = database
        window.database_path = path
        window.favorites_view = favorites_view
        window.review_view = review_view
        if not favorites_view:
            window.favorite_sources = []
        window.current_index = start_index if database.count() else -1
        window.root.title(f"Chess Puzzles Trainer - {title}")
        window._layout.set_welcome_visible(False)
        if window.current_index >= 0:
            window.load_current_puzzle()
        else:
            self.show_empty_state(empty_status)

    def _resume_index(self, db: ContentDatabase) -> int:
        last = self.window.user_store.get_ui(f"last_puzzle:{db.database_id}")
        idx = db.index_of_id(last) if last else None
        return idx if idx is not None else 0

    def show_empty_state(self, status: str) -> None:
        window = self.window
        window.session = None
        window._title_var.set(
            window.database.meta.name if window.database is not None else "No puzzle loaded"
        )
        window._layout.board.set_position(chess.Board())
        window.clear_puzzle_info()
        window._update_favorite_button()
        window._user_notes.clear()
        window._status_var.set(status)

    def _remember_recent_database(self, path: Path) -> None:
        window = self.window
        value = str(path)
        recent = [value]
        recent.extend(
            existing
            for existing in window.state.settings.recent_database_paths
            if existing != value
        )
        window.save_settings(recent_database_paths=tuple(recent[:10]))
        window._menu.refresh_recent_menu()

    def view_favorites(self, scope: str) -> None:
        window = self.window
        favorites = self._favorites(scope)
        if favorites is None:
            return
        if not favorites:
            window._status_var.set("No favorites yet.")
            return
        label = "All favorites" if scope == "all" else f"Favorites — {window.database.meta.name}"
        self._use_favorites_view(favorites, label)

    def export_favorites(self, scope: str) -> None:
        window = self.window
        favorites = self._favorites(scope)
        if favorites is None:
            return
        if not favorites:
            window._status_var.set("No favorites to export.")
            return
        path = filedialog.asksaveasfilename(
            parent=window.root,
            title="Export favorites to PGN",
            defaultextension=".pgn",
            filetypes=(("PGN files", "*.pgn"), ("All files", "*.*")),
        )
        if not path:
            return
        count = export_puzzles_to_pgn((puzzle for puzzle, _source in favorites), path)
        window._status_var.set(f"Exported {count} favorite(s).")

    def _favorites(self, scope: str):
        window = self.window
        if scope == "all":
            return self._all_favorites()
        if window.database is None or window.favorites_view:
            window._status_var.set("Open a deck to use its favorites.")
            return None
        database_id = window.database.database_id
        favorite_ids = window.user_store.favorite_ids(database_id)
        return [
            (puzzle, FavoriteRef(puzzle.puzzle_id, database_id, str(window.database_path)))
            for puzzle in window.database.iter_puzzles()
            if puzzle.puzzle_id in favorite_ids
        ]

    def _all_favorites(self):
        favorites = []
        by_path: dict[Path, list[FavoriteRef]] = {}
        for ref in self.window.user_store.favorite_refs():
            by_path.setdefault(Path(ref.database_path), []).append(ref)
        for path, refs in by_path.items():
            if not path.exists():
                continue
            try:
                db = ContentDatabase.open(path)
            except (OSError, sqlite3.DatabaseError, ValueError):
                continue
            try:
                refs_for_db = [ref for ref in refs if ref.database_id == db.database_id]
                for ref in refs_for_db:
                    puzzle = db.puzzle_by_id(ref.puzzle_id)
                    if puzzle is not None:
                        favorites.append((puzzle, ref))
            finally:
                db.close()
        return favorites

    def review_mistakes(self, scope: str = "all") -> None:
        """Serve the puzzles due for review as an in-memory deck.

        ``scope`` mirrors the favorites views: "deck" reviews only the open
        deck's due items (an opening course is reviewed in its own context),
        "all" is the cross-deck daily sweep. Solving them records attempts as
        usual, which is what reschedules them: due-ness is derived from the
        attempt log, so there is no review state to update here."""
        window = self.window
        if scope == "deck":
            if window.database is None or window.favorites_view:
                window._status_var.set("Open a deck to review its mistakes.")
                return
            due = due_reviews(window.user_store.connection, database_id=window.database.database_id)
            label = f"Review {window.database.meta.name}"
        else:
            due = due_reviews(window.user_store.connection)
            label = "Review"
        pairs = self._resolve_reviews(due)
        if not pairs:
            window._status_var.set("No puzzles due for review.")
            return
        self._use_favorites_view(pairs, f"{label} — {len(pairs)} due", review=True)

    def _resolve_reviews(self, due: list[DueReview]):
        """Map due reviews to their puzzle content, preserving most-overdue order.

        Attempts recorded before the locator migration have no path; those
        puzzles are served only when the currently open deck contains them."""
        window = self.window
        resolved = []
        by_path: dict[Path, list[tuple[int, DueReview]]] = {}
        for order, item in enumerate(due):
            if item.database_path:
                by_path.setdefault(Path(item.database_path), []).append((order, item))
            elif window.database is not None and not window.favorites_view:
                puzzle = window.database.puzzle_by_id(item.puzzle_id)
                if puzzle is not None:
                    ref = FavoriteRef(
                        item.puzzle_id, window.database.database_id, str(window.database_path)
                    )
                    resolved.append((order, puzzle, ref))
        for path, items in by_path.items():
            if not path.exists():
                continue
            try:
                db = ContentDatabase.open(path)
            except (OSError, sqlite3.DatabaseError, ValueError):
                continue
            try:
                for order, item in items:
                    if item.database_id != db.database_id:
                        continue
                    puzzle = db.puzzle_by_id(item.puzzle_id)
                    if puzzle is not None:
                        resolved.append(
                            (
                                order,
                                puzzle,
                                FavoriteRef(item.puzzle_id, item.database_id, item.database_path),
                            )
                        )
            finally:
                db.close()
        resolved.sort(key=lambda entry: entry[0])
        return [(puzzle, ref) for _order, puzzle, ref in resolved]

    def _use_favorites_view(self, favorites, label: str, *, review: bool = False) -> None:
        puzzles = [puzzle for puzzle, _source in favorites]
        self.window.favorite_sources = [source for _puzzle, source in favorites]
        meta = ContentMeta(
            database_id="favorites", name=label, created_at=now_iso(), updated_at=now_iso()
        )
        view = ContentDatabase.in_memory(meta, puzzles)
        self._activate_database(
            view,
            None,
            favorites_view=True,
            review_view=review,
            start_index=0,
            title=label,
            empty_status="No favorites.",
        )

    def reset_deck_userdata(self) -> None:
        """Wipe the user's own records for the open deck (never its content).

        Reloads the current puzzle afterwards, so a reset course immediately
        behaves like day one -- first-encounter demonstrations included."""
        window = self.window
        if window.database is None or window.favorites_view:
            window._status_var.set("Open a deck to reset its user data.")
            return
        store = window.user_store
        database_id = window.database.database_id
        choices = ResetUserdataDialog(
            window.root,
            window.database.meta.name,
            attempt_count=store.deck_attempt_count(database_id),
            favorite_count=store.deck_favorite_count(database_id),
            vision_count=store.vision_attempt_count(),
        ).show_modal()
        if choices is None:
            return
        deleted: list[str] = []
        if choices.attempts:
            deleted.append(f"{store.delete_deck_attempts(database_id)} attempt(s)")
        if choices.favorites:
            deleted.append(f"{store.delete_deck_favorites(database_id)} favorite(s)")
        if choices.position:
            store.delete_ui(f"last_puzzle:{database_id}")
            deleted.append("resume point")
        if choices.vision:
            deleted.append(f"{store.delete_vision_attempts()} vision drill(s)")
        window.load_current_puzzle()
        window._status_var.set(f"Deleted: {', '.join(deleted)}.")

    def delete_current_puzzle(self) -> None:
        window = self.window
        if window.favorites_view:
            window._status_var.set("Deleting puzzles is disabled in the favorites view.")
            return
        if window.session is None or window.database is None:
            return
        if not messagebox.askyesno(
            "Delete current puzzle",
            "Delete this puzzle from the current database?",
            parent=window.root,
        ):
            return
        self._remove_current_row("Puzzle deleted.")

    def _remove_current_row(self, status: str) -> None:
        window = self.window
        window.database.delete_puzzles([window.current_index + 1])
        if window.database.count() == 0:
            window.current_index = -1
            self.show_empty_state(status)
        else:
            window.current_index = min(window.current_index, window.database.count() - 1)
            window.load_current_puzzle()
            window._status_var.set(status)
