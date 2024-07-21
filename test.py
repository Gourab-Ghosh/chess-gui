import os
import sys
import subprocess
from chess_gui import ChessGUI

# try:
#     from stockfish import Stockfish
# except:
#     pass
# else:
#     class Stockfish(Stockfish):
#         def __init__(self, *args, **kwargs):
#             super().__init__(*args, **kwargs)
#             self.board_fens = []

#         def make_move(self, move_uci):
#             self.board_fens.append(self.get_fen_position())
#             self.make_moves_from_current_position([move_uci])

#         def set_fen(self, fen_position: str, send_ucinewgame_token: bool = True) -> None:
#             return super().set_fen_position(fen_position, send_ucinewgame_token)

#         def undo_move(self):
#             self.set_fen_position(self.board_fens.pop())

class Timecat:
    def __init__(self, path: str = "timecat"):
        self._path = os.path.abspath(path)

        self._timecat = subprocess.Popen(
            self._path,
            universal_newlines=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self._has_quit_command_been_sent = False
        self.disable_info = True

    def _read_line(self) -> str:
        if not self._timecat.stdout:
            raise BrokenPipeError()
        if self._timecat.poll() is not None:
            raise Exception("The Timecat process has crashed")
        return self._timecat.stdout.readline().strip()
    
    def _put(self, command: str) -> None:
        if not self._timecat.stdin:
            raise BrokenPipeError()
        if self._timecat.poll() is None and not self._has_quit_command_been_sent:
            self._timecat.stdin.write(f"{command}\n")
            self._timecat.stdin.flush()
            if command == "quit":
                self._has_quit_command_been_sent = True

    def make_move(self, move_uci):
        self._put("push uci {}".format(move_uci))

    def undo_move(self):
        self._put("pop")

    def get_best_move(self):
        self._put("go movetime 1000")
        while True:
            line = self._read_line()
            if not (self.disable_info and (line.lower().startswith("info") or line.lower().startswith("pv"))):
                print(line)
            if line.startswith("bestmove"):
                best_move = line.strip().split()[1]
                break
        return best_move
    
    def set_fen(self, fen):
        self._put("set board fen {}".format(fen))

    def quit(self):
        self._put("quit")

    def __del__(self):
        self.quit()
        del self

timecat = Timecat("dumbcat")
timecat.disable_info = False
# stockfish = Stockfish("stockfish", depth = d - 1)

board_gui = ChessGUI()
# board_gui.add_white_engine(timecat)
# board_gui.add_black_engine(stockfish)
board_gui.add_black_engine(timecat)
# board_gui.set_fen("1b2R3/8/P4k2/7p/8/7P/6K1/8 b - - 7 54")

# board_gui.run()
board_gui.play()
