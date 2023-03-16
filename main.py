import io
import os
import numpy as np
import chess
import chess.svg
import pygame
import cairosvg
import threading

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

def render_object(obj, size: int, **kwargs):
    if isinstance(obj, chess.Board):
        svg = chess.svg.board(obj, size = size, **kwargs)
    elif isinstance(obj, chess.Piece):
        svg = chess.svg.piece(obj, size = size, **kwargs)
    else:
        return
    return svg

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
        if self.board_gui.board.move_stack:
            self.board_gui.popped_moves.append(self.board_gui.pop())
        self.board_gui.clear_arrows_and_highlights_and_update_board()

    def right_arrow_key_down(self):
        if self.board_gui.popped_moves:
            self.board_gui.push((self.board_gui.popped_moves.pop()))
        self.board_gui.clear_arrows_and_highlights_and_update_board()

    def up_arrow_key_down(self):
        while self.board_gui.board.move_stack:
            self.board_gui.popped_moves.append(self.board_gui.board.pop())
        self.board_gui.clear_arrows_and_highlights_and_update_board()

    def down_arrow_key_down(self):
        while self.board_gui.popped_moves:
            self.board_gui.board.push((self.board_gui.popped_moves.pop()))
        self.board_gui.clear_arrows_and_highlights_and_update_board()

    def f_key_down(self):
        self.board_gui.ORIENTATION = not self.board_gui.ORIENTATION
        self.board_gui.dragging_piece_square = None
        self.board_gui.update_board_blit()
    
    def exit(self):
        self.board_gui.running = False

