"""Generates PNG board images for the graphical games using Pillow."""
import io
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def _to_buf(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "board.png"
    return buf


# ---------------------------------------------------------------- Tic-Tac-Toe
BG = (250, 248, 245)
GRID_C = (70, 70, 80)
X_C = (231, 76, 60)
O_C = (52, 120, 219)


def render_tictactoe(board):
    size, pad = 360, 10
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    cell = size // 3

    for i in (1, 2):
        draw.line([(i * cell, pad), (i * cell, size - pad)], fill=GRID_C, width=8)
        draw.line([(pad, i * cell), (size - pad, i * cell)], fill=GRID_C, width=8)

    for i, val in enumerate(board):
        if not val:
            continue
        r, c = divmod(i, 3)
        cx, cy = c * cell + cell // 2, r * cell + cell // 2
        m = cell // 3
        if val == "X":
            draw.line([(cx - m, cy - m), (cx + m, cy + m)], fill=X_C, width=16)
            draw.line([(cx - m, cy + m), (cx + m, cy - m)], fill=X_C, width=16)
        else:
            draw.ellipse([cx - m, cy - m, cx + m, cy + m], outline=O_C, width=14)

    return _to_buf(img)


# ------------------------------------------------------------------ Connect 4
ROWS, COLS = 6, 7
C4_BOARD_C = (30, 90, 200)
C4_EMPTY_C = (245, 245, 245)
C4_RED = (231, 76, 60)
C4_YELLOW = (241, 196, 15)


def render_connect4(grid):
    cell = 60
    w, h = COLS * cell, (ROWS + 1) * cell
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, cell, w, h], fill=C4_BOARD_C)

    for r in range(ROWS):
        for c in range(COLS):
            val = grid[r][c]
            color = C4_EMPTY_C if not val else (C4_RED if val == "R" else C4_YELLOW)
            cx = c * cell + cell // 2
            cy = (r + 1) * cell + cell // 2
            rad = cell // 2 - 6
            draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=color)

    font = _font(28)
    for c in range(COLS):
        cx = c * cell + cell // 2
        draw.text((cx, cell // 2), str(c + 1), font=font, fill=(40, 40, 40), anchor="mm")

    return _to_buf(img)


# ------------------------------------------------------------- Snakes & ladders
SL_LIGHT = (250, 240, 210)
SL_DARK = (235, 210, 160)
SL_LINE = (120, 100, 70)
PLAYER_COLORS = [(52, 120, 219), (231, 76, 60), (46, 170, 90), (241, 196, 15)]


def render_snakes_ladders(positions_by_index, snakes, ladders):
    """positions_by_index: list of cell numbers (1..100 or 0), one per player, in
    player order (used to pick color/offset)."""
    cell = 56
    size = cell * 10
    img = Image.new("RGB", (size, size), SL_LIGHT)
    draw = ImageDraw.Draw(img)
    font = _font(16)

    def cell_xy(n):
        n0 = n - 1
        row_from_bottom = n0 // 10
        col = n0 % 10
        if row_from_bottom % 2 == 1:
            col = 9 - col
        row = 9 - row_from_bottom
        return col * cell, row * cell

    for n in range(1, 101):
        x, y = cell_xy(n)
        light = ((n - 1) // 10 + (n - 1) % 10) % 2 == 0
        draw.rectangle([x, y, x + cell, y + cell], fill=SL_LIGHT if light else SL_DARK, outline=(200, 190, 170))
        draw.text((x + 6, y + 4), str(n), font=font, fill=(90, 75, 50))

    for start, end in ladders.items():
        x1, y1 = cell_xy(start)
        x2, y2 = cell_xy(end)
        draw.line([(x1 + cell // 2, y1 + cell // 2), (x2 + cell // 2, y2 + cell // 2)], fill=(46, 150, 90), width=6)

    for start, end in snakes.items():
        x1, y1 = cell_xy(start)
        x2, y2 = cell_xy(end)
        draw.line([(x1 + cell // 2, y1 + cell // 2), (x2 + cell // 2, y2 + cell // 2)], fill=(190, 60, 60), width=6)

    offsets = [(-12, -12), (12, -12), (-12, 12), (12, 12)]
    for i, pos in enumerate(positions_by_index):
        if pos < 1:
            pos = 1
        x, y = cell_xy(pos)
        ox, oy = offsets[i % 4]
        cx, cy = x + cell // 2 + ox // 2, y + cell // 2 + oy // 2
        rad = 11
        draw.ellipse(
            [cx - rad, cy - rad, cx + rad, cy + rad],
            fill=PLAYER_COLORS[i % len(PLAYER_COLORS)],
            outline=(255, 255, 255),
            width=2,
        )

    return _to_buf(img)
