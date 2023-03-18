import io
import os
import sys
import inspect
import threading

try:
    import numpy as np
    import chess
    import chess.svg
    import pygame
    import cairosvg
except:
    if "--auto-install" in sys.argv:
        python_executable = sys.executable
        req_txt_file = os.path.dirname(__file__) + os.sep + "requirements.txt"
        if not os.path.isfile(req_txt_file):
            print("Could not find requirements.txt file")
            sys.exit(1)
        with open(req_txt_file, "r") as rf:
            req_packages = [package.strip() for package in rf.read().strip().splitlines() if package.strip() and not package.strip().startswith("#")]
        os.system("{} -m ensurepip --upgrade".format(python_executable))
        os.system("{} -m pip install -U pip setuptools wheel".format(python_executable))
        if sys.platform == "win32":
            os.system("{} -m pip install -U {} pipwin".format(python_executable, " ".join(req_packages)))
            os.system("{} -m pipwin install cairocffi".format(python_executable))
        else:
            os.system("{} -m pip install -U {}".format(python_executable, " ".join(req_packages)))
    import numpy as np
    import chess
    import chess.svg
    import pygame
    import cairosvg

os.environ["SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR"] = "0"

SAVE_GAME_MOVES = False
PGN_FILE = os.path.abspath("./game_moves.txt")

roundint = lambda x: int(round(x))

def interpolate(start: int, end: int, alpha: float) -> float:
    return (1 - alpha) * start + alpha * end

def inverse_interpolate(start: float, end: float, value: float) -> np.ndarray:
    return np.true_divide(value - start, end - start)

def match_interpolate(
    new_start: float,
    new_end: float,
    old_start: float,
    old_end: float,
    old_value: float,
) -> np.ndarray:
    return interpolate(
        new_start,
        new_end,
        inverse_interpolate(old_start, old_end, old_value),
    )

chess.Board.__hash__ = lambda self: self.transposition_key()

def tuplify(*args, **kwargs):
    _hash = []
    for arg in args:
        if isinstance(arg, dict):
            _hash.append(tuplify(**arg))
            continue
        try:
            iter(arg)
        except:
            _hash.append(arg)
        else:
            _hash.append(tuplify(*arg))
    for key, value in kwargs.items():
        try:
            iter(value)
        except:
            _hash.append((key, value))
        else:
            _hash.append((key, tuplify(*value)))
    _hash.sort(key=lambda obj: hash(obj))
    _hash = tuple(_hash)
    return _hash

def render_object(obj, size: int, **kwargs):
    if isinstance(obj, chess.Board):
        svg = chess.svg.board(obj, size = size, **kwargs)
    elif isinstance(obj, chess.Piece):
        svg = chess.svg.piece(obj, size = size, **kwargs)
    else:
        return
    return svg

render_object.cache = {}

