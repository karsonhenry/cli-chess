from cli_chess.utils import config, pgn
from cli_chess.utils.config import PgnConfig
from cli_chess.utils.argparse import setup_argparse
import os
import pytest


@pytest.fixture
def pgn_cfg(monkeypatch, tmp_path):
    """PgnConfig in a temp folder"""
    config_dir = str(tmp_path) + os.sep
    monkeypatch.setattr(config, "get_config_path", lambda: config_dir)
    monkeypatch.setattr(pgn, "get_config_path", lambda: config_dir)

    test_config = PgnConfig()
    monkeypatch.setattr(pgn, "pgn_config", test_config)
    yield test_config

    # reset flag
    pgn.set_skip_pgn_for_session(False)


def test_default_save_modes_are_always(pgn_cfg):
    assert pgn_cfg.get_value(PgnConfig.Keys.OFFLINE_SAVE_MODE) == "always"
    assert pgn_cfg.get_value(PgnConfig.Keys.ONLINE_SAVE_MODE) == "always"
    assert pgn_cfg.get_value(PgnConfig.Keys.SAVE_DIRECTORY) == ""


def test_missing_keys_are_added_on_update(monkeypatch, tmp_path):
    # old config missing keys
    config_dir = str(tmp_path) + os.sep
    monkeypatch.setattr(config, "get_config_path", lambda: config_dir)
    with open(os.path.join(config_dir, "config.ini"), "w") as f:
        f.write("[pgn]\noffline_save_mode = never\n")

    test_config = PgnConfig()
    assert test_config.get_value(PgnConfig.Keys.OFFLINE_SAVE_MODE) == "never"
    assert test_config.get_value(PgnConfig.Keys.ONLINE_SAVE_MODE) == "always"
    assert test_config.get_value(PgnConfig.Keys.SAVE_DIRECTORY) == ""


def test_missing_section_is_created_on_update(monkeypatch, tmp_path):
    config_dir = str(tmp_path) + os.sep
    monkeypatch.setattr(config, "get_config_path", lambda: config_dir)
    with open(os.path.join(config_dir, "config.ini"), "w") as f:
        f.write("[game]\nblindfold_chess = False\n")

    test_config = PgnConfig()
    assert test_config.get_value(PgnConfig.Keys.OFFLINE_SAVE_MODE) == "always"
    assert test_config.get_value(PgnConfig.Keys.ONLINE_SAVE_MODE) == "always"


def test_invalid_save_mode_resets_to_default(pgn_cfg):
    pgn_cfg.set_value(PgnConfig.Keys.OFFLINE_SAVE_MODE, "sometimes")
    assert pgn_cfg.get_value(PgnConfig.Keys.OFFLINE_SAVE_MODE) == "always"

    # check file too
    assert pgn_cfg.get_key_value("pgn", PgnConfig.Keys.OFFLINE_SAVE_MODE.name) == "always"


def test_save_mode_is_not_case_sensitive(pgn_cfg):
    pgn_cfg.set_value(PgnConfig.Keys.ONLINE_SAVE_MODE, "NEVER")
    assert pgn_cfg.get_value(PgnConfig.Keys.ONLINE_SAVE_MODE) == "never"


def test_online_and_offline_save_modes_are_separate(pgn_cfg):
    pgn_cfg.set_save_mode(is_online=False, save_mode="never")
    pgn_cfg.set_save_mode(is_online=True, save_mode="ask")

    assert pgn_cfg.get_save_mode(is_online=False) == "never"
    assert pgn_cfg.get_save_mode(is_online=True) == "ask"


def test_set_save_mode_ignores_invalid_values(pgn_cfg):
    pgn_cfg.set_save_mode(is_online=False, save_mode="never")
    pgn_cfg.set_save_mode(is_online=False, save_mode="not a mode")
    assert pgn_cfg.get_save_mode(is_online=False) == "never"


@pytest.mark.parametrize("save_mode", ["always", "ask", "never"])
def test_get_pgn_save_mode_returns_config_value(pgn_cfg, save_mode):
    pgn_cfg.set_save_mode(is_online=False, save_mode=save_mode)
    pgn_cfg.set_save_mode(is_online=True, save_mode=save_mode)

    assert pgn.get_pgn_save_mode(is_online=False) == save_mode
    assert pgn.get_pgn_save_mode(is_online=True) == save_mode


def test_get_pgn_save_mode_uses_correct_game_type(pgn_cfg):
    pgn_cfg.set_save_mode(is_online=False, save_mode="always")
    pgn_cfg.set_save_mode(is_online=True, save_mode="never")

    assert pgn.get_pgn_save_mode(is_online=False) == "always"
    assert pgn.get_pgn_save_mode(is_online=True) == "never"


def test_session_flag_overrides_config(pgn_cfg):
    pgn_cfg.set_save_mode(is_online=False, save_mode="always")
    pgn.set_skip_pgn_for_session(True)

    assert pgn.get_pgn_save_mode(is_online=False) == "never"
    assert pgn.get_pgn_save_mode(is_online=True) == "never"
    # config shouldnt change
    assert pgn_cfg.get_save_mode(is_online=False) == "always"


def test_session_flag_can_be_turned_back_off(pgn_cfg):
    pgn.set_skip_pgn_for_session(True)
    pgn.set_skip_pgn_for_session(False)
    assert pgn.is_pgn_saving_skipped_for_session() is False
    assert pgn.get_pgn_save_mode(is_online=False) == "always"


def test_no_save_pgn_argument():
    args = setup_argparse().parse_args(["--no-save-pgn"])
    assert args.no_save_pgn is True

    args = setup_argparse().parse_args([])
    assert args.no_save_pgn is False


def test_save_dir_is_default_when_not_set(pgn_cfg, tmp_path):
    assert pgn.get_pgn_save_dir() == os.path.join(str(tmp_path) + os.sep, "games")


def test_save_dir_uses_custom_folder(pgn_cfg, tmp_path):
    custom_dir = os.path.join(str(tmp_path), "my_games")
    pgn_cfg.set_value(PgnConfig.Keys.SAVE_DIRECTORY, custom_dir)

    assert pgn.get_pgn_save_dir() == custom_dir
    assert os.path.isdir(custom_dir)  # should get made


def test_save_dir_falls_back_when_custom_folder_is_a_file(pgn_cfg, tmp_path):
    not_a_folder = os.path.join(str(tmp_path), "im_a_file.txt")
    with open(not_a_folder, "w") as f:
        f.write("hello")
    pgn_cfg.set_value(PgnConfig.Keys.SAVE_DIRECTORY, not_a_folder)

    assert pgn.get_pgn_save_dir() == pgn.get_default_pgn_save_dir()


def test_save_dir_falls_back_when_custom_folder_cant_be_made(pgn_cfg, monkeypatch, tmp_path):
    def broken_makedirs(*args, **kwargs):
        raise OSError("permission denied")

    custom_dir = os.path.join(str(tmp_path), "nope")
    pgn_cfg.set_value(PgnConfig.Keys.SAVE_DIRECTORY, custom_dir)
    monkeypatch.setattr(pgn.os, "makedirs", broken_makedirs)

    assert pgn.get_pgn_save_dir() == pgn.get_default_pgn_save_dir()


def test_save_dir_blank_spaces_counts_as_not_set(pgn_cfg):
    pgn_cfg.set_value(PgnConfig.Keys.SAVE_DIRECTORY, "    ")
    assert pgn.get_pgn_save_dir() == pgn.get_default_pgn_save_dir()
