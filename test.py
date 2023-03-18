from main import BoardGUI
from stockfish import Stockfish

class Stockfish(Stockfish):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.board_fens = []

    def make_move(self, move_uci):
        self.board_fens.append(self.get_fen_position())
        self.make_moves_from_current_position([move_uci])

    def undo_move(self):
        self.set_fen_position(self.board_fens.pop())

stockfish = Stockfish()

board_gui = BoardGUI()
board_gui.add_black_engine(stockfish)

# board_gui.run()
board_gui.play()