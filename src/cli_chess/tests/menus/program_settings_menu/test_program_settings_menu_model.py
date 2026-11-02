from cli_chess.menus.program_settings_menu import ProgramSettingsMenuModel
from cli_chess.menus.program_settings_menu import program_settings_menu_model
from cli_chess.utils.config import PgnConfig
from unittest.mock import Mock
import pytest


@pytest.mark.parametrize("save_mode, display_name", [
    ("always", "Always"),
    ("ask", "Ask me"),
    ("never", "Never"),
])
def test_pgn_save_mode_display_names(save_mode, display_name):
    assert ProgramSettingsMenuModel.pgn_save_mode_to_display_name(save_mode) == display_name
    assert ProgramSettingsMenuModel.pgn_display_name_to_save_mode(display_name) == save_mode

def test_unknown_pgn_values_default_to_always():
    assert ProgramSettingsMenuModel.pgn_save_mode_to_display_name("???") == "Always"
    assert ProgramSettingsMenuModel.pgn_display_name_to_save_mode("???") == "always"


def test_current_pgn_save_mode_is_listed_first(monkeypatch):
    fake_config = Mock()
    fake_config.SAVE_MODE_ALWAYS = PgnConfig.SAVE_MODE_ALWAYS
    fake_config.SAVE_MODE_ASK = PgnConfig.SAVE_MODE_ASK
    fake_config.SAVE_MODE_NEVER = PgnConfig.SAVE_MODE_NEVER
    fake_config.VALID_SAVE_MODES = PgnConfig.VALID_SAVE_MODES
    fake_config.get_save_mode = lambda is_online: "never"
    monkeypatch.setattr(program_settings_menu_model, "pgn_config", fake_config)

    options = ProgramSettingsMenuModel._get_available_pgn_save_mode_options(ProgramSettingsMenuModel, is_online=False)
    assert options == ["Never", "Always", "Ask me"]