class EventHandler:

    def __init__(self, board_gui):
        self.board_gui = board_gui
        self.right_click_pressed_square = None
    
    def left_mouse_button_down(self):
        self.board_gui.dragging_piece_square = self.board_gui.get_square_from_mouse_pos()
        self.board_gui.update_board_blit()

    def left_mouse_button_up(self):
        dragging_piece = None if self.board_gui.dragging_piece_square is None else self.board_gui.board.piece_at(self.board_gui.dragging_piece_square)
        if dragging_piece is not None:
            square = self.board_gui.get_square_from_mouse_pos()
            if square is not None:
                promotion_piece_type = None
                if (chess.square_rank(square), dragging_piece.symbol()) in [(0, "p"), (7, "P")]:
                    if self.board_gui.board.is_legal(chess.Move(self.board_gui.dragging_piece_square, square, promotion = chess.QUEEN)):
                        self.board_gui.board.push(chess.Move(self.board_gui.dragging_piece_square, square))
                        promotion_piece_type = self.board_gui.get_promotion_piece_type()
                        self.board_gui.board.pop()
                move = chess.Move(self.board_gui.dragging_piece_square, square, promotion = promotion_piece_type)
                if self.board_gui.board.is_legal(move):
                    self.board_gui.push(move)
                    self.board_gui.popped_moves.clear()
        self.board_gui.dragging_piece_square = None

    def right_mouse_button_down(self):
        self.right_click_pressed_square = self.board_gui.get_square_from_mouse_pos()

    def right_mouse_button_up(self):
        right_click_released_square = self.board_gui.get_square_from_mouse_pos()
        if right_click_released_square is None:
            return
        if self.right_click_pressed_square == right_click_released_square:
            if self.right_click_pressed_square in self.board_gui.highlight_squares_dict.keys():
                self.board_gui.highlight_squares_dict.pop(self.right_click_pressed_square)
            else:
                square = self.right_click_pressed_square
                self.board_gui.highlight_squares_dict[square] = self.board_gui.HIGHLIGHT_SQUARES_COLOR_DARK if (chess.square_rank(square) + chess.square_file(square)) % 2 else self.board_gui.HIGHLIGHT_SQUARES_COLOR_LIGHT
        else:
            arrow = (self.right_click_pressed_square, right_click_released_square)
            if arrow in self.board_gui.arrows:
                self.board_gui.arrows.remove(arrow)
            else:
                self.board_gui.arrows.add(arrow)
            print("Drawing arrows not implemented correctly yet :(")
        self.right_click_pressed_square = None
        self.board_gui.update_board_blit()
    
    def left_arrow_key_down(self):
        if self.board_gui.engine_thinking():
            return
        if self.board_gui.board.move_stack:
            self.board_gui.pop()
        self.board_gui.clear_arrows_and_highlights_and_update_board()

    def right_arrow_key_down(self):
        if self.board_gui.engine_thinking():
            return
        if self.board_gui.popped_moves:
            self.board_gui.push((self.board_gui.popped_moves.pop()))
        self.board_gui.clear_arrows_and_highlights_and_update_board()

    def up_arrow_key_down(self):
        if self.board_gui.engine_thinking():
            return
        while self.board_gui.board.move_stack:
            self.board_gui.board.pop()
        self.board_gui.clear_arrows_and_highlights_and_update_board()

    def down_arrow_key_down(self):
        if self.board_gui.engine_thinking():
            return
        while self.board_gui.popped_moves:
            self.board_gui.board.push((self.board_gui.popped_moves.pop()))
        self.board_gui.clear_arrows_and_highlights_and_update_board()

    def f_key_down(self):
        self.board_gui.ORIENTATION = not self.board_gui.ORIENTATION
        # self.board_gui.update_board_blit()

    def space_key_down(self):
        engine = self.board_gui.white_engine if self.board_gui.board.turn else self.board_gui.black_engine
        if engine is None:
            return
        move = chess.Move.from_uci(engine.get_best_move())
        if move is not None:
            self.board_gui.push(move, force_push = True)
            self.board_gui.popped_moves.clear()
            self.board_gui.clear_arrows_and_highlights_and_update_board()
            self.board_gui.update_board_blit()

    def exit(self):
        self.board_gui.running = False

