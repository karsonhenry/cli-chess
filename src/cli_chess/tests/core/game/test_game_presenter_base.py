from cli_chess.core.game import game_presenter_base
from cli_chess.core.game.game_options import GameOption
from cli_chess.core.game.offline_game import OfflineGameModel, OfflineGamePresenter
from cli_chess.utils import EventTopics
from cli_chess.utils.pgn import save_game_pgn
from chess import WHITE
from unittest.mock import Mock
import pytest


@pytest.fixture
def save_spy(monkeypatch, tmp_path):
    from cli_chess.utils import pgn
    monkeypatch.setattr(pgn, "get_pgn_save_dir", lambda: str(tmp_path))
    spy = Mock(wraps=save_game_pgn)
    monkeypatch.setattr(game_presenter_base, "save_game_pgn", spy)
    # so real config doesnt matter
    monkeypatch.setattr(game_presenter_base, "get_pgn_save_mode", lambda is_online: "always")
    return spy


@pytest.fixture
def presenter(monkeypatch, save_spy):
    from cli_chess.core.game.offline_game import offline_game_model
    monkeypatch.setattr(offline_game_model, "EngineModel", Mock())

    game_parameters = {
        GameOption.COLOR: "white",
        GameOption.VARIANT: "standard",
        GameOption.COMPUTER_SKILL_LEVEL: 1,
        GameOption.SPECIFY_ELO: False,
        GameOption.COMPUTER_ELO: 1500,
    }
    return OfflineGamePresenter(OfflineGameModel(game_parameters))


def saved_lines(presenter) -> list:
    return [line for line in presenter.view.alert._alert_label.text.split("\n") if line.startswith("Game saved:")]


def test_resignation_saves_pgn_once(presenter, save_spy, tmp_path):
    presenter.model.board_model.make_move("e4")
    presenter.model.board_model.handle_resignation(WHITE)

    assert save_spy.call_count == 1
    assert len(saved_lines(presenter)) == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_checkmate_saves_pgn_once_and_keeps_result(presenter, save_spy, tmp_path):
    for move in ("f3", "e5", "g4", "Qh4"):
        presenter.model.board_model.make_move(move)

    assert save_spy.call_count == 1
    assert len(saved_lines(presenter)) == 1
    assert len(list(tmp_path.iterdir())) == 1
    assert "Checkmate" in presenter.view.alert._alert_label.text


def test_game_start_allows_the_next_game_to_save(presenter, save_spy):
    presenter.model.board_model.make_move("e4")
    presenter.model.board_model.handle_resignation(WHITE)
    save_spy.reset_mock()

    presenter.model._notify_game_model_updated(EventTopics.GAME_START)
    presenter.model._notify_game_model_updated(EventTopics.GAME_END)

    assert save_spy.call_count == 1
    assert len(saved_lines(presenter)) == 1


def set_save_mode(monkeypatch, offline_mode: str, online_mode: str = "always"):
    """Fakes the save mode"""
    def fake_get_pgn_save_mode(is_online):
        if is_online:
            return online_mode
        else:
            return offline_mode
    monkeypatch.setattr(game_presenter_base, "get_pgn_save_mode", fake_get_pgn_save_mode)


def test_never_save_mode_does_not_save(presenter, save_spy, tmp_path, monkeypatch):
    set_save_mode(monkeypatch, "never")
    presenter.model.board_model.make_move("e4")
    presenter.model.board_model.handle_resignation(WHITE)

    assert save_spy.call_count == 0
    assert len(saved_lines(presenter)) == 0
    assert len(list(tmp_path.iterdir())) == 0


def test_offline_game_uses_offline_save_mode(presenter, save_spy, tmp_path, monkeypatch):
    # offline game so online setting shouldnt matter
    set_save_mode(monkeypatch, offline_mode="always", online_mode="never")
    presenter.model.board_model.make_move("e4")
    presenter.model.board_model.handle_resignation(WHITE)

    assert save_spy.call_count == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_ask_save_mode_shows_prompt_and_waits(presenter, save_spy, tmp_path, monkeypatch):
    set_save_mode(monkeypatch, "ask")
    presenter.model.board_model.make_move("e4")
    presenter.model.board_model.handle_resignation(WHITE)

    assert save_spy.call_count == 0
    assert presenter._waiting_on_pgn_answer is True
    assert "Save this game?" in presenter.view.alert._alert_label.text
    assert len(list(tmp_path.iterdir())) == 0


