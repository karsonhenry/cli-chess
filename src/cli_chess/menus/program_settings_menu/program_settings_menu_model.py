from cli_chess.menus import MultiValueMenuModel, MultiValueMenuOption, MenuCategory
from cli_chess.utils.config import game_config, terminal_config, pgn_config
from cli_chess.utils.common import VALID_COLOR_DEPTHS, COLOR_DEPTH_MAP
from cli_chess.utils.logging import log


class ProgramSettingsMenuModel(MultiValueMenuModel):
    def __init__(self):
        self.menu = self._create_menu()
        super().__init__(self.menu)

    def _create_menu(self) -> MenuCategory:
        """Create the program settings menu options"""
        menu_options = [
            MultiValueMenuOption(game_config.Keys.SHOW_BOARD_COORDINATES, "", self._get_available_game_config_options(game_config.Keys.SHOW_BOARD_COORDINATES), display_name="Show board coordinates"),  # noqa: E501
            MultiValueMenuOption(game_config.Keys.SHOW_BOARD_HIGHLIGHTS, "", self._get_available_game_config_options(game_config.Keys.SHOW_BOARD_HIGHLIGHTS), display_name="Show board highlights"),  # noqa: E501
            MultiValueMenuOption(game_config.Keys.BLINDFOLD_CHESS, "", self._get_available_game_config_options(game_config.Keys.BLINDFOLD_CHESS), display_name="Blindfold chess"),  # noqa: E501
            MultiValueMenuOption(game_config.Keys.USE_UNICODE_PIECES, "", self._get_available_game_config_options(game_config.Keys.USE_UNICODE_PIECES), display_name="Use unicode pieces"),  # noqa: E501
            MultiValueMenuOption(game_config.Keys.SHOW_MOVE_LIST_IN_UNICODE, "", self._get_available_game_config_options(game_config.Keys.SHOW_MOVE_LIST_IN_UNICODE), display_name="Show move list in unicode"),  # noqa: E501
            MultiValueMenuOption(game_config.Keys.SHOW_MATERIAL_DIFF_IN_UNICODE, "", self._get_available_game_config_options(game_config.Keys.SHOW_MATERIAL_DIFF_IN_UNICODE), display_name="Unicode material difference"),  # noqa: E501
            MultiValueMenuOption(game_config.Keys.PAD_UNICODE, "", self._get_available_game_config_options(game_config.Keys.PAD_UNICODE), display_name="Pad unicode (fix overlap)"),  # noqa: E501
            MultiValueMenuOption(terminal_config.Keys.TERMINAL_COLOR_DEPTH, "", self._get_available_color_depth_options(), display_name="Terminal color depth"),  # noqa: E501
            MultiValueMenuOption(pgn_config.Keys.OFFLINE_SAVE_MODE, "", self._get_available_pgn_save_mode_options(is_online=False), display_name="Save offline game PGNs"),
            MultiValueMenuOption(pgn_config.Keys.ONLINE_SAVE_MODE, "", self._get_available_pgn_save_mode_options(is_online=True), display_name="Save online game PGNs"),
        ]
        return MenuCategory("Program Settings", menu_options)

    @staticmethod
    def _get_available_game_config_options(key: game_config.Keys) -> list:
        """Returns a list of available game configuration options for the passed in key"""
        return ["Yes", "No"] if game_config.get_boolean(key) else ["No", "Yes"]

    @staticmethod
    def _get_available_color_depth_options() -> list:
        """Returns a list of friendly named color depth options.
           The currently set color depth will be the first in the list.
        """
        cdl = VALID_COLOR_DEPTHS.copy()
        current_color_depth = terminal_config.get_value(terminal_config.Keys.TERMINAL_COLOR_DEPTH)
        cdl.insert(0, cdl.pop(cdl.index(current_color_depth)))
        for idx, depth in enumerate(cdl):
            cdl[idx] = COLOR_DEPTH_MAP[depth]
        return cdl

    @staticmethod
    def pgn_save_mode_to_display_name(save_mode: str) -> str:
        """Save mode to menu name"""
        if save_mode == pgn_config.SAVE_MODE_ALWAYS:
            return "Always"
        elif save_mode == pgn_config.SAVE_MODE_ASK:
            return "Ask me"
        elif save_mode == pgn_config.SAVE_MODE_NEVER:
            return "Never"
        else:
            return "Always"

    @staticmethod
    def pgn_display_name_to_save_mode(display_name: str) -> str:
        """Menu name to save mode"""
        if display_name == "Always":
            return pgn_config.SAVE_MODE_ALWAYS
        elif display_name == "Ask me":
            return pgn_config.SAVE_MODE_ASK
        elif display_name == "Never":
            return pgn_config.SAVE_MODE_NEVER
        else:
            return pgn_config.SAVE_MODE_ALWAYS

    def _get_available_pgn_save_mode_options(self, is_online: bool) -> list:
        """Returns save mode options, current one first"""
        options = []
        current_save_mode = pgn_config.get_save_mode(is_online)
        options.append(self.pgn_save_mode_to_display_name(current_save_mode))

        for save_mode in pgn_config.VALID_SAVE_MODES:
            display_name = self.pgn_save_mode_to_display_name(save_mode)
            if display_name not in options:
                options.append(display_name)
        return options

    @staticmethod
    def save_pgn_save_mode_setting(is_online: bool, save_mode: str):
        """Saves the pgn save mode"""
        pgn_config.set_save_mode(is_online, save_mode)

    @staticmethod
    def save_selected_game_config_setting(key: game_config.Keys, enabled: bool):
        """Saves the selected option in the game configuration"""
        game_config.set_value(key, str(enabled))

    @staticmethod
    def save_terminal_color_depth_setting(depth: str):
        """Saves the selected option in the terminal configuration"""
        if depth in VALID_COLOR_DEPTHS:
            terminal_config.set_value(terminal_config.Keys.TERMINAL_COLOR_DEPTH, depth)
        else:
            log.error(f"Invalid color depth value: {depth}")
