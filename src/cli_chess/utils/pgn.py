from __future__ import annotations

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import chess

from cli_chess.utils.config import get_config_path, pgn_config
from cli_chess.utils.logging import log

if TYPE_CHECKING:
    from cli_chess.modules.board import BoardModel
    from cli_chess.core.game.game_metadata import GameMetadata


_STANDARD_START_FEN = chess.STARTING_FEN
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

# for --no-save-pgn
_skip_pgn_saving_this_session = False


def set_skip_pgn_for_session(skip: bool) -> None:
    """Turns off pgn saving for this session only"""
    global _skip_pgn_saving_this_session
    if skip:
        _skip_pgn_saving_this_session = True
        log.info("PGN saving disabled for this session (--no-save-pgn)")
    else:
        _skip_pgn_saving_this_session = False


def is_pgn_saving_skipped_for_session() -> bool:
    """Returns True if saving is off this session"""
    if _skip_pgn_saving_this_session:
        return True
    else:
        return False


def get_default_pgn_save_dir() -> str:
    """Returns default games folder"""
    return os.path.join(get_config_path(), "games")


def _is_usable_dir(path: str) -> bool:
    """Checks if we can save to this folder"""
    if not path:
        return False

    if os.path.exists(path):
        if os.path.isdir(path):
            if os.access(path, os.W_OK):
                return True
            else:
                log.error(f"PGN save directory is not writable: {path}")
                return False
        else:
            log.error(f"PGN save directory is a file, not a folder: {path}")
            return False

    # try making it
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        log.error(f"Unable to create PGN save directory {path}: {e}")
        return False


def get_pgn_save_dir() -> str:
    """Returns the pgn save folder. Uses default if custom one doesnt work"""
    default_dir = get_default_pgn_save_dir()
    custom_dir = pgn_config.get_value(pgn_config.Keys.SAVE_DIRECTORY)

    if custom_dir is None or custom_dir.strip() == "":
        return default_dir

    # for ~ and $HOME
    custom_dir = os.path.expanduser(os.path.expandvars(custom_dir.strip()))

    if _is_usable_dir(custom_dir):
        return custom_dir
    else:
        log.warning(f"Falling back to the default PGN save directory: {default_dir}")
        return default_dir


def get_pgn_save_mode(is_online: bool) -> str:
    """Returns always, ask, or never"""
    if is_pgn_saving_skipped_for_session():
        return pgn_config.SAVE_MODE_NEVER

    save_mode = pgn_config.get_save_mode(is_online)
    if save_mode == pgn_config.SAVE_MODE_ALWAYS:
        return pgn_config.SAVE_MODE_ALWAYS
    elif save_mode == pgn_config.SAVE_MODE_ASK:
        return pgn_config.SAVE_MODE_ASK
    elif save_mode == pgn_config.SAVE_MODE_NEVER:
        return pgn_config.SAVE_MODE_NEVER
    else:
        # shouldnt happen
        return pgn_config.SAVE_MODE_ALWAYS


def _slug(value: Optional[str], fallback: str) -> str:
    if not value:
        return fallback
    cleaned = _FILENAME_SAFE.sub("_", value).strip("_")
    return cleaned or fallback


def _player_name(metadata, color: chess.Color) -> str:
    player = metadata.players[color]
    name = player.name or "?"
    if player.title:
        return f"{player.title} {name}"
    return name


def _result_string(metadata) -> str:
    winner = metadata.game_status.winner
    status = metadata.game_status.status
    if winner == "white":
        return "1-0"
    if winner == "black":
        return "0-1"
    if status:
        return "1/2-1/2"
    return "*"


def _time_control(metadata) -> Optional[str]:
    clock = metadata.clocks[chess.WHITE]
    if clock.time is None or clock.increment is None:
        return None
    base_seconds = clock.time // 1000 if clock.units == "ms" else clock.time * 60
    return f"{base_seconds}+{clock.increment}"


def build_pgn_game(board_model: "BoardModel", metadata: "GameMetadata", is_online: bool):
    """Builds PGN from metadata"""
    import chess.pgn
    game = chess.pgn.Game.from_board(board_model.board)

    headers = game.headers
    headers["Event"] = "cli-chess online" if is_online else "cli-chess offline"
    headers["Site"] = f"lichess.org/{metadata.game_id}" if is_online and metadata.game_id else "local"
    headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    headers["Round"] = "?"
    headers["White"] = _player_name(metadata, chess.WHITE)
    headers["Black"] = _player_name(metadata, chess.BLACK)
    headers["Result"] = _result_string(metadata)

    white_rating = metadata.players[chess.WHITE].rating
    black_rating = metadata.players[chess.BLACK].rating
    if white_rating:
        headers["WhiteElo"] = str(white_rating)
    if black_rating:
        headers["BlackElo"] = str(black_rating)

    tc = _time_control(metadata)
    headers["TimeControl"] = tc if tc else "-"

    variant = board_model.get_variant_name()
    if variant and variant != "chess":
        headers["Variant"] = variant

    if board_model.initial_fen and board_model.initial_fen != _STANDARD_START_FEN:
        headers["SetUp"] = "1"
        headers["FEN"] = board_model.initial_fen

    if metadata.game_status.status:
        headers["Termination"] = str(metadata.game_status.status)

    return game


def save_game_pgn(board_model: "BoardModel", metadata: "GameMetadata", is_online: bool) -> Optional[str]:
    """Creates PGN and returns full path of the file or none if no moves were present"""
    if not board_model.board.move_stack:
        log.debug("Skipping PGN save: no moves were played")
        return None

    try:
        import chess.pgn
        game = build_pgn_game(board_model, metadata, is_online)
        save_dir = get_pgn_save_dir()
        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        white = _slug(metadata.players[chess.WHITE].name, "white")
        black = _slug(metadata.players[chess.BLACK].name, "black")
        filename = f"{timestamp}-{white}_vs_{black}.pgn"
        full_path = os.path.join(save_dir, filename)

        with open(full_path, "w", encoding="utf-8") as f:
            exporter = chess.pgn.FileExporter(f)
            game.accept(exporter)

        log.info(f"Saved game PGN to {full_path}")
        return full_path
    except Exception as e:
        log.error(f"Failed to save PGN: {e}")
        return None