def test_ask_save_mode_with_no_moves_does_not_prompt(presenter, save_spy, monkeypatch):
    set_save_mode(monkeypatch, "ask")
    presenter.model.board_model.handle_resignation(WHITE)

    assert presenter._waiting_on_pgn_answer is False
    assert "Save this game?" not in presenter.view.alert._alert_label.text


def test_new_game_clears_the_save_prompt(presenter, monkeypatch):
    set_save_mode(monkeypatch, "ask")
    presenter.model.board_model.make_move("e4")
    presenter.model.board_model.handle_resignation(WHITE)
    presenter.model._notify_game_model_updated(EventTopics.GAME_START)

    assert presenter._waiting_on_pgn_answer is False


def test_ask_save_mode_answer_save(presenter, save_spy, tmp_path, monkeypatch):
    set_save_mode(monkeypatch, "ask")
    presenter.model.board_model.make_move("e4")
    presenter.model.board_model.handle_resignation(WHITE)
    presenter.user_input_received("save")

    assert save_spy.call_count == 1
    assert len(saved_lines(presenter)) == 1
    assert presenter._waiting_on_pgn_answer is False


def start_ask_prompt(presenter, monkeypatch):
    set_save_mode(monkeypatch, "ask")
    presenter.model.board_model.make_move("e4")
    presenter.model.board_model.handle_resignation(WHITE)


def test_ask_save_mode_answer_y(presenter, save_spy, tmp_path, monkeypatch):
    start_ask_prompt(presenter, monkeypatch)
    presenter.user_input_received("y")

    assert save_spy.call_count == 1
    assert len(list(tmp_path.iterdir())) == 1
    assert presenter._waiting_on_pgn_answer is False


def test_ask_save_mode_answer_n(presenter, save_spy, tmp_path, monkeypatch):
    start_ask_prompt(presenter, monkeypatch)
    presenter.user_input_received("n")

    assert save_spy.call_count == 0
    assert len(list(tmp_path.iterdir())) == 0
    assert "Game not saved" in presenter.view.alert._alert_label.text
    assert presenter._waiting_on_pgn_answer is False


def test_ask_save_mode_answer_caps(presenter, save_spy, tmp_path, monkeypatch):
    start_ask_prompt(presenter, monkeypatch)
    presenter.user_input_received(" YES ")

    assert save_spy.call_count == 1
    assert len(list(tmp_path.iterdir())) == 1
    assert presenter._waiting_on_pgn_answer is False


def test_ask_save_mode_exit(presenter, save_spy, monkeypatch):
    start_ask_prompt(presenter, monkeypatch)
    exit_spy = Mock()
    monkeypatch.setattr(presenter, "exit", exit_spy)
    presenter.user_input_received("exit")

    assert exit_spy.call_count == 1
    assert save_spy.call_count == 0
    assert presenter._waiting_on_pgn_answer is False


def test_ask_save_mode_quit(presenter, save_spy, monkeypatch):
    start_ask_prompt(presenter, monkeypatch)
    exit_spy = Mock()
    monkeypatch.setattr(presenter, "exit", exit_spy)
    presenter.user_input_received("quit")

    assert exit_spy.call_count == 1
    assert save_spy.call_count == 0
    assert presenter._waiting_on_pgn_answer is False


def test_ask_save_mode_random_answer_keeps_waiting(presenter, save_spy, monkeypatch):
    start_ask_prompt(presenter, monkeypatch)
    presenter.user_input_received("maybe")

    assert save_spy.call_count == 0
    assert presenter._waiting_on_pgn_answer is True


def test_ask_save_mode_discard_keeps_game_over_message(presenter, save_spy, monkeypatch):
    set_save_mode(monkeypatch, "ask")
    for move in ("f3", "e5", "g4", "Qh4"):
        presenter.model.board_model.make_move(move)
    presenter.user_input_received("n")

    assert "Checkmate" in presenter.view.alert._alert_label.text
    assert "Game not saved" in presenter.view.alert._alert_label.text
    assert save_spy.call_count == 0


def test_ask_save_mode_answer_discard(presenter, save_spy, tmp_path, monkeypatch):
    start_ask_prompt(presenter, monkeypatch)
    presenter.user_input_received("discard")

    assert save_spy.call_count == 0
    assert len(list(tmp_path.iterdir())) == 0
    assert presenter._waiting_on_pgn_answer is False
