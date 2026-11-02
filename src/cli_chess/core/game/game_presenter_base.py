from __future__ import annotations
from cli_chess.core.game import GameViewBase, PlayableGameViewBase
from cli_chess.modules.board import BoardPresenter
from cli_chess.modules.move_list import MoveListPresenter
from cli_chess.modules.material_difference import MaterialDifferencePresenter
from cli_chess.modules.player_info import PlayerInfoPresenter
from cli_chess.modules.clock import ClockPresenter
from cli_chess.modules.premove import PremovePresenter
from cli_chess.utils import log, AlertType, RequestSuccessfullySent, EventTopics, save_game_pgn, get_pgn_save_mode
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cli_chess.core.game import GameModelBase, PlayableGameModelBase


class GamePresenterBase(ABC):
    def __init__(self, model: GameModelBase):
        self.model = model
        self.board_presenter = BoardPresenter(model.board_model)
        self.move_list_presenter = MoveListPresenter(model.move_list_model)
        self.material_diff_presenter = MaterialDifferencePresenter(model.material_diff_model)
        self.player_info_presenter = PlayerInfoPresenter(model)
        self.clock_presenter = ClockPresenter(model)
        self.view = self._get_view()

        self.model.e_game_model_updated.add_listener(self.update)
        log.debug(f"Created {type(self).__name__} (id={id(self)})")

    @abstractmethod
    def _get_view(self) -> GameViewBase:
        """Returns the view to use for this presenter"""
        pass

    @abstractmethod
    def update(self, *args, **kwargs) -> None:
        """Listens to game model updates when notified.
           See model for specific kwargs that are currently being sent.
        """
        if EventTopics.GAME_START in args:
            self.view.alert.clear_alert()

    def flip_board(self) -> None:
        """Flip the board orientation"""
        self.board_presenter.flip_board()

    def exit(self) -> None:
        """Exit current presenter/view"""
        log.debug("Exiting game presenter")
        self.model.cleanup()
        self.view.exit()


