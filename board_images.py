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
SL_BORDER = (88, 60, 20)
SL_LIGHT = (250, 240, 214)
SL_DARK = (233, 205, 158)
PLAYER_COLORS = [(46, 120, 210), (224, 70, 60), (46, 168, 88), (236, 178, 24)]
PLAYER_OUTLINE = (255, 255, 255)
LADDER_C = (150, 95, 40)
LADDER_RUNG = (110, 70, 30)
SNAKE_C = (60, 150, 60)


def _cell_xy(n):
    n0 = n - 1
    row_from_bottom = n0 // 10
    col = n0 % 10
    if row_from_bottom % 2 == 1:
        col = 9 - col
    row = 9 - row_from_bottom
    return col, row


def render_snakes_ladders(positions_by_index, snakes, ladders):
    """positions_by_index: list of cell numbers (1..100 or 0), one per player, in
    player order (used to pick color/offset). Draws a polished glossy board once —
    snakes and ladders are drawn with dimension so it doesn't look like a flat
    sketch."""
    cell = 56
    size = cell * 10
    img = Image.new("RGB", (size, size), SL_BORDER)
    draw = ImageDraw.Draw(img)

    # subtle background tint within the board
    draw.rectangle([0, 0, size, size], fill=(245, 235, 200))

    # checkerboard cells
    for n in range(1, 101):
        col, row = _cell_xy(n)
        x, y = col * cell, row * cell
        fill = SL_LIGHT if ((n - 1) // 10 + (n - 1) % 10) % 2 == 0 else SL_DARK
        draw.rectangle([x, y, x + cell, y + cell], fill=fill,
                       outline=(224, 208, 176))

    # --- ladders first (drawn under the tokens), with vertical rails + rungs ---
    rail = 5
    for start, end in ladders.items():
        sc, sr = _cell_xy(start)
        ec, er = _cell_xy(end)
        x1, y1 = sc * cell + cell // 2, sr * cell + cell // 2
        x2, y2 = ec * cell + cell // 2, er * cell + cell // 2
        # rail offset perpendicular to the ladder direction
        dx, dy = (x2 - x1), (y2 - y1)
        ln = (dx * dx + dy * dy) ** 0.5 or 1
        off = (dy / ln * 5, -dx / ln * 5)
        for s in (-1, 1):
            ax, ay = x1 + off[0] * s, y1 + off[1] * s
            bx, by = x2 + off[0] * s, y2 + off[1] * s
            draw.line([(ax, ay), (bx, by)], fill=LADDER_C, width=rail)
        # rungs between the rails
        rungs = max(2, int(ln // (cell * 0.9)))
        for i in range(1, rungs):
            t = i / rungs
            rx1 = x1 + off[0] * -1 + (x2 - x1) * t
            ry1 = y1 + off[1] * -1 + (y2 - y1) * t
            rx2 = x1 + off[0] * 1 + (x2 - x1) * t
            ry2 = y1 + off[1] * 1 + (y2 - y1) * t
            draw.line([(rx1, ry1), (rx2, ry2)], fill=LADDER_RUNG, width=4)

    # --- snakes: wavy body from head cell to tail cell ---
    for start, end in snakes.items():
        sc, sr = _cell_xy(start)
        ec, er = _cell_xy(end)
        x1, y1 = sc * cell + cell // 2, sr * cell + cell // 2
        x2, y2 = ec * cell + cell // 2, er * cell + cell // 2
        # a slight S-curve so it reads as a snake, not a straight line
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        dxn, dyn = (y2 - y1), -(x2 - x1)
        nlen = (dxn * dxn + dyn * dyn) ** 0.5 or 1
        bend = cell * 0.7
        mx += dxn / nlen * bend * 0.4
        my += dyn / nlen * bend * 0.4
        pts = [(x1, y1), (mx, my), (x2, y2)]
        draw.line(pts, fill=SNAKE_C, width=8, joint="curve")
        draw.line(pts, fill=(120, 195, 90), width=3, joint="curve")
        # head dot at the top cell
        hr = 9
        draw.ellipse([x1 - hr, y1 - hr, x1 + hr, y1 + hr], fill=SNAKE_C)
        # eyes
        for s in (-1, 1):
            ex = x1 + dxn / nlen * 3 + (x2 - x1) / nlen * s * 3
            ey = y1 + dyn / nlen * 3
            draw.ellipse([ex - 2, ey - 2, ex + 2, ey + 2], fill=(30, 80, 30))

    # cell numbers (clearer, above everything except the tokens)
    font = _font(14)
    for n in range(1, 101):
        col, row = _cell_xy(n)
        x, y = col * cell, row * cell
        draw.text((x + 4, y + 3), str(n), font=font, fill=(120, 100, 70))

    # player tokens with white halo ring so they pop on the board
    offsets = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    for i, pos in enumerate(positions_by_index):
        if pos < 1:
            pos = 1
        col, row = _cell_xy(pos)
        x, y = col * cell, row * cell
        ox, oy = offsets[i % 4]
        cx = x + cell // 2 + ox * 11
        cy = y + cell // 2 + oy * 11
        rad = 12
        draw.ellipse([cx - rad - 2, cy - rad - 2, cx + rad + 2, cy + rad + 2],
                     fill=PLAYER_OUTLINE)
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                     fill=PLAYER_COLORS[i % len(PLAYER_COLORS)],
                     outline=(255, 255, 255), width=2)

    return _to_buf(img)
