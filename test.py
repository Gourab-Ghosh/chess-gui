import os
import sys
import subprocess
from chess_gui import ChessGUI

try:
    from stockfish import Stockfish
except:
    pass
else:
    class Stockfish(Stockfish):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.board_fens = []

        def make_move(self, move_uci):
            self.board_fens.append(self.get_fen_position())
            self.make_moves_from_current_position([move_uci])

        def undo_move(self):
            self.set_fen_position(self.board_fens.pop())

class Timecat:
    def __init__(self, path: str = "timecat", depth: int = 10):
        self._path = os.path.abspath(path)
        self.depth = depth
        self._stockfish = subprocess.Popen(
            self._path,
            universal_newlines=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self._has_quit_command_been_sent = False
        self._put("set color false")
        self.disable_info = True

    def _read_line(self) -> str:
        if not self._stockfish.stdout:
            raise BrokenPipeError()
        if self._stockfish.poll() is not None:
            raise Exception("The Timecat process has crashed")
        return self._stockfish.stdout.readline().strip()
    
    def _put(self, command: str) -> None:
        if not self._stockfish.stdin:
            raise BrokenPipeError()
        if self._stockfish.poll() is None and not self._has_quit_command_been_sent:
            self._stockfish.stdin.write(f"{command}\n")
            self._stockfish.stdin.flush()
            if command == "quit":
                self._has_quit_command_been_sent = True

    def make_move(self, move_uci):
        self._put("push uci {}".format(move_uci))
        print(self._read_line())

    def undo_move(self):
        self._put("pop")
        print(self._read_line())

    def get_best_move(self):
        self._put("go depth {}".format(self.depth))
        while True:
            line = self._read_line()
            if not (self.disable_info and (line.lower().startswith("info") or line.lower().startswith("pv"))):
                print(line)
            if line.startswith("Best Move"):
                best_move = line.split()[-1]
                break
        return best_move

timecat = Timecat()

board_gui = ChessGUI()
board_gui.add_black_engine(timecat)

# board_gui.run()
board_gui.play()