class PlayableGamePresenterBase(GamePresenterBase, ABC):
    def __init__(self, model: PlayableGameModelBase):
        self.premove_presenter = PremovePresenter(model.premove_model)
        self._game_over_handled = False
        self._waiting_on_pgn_answer = False  # for ask mode
        super().__init__(model)
        self.model = model

    @abstractmethod
    def _get_view(self) -> PlayableGameViewBase:
        """Returns the view to use for this presenter"""
        return PlayableGameViewBase(self)

    def update(self, *args, **kwargs) -> None:
        """Update method called on game model updates. Overrides base."""
        super().update(*args, **kwargs)
        if EventTopics.GAME_START in args:
            self._game_over_handled = False
            self._waiting_on_pgn_answer = False
        # Guarded too, otherwise the (MOVE_MADE, GAME_END) event that follows a
        # checkmate clears the result off the screen
        if EventTopics.MOVE_MADE in args and not self._game_over_handled:
            self.view.alert.clear_alert()
        if EventTopics.GAME_END in args and not self._game_over_handled:
            # The game end is broadcast more than once per game (e.g. the model reports
            # the game over and then rebroadcasts the event it was triaging)
            self._game_over_handled = True
            self._parse_and_present_game_over()
            self.premove_presenter.clear_premove()
            self._save_pgn()

    def user_input_received(self, inpt: str) -> None:
        """Respond to the users input. This input can either be the
           move input, or game actions (such as resign)
        """
        try:
            if self._waiting_on_pgn_answer and not self.model.game_in_progress:
                self._handle_pgn_save_answer(inpt)
                return

            inpt_lower = inpt.lower()
            if inpt_lower == "resign" or inpt_lower == "quit" or inpt_lower == "exit":
                self.resign()
            elif inpt_lower == "draw" or inpt_lower == "offer draw":
                self.offer_draw()
            elif inpt_lower == "takeback" or inpt_lower == "back" or inpt_lower == "undo":
                self.propose_takeback()
            elif inpt_lower.find("send") == 0:
                self.post_message(inpt.replace("send", "", 1))
            elif self.model.is_my_turn():
                self.make_move(inpt)
            else:
                self.model.set_premove(inpt)
        except Exception as e:
            self.view.alert.show_alert(str(e))

    def make_move(self, move: str) -> None:
        """Make the passed in move on the board"""
        try:
            self.model.make_move(move)
        except Exception as e:
            self.view.alert.show_alert(str(e))

    def propose_takeback(self) -> None:
        """Proposes a takeback"""
        try:
            self.model.propose_takeback()
        except Exception as e:
            if isinstance(e, RequestSuccessfullySent):
                self.view.alert.show_alert(str(e), AlertType.NEUTRAL)
            else:
                self.view.alert.show_alert(str(e))

    def offer_draw(self) -> None:
        """Offers a draw"""
        try:
            self.model.offer_draw()
        except Exception as e:
            if isinstance(e, RequestSuccessfullySent):
                self.view.alert.show_alert(str(e), AlertType.NEUTRAL)
            else:
                self.view.alert.show_alert(str(e))

    def resign(self) -> None:
        """Resigns the game"""
        try:
            if self.model.game_in_progress:
                self.model.resign()
            else:
                self.exit()
        except Exception as e:
            self.view.alert.show_alert(str(e))

    def post_message(self, text: str) -> None:
        """Send message to opponent"""
        try:
            self.model.post_message(text)
        except Exception as e:
            self.view.alert.show_alert(str(e))

    def is_game_in_progress(self) -> bool:
        return self.model.game_in_progress

    def _is_online_game(self) -> bool:
        """Returns True if online game"""
        if self.model.game_metadata.game_id is not None:
            return True
        else:
            return False

    def _save_pgn(self) -> None:
        """Saves pgn based on the save mode"""
        try:
            is_online = self._is_online_game()
            save_mode = get_pgn_save_mode(is_online)

            if save_mode == "never":
                log.debug("Skipping PGN save: save mode is set to never")
                return
            elif save_mode == "ask":
                self._ask_to_save_pgn()
            elif save_mode == "always":
                self._write_pgn()
            else:
                log.error(f"Unknown PGN save mode ({save_mode}), saving anyway")
                self._write_pgn()
        except Exception as e:
            log.error(f"Unexpected error saving PGN: {e}")

    def _write_pgn(self) -> None:
        """Save PGN to save locaton and print path on screen"""
        try:
            is_online = self._is_online_game()
            path = save_game_pgn(self.model.board_model, self.model.game_metadata, is_online=is_online)
            if path:
                self.view.alert.append_alert(f"Game saved: {path}")
        except Exception as e:
            log.error(f"Unexpected error saving PGN: {e}")

    def _ask_to_save_pgn(self) -> None:
        """Asks user if they want to save"""
        if not self.model.board_model.board.move_stack:
            # no moves
            log.debug("Skipping PGN save prompt: no moves were played")
            return

        self._waiting_on_pgn_answer = True
        self.view.alert.append_alert("Save this game? Type 'y' or 'save' to keep it, or 'n' or 'discard' to skip it")

    def _handle_pgn_save_answer(self, answer: str) -> None:
        """Handles save prompt answer"""
        answer_lower = answer.strip().lower()

        if answer_lower == "save" or answer_lower == "yes" or answer_lower == "y":
            self._waiting_on_pgn_answer = False
            self._write_pgn()
        elif answer_lower == "discard" or answer_lower == "no" or answer_lower == "n":
            self._waiting_on_pgn_answer = False
            self.view.alert.append_alert("Game not saved")
        elif answer_lower == "exit" or answer_lower == "quit":
            self._waiting_on_pgn_answer = False
            self.exit()
        else:
            # didnt understand it so keep waiting
            log.debug(f"Unknown answer to save prompt: {answer}")

    @abstractmethod
    def is_vs_ai(self) -> bool:
        """Inheriting classes must specify if the game
           is versus AI (offline engine or Lichess)
        """
        pass

    @abstractmethod
    def _parse_and_present_game_over(self) -> str:
        pass