class BoardGUI:

    RESOLUTION = 800
    OFFSET = roundint(0.04 * RESOLUTION)
    PIECE_SHIFT = (0 * np.array([1, 1]) * RESOLUTION).round().astype(int)
    SHADOW_ALPHA = 0.5
    CIRCLE_COLOR = CIRCLE_COLOR_CAPTURE = (0, 0, 0)
    CIRCLE_COLOR_ALPHA = 40
    CIRCLE_RADIUS = roundint((RESOLUTION - 2 * OFFSET) / 64)
    CIRCLE_RADIUS_CAPTURE = roundint(4 * (RESOLUTION - 2 * OFFSET) / 64)
    CIRCLE_THICKNESS_CAPTURE = roundint(0.15 * CIRCLE_RADIUS_CAPTURE)
    ORIENTATION = chess.WHITE
    HIGHLIGHT_SQUARES_COLOR_DARK = "#ff0000"
    HIGHLIGHT_SQUARES_COLOR_LIGHT = "#ee0000"

    def __init__(self) -> None:
        self._dragging_piece_square = None
        self.board = chess.Board()
        self.event_handler = EventHandler(self)
        self.screen = pygame.display.set_mode((self.RESOLUTION, self.RESOLUTION))
        self.piece_symbols = "pnbrqkPNBRQK"
        self.pieces_blit = {piece: self.render_object(chess.Piece.from_symbol(piece), (self.RESOLUTION - 2 * self.OFFSET) / 8) for piece in self.piece_symbols}
        self.selected_piece = None
        self.popped_moves = []
        self.arrows = set()
        self.highlight_squares_dict = {}
        self.update_board_blit()

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

    def push(self, move):
        self.board.push(move)
        self.update_board_blit()

    def pop(self):
        move = self.board.pop()
        if self.board.move_stack:
            self.update_board_blit()
        else:
            self.update_board_blit()
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

                if self.dragging_piece_square:
                    circle_coordinate = (x + (self.RESOLUTION - 2 * self.OFFSET) / 16, y + (self.RESOLUTION - 2 * self.OFFSET) / 16)
                    for move in self.board.generate_legal_moves(chess.BB_SQUARES[self.dragging_piece_square]):
                        if square == move.to_square and move.promotion in [None, chess.QUEEN]:
                            radius = self.CIRCLE_RADIUS_CAPTURE if self.board.is_capture(move) else self.CIRCLE_RADIUS
                            color = self.CIRCLE_COLOR_CAPTURE if self.board.is_capture(move) else self.CIRCLE_COLOR
                            thickness = self.CIRCLE_THICKNESS_CAPTURE if self.board.is_capture(move) else 0
                            alpha = self.CIRCLE_COLOR_ALPHA
                            circle = pygame.Surface((2*radius, 2*radius), pygame.SRCALPHA)
                            pygame.draw.circle(circle, color, (radius, radius), radius, thickness)
                            circle.set_alpha(alpha)
                            self.screen.blit(circle, circle.get_rect(center = circle_coordinate))

        if dragging_piece_blit:
            self.screen.blit(*dragging_piece_blit)

    def get_promotion_piece_type(self):
        font = pygame.font.SysFont(None, 24)
        screen_width, screen_height = self.screen.get_size()
        dialog_width = 200
        dialog_height = 100
        dialog_left = (screen_width - dialog_width) // 2
        dialog_top = (screen_height - dialog_height) // 2
        dialog_rect = pygame.Rect(dialog_left, dialog_top, dialog_width, dialog_height)

        # Render board and make shadow
        self.render_board()
        shadow = pygame.Surface((self.RESOLUTION, self.RESOLUTION))
        shadow.set_alpha(roundint(self.SHADOW_ALPHA * 255))
        self.screen.blit(shadow, (0, 0))

        # Draw the dialog box
        pygame.draw.rect(self.screen, (255, 255, 255), dialog_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), dialog_rect, 2)

        # Draw the buttons
        knight_rect = pygame.Rect(dialog_left + 10, dialog_top + 10, dialog_width // 2 - 15, dialog_height // 2 - 15)
        bishop_rect = pygame.Rect(dialog_left + 10, dialog_top + dialog_height // 2 + 5, dialog_width // 2 - 15, dialog_height // 2 - 15)
        rook_rect = pygame.Rect(dialog_left + dialog_width // 2 + 5, dialog_top + 10, dialog_width // 2 - 15, dialog_height // 2 - 15)
        queen_rect = pygame.Rect(dialog_left + dialog_width // 2 + 5, dialog_top + dialog_height // 2 + 5, dialog_width // 2 - 15, dialog_height // 2 - 15)

        knight_button = font.render("Knight", True, (0, 0, 0))
        bishop_button = font.render("Bishop", True, (0, 0, 0))
        rook_button = font.render("Rook", True, (0, 0, 0))
        queen_button = font.render("Queen", True, (0, 0, 0))

        pygame.draw.rect(self.screen, (192, 192, 192), knight_rect)
        pygame.draw.rect(self.screen, (192, 192, 192), bishop_rect)
        pygame.draw.rect(self.screen, (192, 192, 192), rook_rect)
        pygame.draw.rect(self.screen, (192, 192, 192), queen_rect)

        self.screen.blit(knight_button, knight_rect.move(10, 5))
        self.screen.blit(bishop_button, bishop_rect.move(10, 5))
        self.screen.blit(rook_button, rook_rect.move(10, 5))
        self.screen.blit(queen_button, queen_rect.move(10, 5))

        pygame.display.update()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
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

            elif event.key == pygame.K_RIGHT:
                self.event_handler.right_arrow_key_down()

            elif event.key == pygame.K_UP:
                self.event_handler.up_arrow_key_down()

            elif event.key == pygame.K_DOWN:
                self.event_handler.down_arrow_key_down()

            elif event.key == pygame.K_f:
                self.event_handler.f_key_down()

    def run_gui(self):
        pygame.init()
        pygame.font.init()
        pygame.display.set_caption("Chess GUI")
        self.clock = pygame.time.Clock()
        self.running = True
        while self.running:
            for event in pygame.event.get():
                self.handle_events(event)
            self.render_board()
            pygame.display.update()
        pygame.quit()

board_gui = BoardGUI()

board_gui.run_gui()