class BoardGUI:

    def __init__(self) -> None:
        pygame.init()

        self.RESOLUTION = roundint(0.8 * min(pygame.display.Info().current_w, pygame.display.Info().current_h))
        self.OFFSET = roundint(0.04 * self.RESOLUTION)
        self.PIECE_SHIFT = (0 * np.array([1, 1]) * self.RESOLUTION).round().astype(int)
        self.SHADOW_ALPHA_PERCENT = 0.5
        self.CIRCLE_COLOR = self.CIRCLE_COLOR_CAPTURE = (0, 0, 0)
        self.CIRCLE_COLOR_ALPHA = 40
        self.CIRCLE_RADIUS = roundint((self.RESOLUTION - 2 * self.OFFSET) / 64)
        self.CIRCLE_RADIUS_CAPTURE = roundint(4 * (self.RESOLUTION - 2 * self.OFFSET) / 64)
        self.CIRCLE_THICKNESS_CAPTURE = roundint(0.15 * self.CIRCLE_RADIUS_CAPTURE)
        self.ORIENTATION = chess.WHITE
        self.HIGHLIGHT_SQUARES_COLOR_DARK = "#ff0000"
        self.HIGHLIGHT_SQUARES_COLOR_LIGHT = "#ee0000"

        self._dragging_piece_square = None
        self.board = chess.Board()
        self.event_handler = EventHandler(self)
        self.screen = pygame.display.set_mode((self.RESOLUTION, self.RESOLUTION))
        self.piece_symbols = "pnbrqkPNBRQK"
        self.selected_piece = None
        self.popped_moves = []
        self.arrows = set()
        self.highlight_squares_dict = {}
        self.white_engine = None
        self.black_engine = None
        self._last_thread = None

        self.generate_blits()

    def generate_blits(self):
        self.pieces_blit = {piece: self.render_object(chess.Piece.from_symbol(piece), (self.RESOLUTION - 2 * self.OFFSET) / 8) for piece in self.piece_symbols}
        self.update_board_blit()

        self.circle = pygame.Surface((2*self.CIRCLE_RADIUS, 2*self.CIRCLE_RADIUS), pygame.SRCALPHA)
        pygame.draw.circle(self.circle, self.CIRCLE_COLOR_CAPTURE, (self.CIRCLE_RADIUS, self.CIRCLE_RADIUS), self.CIRCLE_RADIUS)
        self.circle.set_alpha(self.CIRCLE_COLOR_ALPHA)

        self.circle_capture = pygame.Surface((2*self.CIRCLE_RADIUS_CAPTURE, 2*self.CIRCLE_RADIUS_CAPTURE), pygame.SRCALPHA)
        pygame.draw.circle(self.circle_capture, self.CIRCLE_COLOR, (self.CIRCLE_RADIUS_CAPTURE, self.CIRCLE_RADIUS_CAPTURE), self.CIRCLE_RADIUS_CAPTURE, self.CIRCLE_THICKNESS_CAPTURE)
        self.circle_capture.set_alpha(self.CIRCLE_COLOR_ALPHA)

        self.shadow = pygame.Surface((self.RESOLUTION, self.RESOLUTION))
        self.shadow.set_alpha(roundint(self.SHADOW_ALPHA_PERCENT * 255))

    def render_object(self, obj, resolution: int, **kwargs):
        resolution = roundint(resolution)
        svg = render_object(obj, resolution, **kwargs)
        if svg is None:
            return
        png_io = io.BytesIO()
        cairosvg.svg2png(bytestring=bytes(svg, "utf8"), write_to=png_io)
        png_io.seek(0)
        surf = pygame.image.load(png_io, "png")
        return surf

    @property
    def dragging_piece_square(self):
        if self._dragging_piece_square is None:
            return
        return self._dragging_piece_square if self.ORIENTATION else chess.square_mirror(self._dragging_piece_square)

    @dragging_piece_square.setter
    def dragging_piece_square(self, square):
        if square is None:
            self._dragging_piece_square = None
            return
        self._dragging_piece_square = square if self.ORIENTATION else chess.square_mirror(square)

    def clear_arrows_and_highlights_and_update_board(self):
        self.arrows.clear()
        self.highlight_squares_dict.clear()
        self.update_board_blit()

    def update_board_blit(self):
        lastmove = self.board.move_stack[-1] if self.board.move_stack else None
        check = None
        if self.board.is_check():
            check = self.board.king(self.board.turn)
        if self.dragging_piece_square is not None:
            self.arrows.clear()
            self.highlight_squares_dict.clear()
        self.board_blit = self.render_object(
            chess.Board("8/8/8/8/8/8/8/8 w - - 0 1"),
            self.RESOLUTION,
            lastmove = lastmove,
            orientation = self.ORIENTATION,
            check = check,
            arrows = self.arrows,
            fill = self.highlight_squares_dict,
        )

    def push(self, move: chess.Move, force_push = False):
        if self.engine_thinking() and not force_push:
            return
        self.board.push(move)
        self.update_board_blit()
        for engine in {self.white_engine, self.black_engine}:
            if engine is not None:
                engine.make_move(move.uci())

    def pop(self):
        if self.engine_thinking():
            return
        move = self.board.pop()
        self.popped_moves.append(move)
        self.update_board_blit()
        for engine in {self.white_engine, self.black_engine}:
            if engine is not None:
                if inspect.signature(engine.undo_move).parameters:
                    engine.undo_move(move.uci())
                else:
                    engine.undo_move()
        return move

    def get_square_from_mouse_pos(self, mouse_pos = None):
        if mouse_pos is None:
            mouse_pos = pygame.mouse.get_pos()
        x, y = mouse_pos

        if x < self.OFFSET or x > self.RESOLUTION - self.OFFSET or y < self.OFFSET or y > self.RESOLUTION - self.OFFSET:
            return

        # Determine the row and column of the board square that the mouse is over
        row = int(match_interpolate(0, 8, self.OFFSET, self.RESOLUTION - self.OFFSET, x))
        col = int(match_interpolate(0, 8, self.OFFSET, self.RESOLUTION - self.OFFSET, y))

        # Return the square as a chess.square() object
        square = chess.square_mirror(chess.square(row, col))
        if not self.ORIENTATION:
            square = 63 - square
        if 0 <= square < 64:
            return square

    def render_board(self):
        self.screen.blit(self.board_blit, (0, 0))
        xs = np.linspace(self.OFFSET, self.RESOLUTION - self.OFFSET, 9)[:-1]
        ys = np.linspace(self.OFFSET, self.RESOLUTION - self.OFFSET, 9)[:-1]
        dragging_piece_blit = None
        for x in xs:
            for y in ys:
                square = self.get_square_from_mouse_pos((x, y))
                piece = self.board.piece_at(square)
                if piece:
                    image = self.pieces_blit[str(piece)]
                    if self.dragging_piece_square == square:
                        mouse_pos = pygame.mouse.get_pos()
                        image_rect = image.get_rect(center=mouse_pos)
                        dragging_piece_blit = (image, image_rect)
                        continue
                    image_rect = (x + self.PIECE_SHIFT[0], y + self.PIECE_SHIFT[1])
                    self.screen.blit(image, image_rect)

                if self.dragging_piece_square and not self.engine_thinking():
                    circle_coordinate = (x + (self.RESOLUTION - 2 * self.OFFSET) / 16, y + (self.RESOLUTION - 2 * self.OFFSET) / 16)
                    for move in self.board.generate_legal_moves(chess.BB_SQUARES[self.dragging_piece_square]):
                        if square == move.to_square and move.promotion in [None, chess.QUEEN]:
                            circle = self.circle_capture if self.board.is_capture(move) else self.circle
                            self.screen.blit(circle, circle.get_rect(center = circle_coordinate))

        if self.dragging_piece_square and self.engine_thinking():

            # Make shadow
            self.screen.blit(self.shadow, (0, 0))

            # Make dialog
            text = self.font.render("Engine Thinking...", True, (0, 0, 0))
            text_rect = text.get_rect(center = (self.RESOLUTION // 2, self.RESOLUTION // 2))
            self.screen.blit(text, text_rect)

        if dragging_piece_blit:
            self.screen.blit(*dragging_piece_blit)

    def get_promotion_piece_type(self):
        screen_width = screen_height = self.RESOLUTION
        dialog_width = roundint(self.RESOLUTION / 4)
        dialog_height = roundint(self.RESOLUTION / 4)
        dialog_left = (screen_width - dialog_width) // 2
        dialog_top = (screen_height - dialog_height) // 2
        dialog_rect = pygame.Rect(dialog_left, dialog_top, dialog_width, dialog_height)

        # Render board and make shadow
        self.render_board()
        self.screen.blit(self.shadow, (0, 0))

        # Draw the dialog box
        pygame.draw.rect(self.screen, (255, 255, 255), dialog_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), dialog_rect, 2)

        # Draw the buttons
        knight_rect = pygame.Rect(dialog_left + 10, dialog_top + 10, dialog_width // 2 - 15, dialog_height // 2 - 15)
        bishop_rect = pygame.Rect(dialog_left + 10, dialog_top + dialog_height // 2 + 5, dialog_width // 2 - 15, dialog_height // 2 - 15)
        rook_rect = pygame.Rect(dialog_left + dialog_width // 2 + 5, dialog_top + 10, dialog_width // 2 - 15, dialog_height // 2 - 15)
        queen_rect = pygame.Rect(dialog_left + dialog_width // 2 + 5, dialog_top + dialog_height // 2 + 5, dialog_width // 2 - 15, dialog_height // 2 - 15)

        knight_button = self.pieces_blit["n" if self.board.turn else "N"]
        bishop_button = self.pieces_blit["b" if self.board.turn else "B"]
        rook_button = self.pieces_blit["r" if self.board.turn else "R"]
        queen_button = self.pieces_blit["q" if self.board.turn else "Q"]

        pygame.draw.rect(self.screen, (192, 192, 192), knight_rect)
        pygame.draw.rect(self.screen, (192, 192, 192), bishop_rect)
        pygame.draw.rect(self.screen, (192, 192, 192), rook_rect)
        pygame.draw.rect(self.screen, (192, 192, 192), queen_rect)

        self.screen.blit(knight_button, knight_button.get_rect(center = knight_rect.center))
        self.screen.blit(bishop_button, bishop_button.get_rect(center = bishop_rect.center))
        self.screen.blit(rook_button, rook_button.get_rect(center = rook_rect.center))
        self.screen.blit(queen_button, queen_button.get_rect(center = queen_rect.center))

        pygame.display.update()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return None
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    if dialog_rect.collidepoint(x, y):
                        x -= dialog_left
                        y -= dialog_top
                        if x < dialog_width // 2:
                            if y < dialog_height // 2:
                                return chess.KNIGHT
                            else:
                                return chess.BISHOP
                        else:
                            if y < dialog_height // 2:
                                return chess.ROOK
                            else:
                                return chess.QUEEN
                    return

    def handle_events(self, event):
        if event.type in [pygame.QUIT] or (event.type == pygame.KEYDOWN and event.key in [pygame.K_ESCAPE, pygame.K_q]):
            self.event_handler.exit()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == pygame.BUTTON_LEFT:
                self.event_handler.left_mouse_button_down()

            elif event.button == pygame.BUTTON_RIGHT:
                self.event_handler.right_mouse_button_down()

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == pygame.BUTTON_LEFT:
                self.event_handler.left_mouse_button_up()

            elif event.button == pygame.BUTTON_RIGHT:
                self.event_handler.right_mouse_button_up()

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.event_handler.left_arrow_key_down()
                if self.in_play_mode:
                    self.event_handler.left_arrow_key_down()

            elif event.key == pygame.K_RIGHT:
                self.event_handler.right_arrow_key_down()
                if self.in_play_mode:
                    self.event_handler.right_arrow_key_down()

            elif event.key == pygame.K_UP:
                self.event_handler.up_arrow_key_down()

            elif event.key == pygame.K_DOWN:
                self.event_handler.down_arrow_key_down()

            elif event.key == pygame.K_f:
                self.event_handler.f_key_down()

            elif event.key == pygame.K_SPACE:
                if self.engine_thinking():
                    return
                self._last_thread = threading.Thread(target = self.event_handler.space_key_down)
                self._last_thread.start()

    def add_white_engine(self, engine):
        self.white_engine = engine
    
    def add_black_engine(self, engine):
        self.black_engine = engine
    
    def add_engine(self, engine):
        self.white_engine = self.black_engine = engine

    def engine_thinking(self):
        if self._last_thread is None:
            return False
        return self._last_thread.is_alive()

    def run(self):
        pygame.font.init()
        pygame.display.set_caption("Chess GUI")
        self.font = pygame.font.SysFont("Arial", 20)
        self.clock = pygame.time.Clock()
        self.running = True
        self.in_play_mode = False
        while self.running:
            for event in pygame.event.get():
                self.handle_events(event)
            self.render_board()
            pygame.display.update()
        pygame.quit()

    def play(self):
        pygame.font.init()
        pygame.display.set_caption("Chess GUI")
        self.font = pygame.font.SysFont("Arial", 20)
        self.clock = pygame.time.Clock()
        self.running = True
        self.in_play_mode = True
        while self.running:
            engine = self.white_engine if self.board.turn else self.black_engine
            if not self.engine_thinking() and engine:
                self.handle_events(pygame.event.Event(pygame.KEYDOWN, key = pygame.K_SPACE))
            else:
                for event in pygame.event.get():
                    self.handle_events(event)
            self.render_board()
            pygame.display.update()
        pygame.quit()