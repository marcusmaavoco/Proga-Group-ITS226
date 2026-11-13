import atexit
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import wave
from tkinter import colorchooser, messagebox

# ---------------------------------------------------------------- settings
ROWS = 10
COLS = 10
WIN_LENGTH = 10
CELL = 56
MARGIN = 12
TOP = 56                  # strip above the board (hover preview / result)

# ---------------------------------------------------------------- theme
if sys.platform.startswith("win"):
    FONT = "Segoe UI"
elif sys.platform == "darwin":
    FONT = "Helvetica Neue"
else:
    FONT = "DejaVu Sans"

BG = "#0b1220"
PANEL = "#111a2e"
PANEL2 = "#1a2744"
PANEL2_HOVER = "#243457"
TEXT = "#e5e7eb"
MUTED = "#94a3b8"
ACCENT = "#38bdf8"
ACCENT_HOVER = "#7dd3fc"
ACCENT_TEXT = "#06121f"

BOARD_COLOR = "#1d4ed8"
BOARD_EDGE = "#172554"
BOARD_SHADOW = "#050a16"
EMPTY_COLOR = "#0a1330"   # empty hole
HOLE_EDGE = "#0c1f55"

DEFAULT_COLORS = {1: "#ef4444", 2: "#facc15"}   # Red, Yellow
DEFAULT_NAMES = {1: "Red", 2: "Yellow"}
MAX_NAME_LEN = 12

IDLE_DELAY_MS = 5000      # 5 seconds before bell appears
BELL_DURATION_MS = 2000   # 2 seconds of left-right movement
BELL_FRAME_MS = 25        # animation frame interval
BELL_SCALE = 5.8          # fills almost the entire board
FLASH_CHANCE = 0.05       # chance of a flashbang after each move
BOT_DELAY_MS = 450        # small pause before the bot moves

MODE_PVP = "pvp"
MODE_BOT = "bot"

# Sounds as (frequency Hz, duration ms); frequency 0 = silence
SOUNDS = {
    "drop": [(330, 70)],
    "win":  [(523, 120), (659, 120), (784, 120), (1047, 320)],
    "draw": [(392, 150), (330, 260)],
    "bell": [(988, 180), (1319, 380)],
    "flash": [(90, 70), (2800, 2000)],   # thump + ringing
}


# ---------------------------------------------------------------- helpers
def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def darken(hex_color, factor=0.65):
    r, g, b = _rgb(hex_color)
    return "#%02x%02x%02x" % (int(r * factor), int(g * factor), int(b * factor))


def lighten(hex_color, amount=0.45):
    r, g, b = _rgb(hex_color)
    return "#%02x%02x%02x" % (int(r + (255 - r) * amount),
                              int(g + (255 - g) * amount),
                              int(b + (255 - b) * amount))


def blend(c1, c2, t):
    """Mix two hex colors, t=0 -> c1, t=1 -> c2."""
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class FlatButton(tk.Label):
    """Flat, hover-aware button (a Label, so colors work on every OS)."""

    def __init__(self, parent, text, command, bg=PANEL2, hover=PANEL2_HOVER,
                 fg=TEXT, size=11, padx=16, pady=8):
        super().__init__(parent, text=text, bg=bg, fg=fg,
                         font=(FONT, size, "bold"), padx=padx, pady=pady,
                         cursor="hand2")
        self.normal, self.hover = bg, hover
        self.command = command
        self.bind("<Enter>", lambda e: self.config(bg=self.hover))
        self.bind("<Leave>", lambda e: self.config(bg=self.normal))
        self.bind("<Button-1>", lambda e: self.command())

    def restyle(self, bg, hover, fg):
        self.normal, self.hover = bg, hover
        self.config(bg=bg, fg=fg)


class SoundPlayer:
    """Tiny dependency-free sound player with volume control."""

    RATE = 22050

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="connect10_")
        atexit.register(shutil.rmtree, self.dir, True)
        self.cache = {}

    def _make_file(self, kind, volume):
        path = os.path.join(self.dir, f"{kind}_{int(volume * 100)}.wav")
        frames = bytearray()
        for freq, ms in SOUNDS[kind]:
            n = int(self.RATE * ms / 1000)
            fade_in = max(1, int(self.RATE * 0.005))
            for i in range(n):
                env = (1 - i / n) ** 1.3 * min(1.0, i / fade_in)
                val = math.sin(2 * math.pi * freq * i / self.RATE) if freq else 0
                frames += struct.pack("<h", int(val * env * volume * 0.7 * 32767))
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.RATE)
            wf.writeframes(bytes(frames))
        return path

    def play(self, kind, volume_percent):
        if volume_percent <= 0:
            return
        step = max(5, round(volume_percent / 5) * 5)
        key = (kind, step)
        try:
            if key not in self.cache:
                self.cache[key] = self._make_file(kind, step / 100)
            path = self.cache[key]
            if sys.platform.startswith("win"):
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", path], stderr=subprocess.DEVNULL)
            else:
                player = shutil.which("aplay") or shutil.which("paplay")
                if player:
                    args = [player, "-q", path] if player.endswith("aplay") else [player, path]
                    subprocess.Popen(args, stderr=subprocess.DEVNULL)
        except Exception:
            pass  # sound is optional; never break the game


# ---------------------------------------------------------------- game
class Connect10:
    def __init__(self, root):
        self.root = root
        root.title("Connect 10")
        root.resizable(False, False)
        root.configure(bg=BG)

        self.idle_timer = None
        self.bell_anim_id = None
        self.bot_after_id = None
        self.pulse_id = None
        self.opt_win = None
        self.p2_entry = None
        self.swatches = {}
        self.mode_buttons = {}
        self.end_time = 0.0
        self.fx_id = None
        self.confetti, self.sparkles = [], []
        self.sparkle_cells, self.sparkle_colors = [], []
        self.fx_frames = 0
        self.flashing = False
        self.flash_win = None

        self.sound = SoundPlayer()
        self.mode = tk.StringVar(value=MODE_PVP)
        self.volume = tk.IntVar(value=60)
        self.fx_enabled = tk.BooleanVar(value=True)
        self.flash_enabled = tk.BooleanVar(value=True)
        self.colors = dict(DEFAULT_COLORS)
        self.p_names = dict(DEFAULT_NAMES)
        self.scores = {1: 0, 2: 0, "draw": 0}
        self.win_cells = []
        self.result = None

        # ---- title ----
        tk.Label(root, text="CONNECT 10", font=(FONT, 22, "bold"),
                 fg=TEXT, bg=BG).pack(pady=(14, 0))
        tk.Label(root, text="get ten in a row", font=(FONT, 10),
                 fg=MUTED, bg=BG).pack(pady=(0, 8))

        # ---- scoreboard cards ----
        score_frame = tk.Frame(root, bg=BG)
        score_frame.pack(padx=14, fill="x")
        for col in range(3):
            score_frame.columnconfigure(col, weight=1, uniform="score")
        self.score_cards, self.score_names, self.score_vals = {}, {}, {}
        for col, key in enumerate((1, "draw", 2)):
            card = tk.Frame(score_frame, bg=PANEL, highlightthickness=3,
                            highlightbackground=PANEL, highlightcolor=PANEL)
            card.grid(row=0, column=col, sticky="ew", padx=4)
            name = tk.Label(card, text="", font=(FONT, 11, "bold"),
                            fg=MUTED, bg=PANEL)
            name.pack(pady=(8, 0))
            val = tk.Label(card, text="0", font=(FONT, 28, "bold"),
                           fg=TEXT, bg=PANEL)
            val.pack(pady=(0, 6))
            self.score_cards[key] = card
            self.score_names[key] = name
            self.score_vals[key] = val

        # ---- status ----
        status_frame = tk.Frame(root, bg=BG)
        status_frame.pack(pady=(12, 6))
        self.dot = tk.Canvas(status_frame, width=18, height=18, bg=BG,
                             highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 8))
        self.dot_item = self.dot.create_oval(2, 2, 16, 16, fill=MUTED, outline="")
        self.status = tk.Label(status_frame, text="", font=(FONT, 16, "bold"),
                               fg=TEXT, bg=BG)
        self.status.pack(side="left")

        # ---- board canvas ----
        self.board_w = COLS * CELL + 2 * MARGIN
        self.board_h = ROWS * CELL + 2 * MARGIN
        self.canvas = tk.Canvas(root, width=self.board_w,
                                height=TOP + self.board_h + 8, bg=BG,
                                highlightthickness=0)
        self.canvas.pack(padx=14)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_hover)
        self.canvas.bind("<Leave>", lambda e: self.canvas.delete("hover"))

        # Track mouse movement anywhere on the window to reset the 5s timer
        root.bind("<Motion>", self.on_mouse_move)

        # ---- buttons ----
        btn_frame = tk.Frame(root, bg=BG)
        btn_frame.pack(pady=14)
        FlatButton(btn_frame, "New Game", self.reset, bg=ACCENT,
                   hover=ACCENT_HOVER, fg=ACCENT_TEXT).pack(side="left", padx=5)
        FlatButton(btn_frame, "Reset Scores", self.reset_scores).pack(side="left", padx=5)
        FlatButton(btn_frame, "Options", self.open_options).pack(side="left", padx=5)

        self.reset()

    # ---------- helpers ----------
    def is_bot_mode(self):
        return self.mode.get() == MODE_BOT

    def is_bot_turn(self):
        return self.is_bot_mode() and self.current == 2

    def name(self, p):
        if p == 2 and self.is_bot_mode():
            return "Bot"
        return self.p_names[p]

    def play(self, kind):
        self.sound.play(kind, self.volume.get())

    # ---------- options window ----------
    def section(self, parent, title):
        tk.Label(parent, text=title.upper(), font=(FONT, 9, "bold"),
                 fg=MUTED, bg=BG).pack(anchor="w", padx=16, pady=(12, 4))
        frame = tk.Frame(parent, bg=PANEL, padx=12, pady=10)
        frame.pack(fill="x", padx=16)
        return frame

    def open_options(self):
        if self.opt_win is not None and self.opt_win.winfo_exists():
            self.opt_win.lift()
            return
        win = tk.Toplevel(self.root)
        self.opt_win = win
        win.title("Options")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=BG)

        # Game mode (segmented control)
        sec = self.section(win, "Game mode")
        row = tk.Frame(sec, bg=PANEL)
        row.pack(fill="x")
        self.mode_buttons = {}
        for val, label in ((MODE_PVP, "1 vs 1"), (MODE_BOT, "1 vs Bot")):
            b = FlatButton(row, label, lambda v=val: self.set_mode(v),
                           padx=18, pady=7)
            b.pack(side="left", expand=True, fill="x", padx=2)
            self.mode_buttons[val] = b
        self.refresh_mode_buttons()

        # Players: name + color
        sec = self.section(win, "Players")
        self.name_vars = {}
        for r, p in enumerate((1, 2)):
            tk.Label(sec, text=f"Player {p}", font=(FONT, 11), fg=TEXT,
                     bg=PANEL).grid(row=r, column=0, sticky="w", pady=4)
            var = tk.StringVar(value=self.p_names[p])
            var.trace_add("write", lambda *a, p=p: self.on_name_change(p))
            self.name_vars[p] = var
            entry = tk.Entry(sec, textvariable=var, width=14, font=(FONT, 11),
                             bg=PANEL2, fg=TEXT, insertbackground=TEXT,
                             disabledbackground=PANEL, disabledforeground=MUTED,
                             relief="flat", highlightthickness=1,
                             highlightbackground="#2b3a5c", highlightcolor=ACCENT)
            entry.grid(row=r, column=1, padx=10, ipady=4)
            if p == 2:
                self.p2_entry = entry
            sw = tk.Label(sec, width=4, bg=self.colors[p], bd=0,
                          highlightthickness=2, highlightbackground="#e2e8f0")
            sw.grid(row=r, column=2, padx=4)
            self.swatches[p] = sw
            FlatButton(sec, "Color", lambda p=p: self.pick_color(p), size=10,
                       padx=10, pady=4).grid(row=r, column=3, padx=(4, 0))
        FlatButton(sec, "Reset colors", self.reset_colors, size=10,
                   padx=10, pady=4).grid(row=2, column=0, columnspan=4,
                                         pady=(8, 0))

        # Volume
        sec = self.section(win, "Volume")
        scale = tk.Scale(sec, from_=0, to=100, orient="horizontal",
                         variable=self.volume, length=300, bg=PANEL, fg=TEXT,
                         troughcolor=PANEL2, highlightthickness=0, bd=0,
                         activebackground=ACCENT, sliderrelief="flat",
                         font=(FONT, 10))
        scale.pack()
        scale.bind("<ButtonRelease-1>", lambda e: self.play("drop"))

        # Effects
        sec = self.section(win, "Effects")
        for var, label in (
                (self.fx_enabled, "Confetti & sparkles on win"),
                (self.flash_enabled,
                 f"Random flashbang ({int(FLASH_CHANCE * 100)}% per move)")):
            tk.Checkbutton(sec, text=label, variable=var, font=(FONT, 11),
                           fg=TEXT, bg=PANEL, selectcolor=PANEL2,
                           activebackground=PANEL, activeforeground=TEXT,
                           highlightthickness=0, bd=0,
                           anchor="w").pack(fill="x", pady=2)
        tk.Label(sec, text="Flashbang = bright white flash + loud ringing.\n"
                           "Turn it off if you're sensitive to bright light or noise.",
                 font=(FONT, 9), fg=MUTED, bg=PANEL,
                 justify="left").pack(anchor="w", pady=(4, 0))

        FlatButton(win, "Close", win.destroy, bg=ACCENT, hover=ACCENT_HOVER,
                   fg=ACCENT_TEXT).pack(pady=14)

        self.update_p2_entry_state()

    def refresh_mode_buttons(self):
        for val, b in self.mode_buttons.items():
            if not b.winfo_exists():
                continue
            if val == self.mode.get():
                b.restyle(ACCENT, ACCENT_HOVER, ACCENT_TEXT)
            else:
                b.restyle(PANEL2, PANEL2_HOVER, TEXT)

    def set_mode(self, value):
        if self.mode.get() == value:
            return
        self.mode.set(value)
        self.refresh_mode_buttons()
        self.on_mode_change()

    def update_p2_entry_state(self):
        if self.p2_entry is not None and self.p2_entry.winfo_exists():
            self.p2_entry.config(state="disabled" if self.is_bot_mode() else "normal")

    def on_mode_change(self):
        self.scores = {1: 0, 2: 0, "draw": 0}
        self.update_p2_entry_state()
        self.reset()

    def on_name_change(self, p):
        value = self.name_vars[p].get().strip()[:MAX_NAME_LEN]
        self.p_names[p] = value or DEFAULT_NAMES[p]
        self.update_status()
        self.update_scoreboard()
        self.draw_banner()

    def pick_color(self, p):
        other = 2 if p == 1 else 1
        result = colorchooser.askcolor(color=self.colors[p], parent=self.opt_win,
                                       title=f"Color for {self.name(p)}")
        new = result[1] if result else None
        if not new:
            return
        if new.lower() == self.colors[other].lower():
            messagebox.showwarning("Same color",
                                   "Both players can't have the same color.",
                                   parent=self.opt_win)
            return
        self.colors[p] = new
        self.apply_colors()

    def reset_colors(self):
        self.colors = dict(DEFAULT_COLORS)
        self.apply_colors()

    def apply_colors(self):
        for p, sw in self.swatches.items():
            if sw.winfo_exists():
                sw.config(bg=self.colors[p])
        self.draw_board()
        self.update_status()
        self.update_scoreboard()

    # ---------- scoreboard ----------
    def reset_scores(self):
        self.scores = {1: 0, 2: 0, "draw": 0}
        self.update_scoreboard()

    def update_scoreboard(self):
        for p in (1, 2):
            self.score_names[p].config(text=self.name(p),
                                       fg=lighten(self.colors[p], 0.15))
            self.score_vals[p].config(text=str(self.scores[p]))
        self.score_names["draw"].config(text="Draws")
        self.score_vals["draw"].config(text=str(self.scores["draw"]))
        self.update_card_highlight()

    def update_card_highlight(self):
        for p in (1, 2):
            if self.result:
                active = self.result[0] == "win" and self.result[1] == p
            else:
                active = self.current == p
            color = self.colors[p] if active else PANEL
            self.score_cards[p].config(highlightbackground=color,
                                       highlightcolor=color)

    def update_status(self):
        if self.result and self.result[0] == "win":
            p = self.result[1]
            text, dot = f"{self.name(p)} wins!", self.colors[p]
        elif self.result:
            text, dot = "It's a draw!", MUTED
        else:
            p = self.current
            text, dot = f"{self.name(p)}'s turn", self.colors[p]
        self.status.config(text=text)
        self.dot.itemconfig(self.dot_item, fill=dot)
        self.update_card_highlight()

    # ---------- idle bell reminder ----------
    def on_mouse_move(self, event):
        self.reset_idle_timer()

    def reset_idle_timer(self):
        if self.idle_timer is not None:
            self.root.after_cancel(self.idle_timer)
            self.idle_timer = None
        if self.bell_anim_id is not None:
            self.root.after_cancel(self.bell_anim_id)
            self.bell_anim_id = None
        self.canvas.delete("bell")

        if not self.game_over:
            self.idle_timer = self.root.after(IDLE_DELAY_MS, self.start_bell_reminder)

    def start_bell_reminder(self):
        self.idle_timer = None
        if self.game_over or self.animating or self.is_bot_turn():
            self.reset_idle_timer()
            return
        self.play("bell")
        self.animate_bell(0)

    def draw_bell(self, cx, cy, clapper_dx):
        self.canvas.delete("bell")
        s = BELL_SCALE

        # Top handle loop
        self.canvas.create_oval(cx - 10 * s, cy - 44 * s,
                                cx + 10 * s, cy - 26 * s,
                                outline="#451a03", width=max(2, int(4 * s)),
                                tags="bell")
        # Swinging clapper
        self.canvas.create_oval(cx - 11 * s + clapper_dx, cy + 20 * s,
                                cx + 11 * s + clapper_dx, cy + 40 * s,
                                fill="#d97706", outline="#451a03",
                                width=max(2, int(3 * s)), tags="bell")
        # Bell body
        raw_points = [
            (-18, -24), (-12, -33), (0, -36), (12, -33), (18, -24),
            (22, -4), (34, 16), (38, 22), (38, 27),
            (-38, 27), (-38, 22), (-34, 16), (-22, -4),
        ]
        body_points = [
            coord
            for dx, dy in raw_points
            for coord in (cx + dx * s, cy + dy * s)
        ]
        self.canvas.create_polygon(body_points, fill="#fbbf24",
                                   outline="#451a03",
                                   width=max(2, int(3 * s)), tags="bell")
        # Rim detail and highlight
        self.canvas.create_line(cx - 33 * s, cy + 16 * s,
                                cx + 33 * s, cy + 16 * s,
                                fill="#451a03", width=max(2, int(2 * s)),
                                tags="bell")
        self.canvas.create_line(cx - 14 * s, cy - 22 * s,
                                cx - 24 * s, cy + 10 * s,
                                fill="#fef08a", width=max(2, int(3 * s)),
                                capstyle=tk.ROUND, tags="bell")

    def animate_bell(self, step):
        total_steps = BELL_DURATION_MS // BELL_FRAME_MS
        if step >= total_steps or self.game_over:
            self.canvas.delete("bell")
            self.bell_anim_id = None
            self.reset_idle_timer()
            return

        center_x = self.board_w / 2
        center_y = TOP + self.board_h / 2

        # Keep the full width of the giant bell inside the canvas while swinging
        max_swing = max(15, (self.board_w / 2) - (38 * BELL_SCALE) - 8)
        offset_x = math.sin(step * 0.45) * max_swing
        clapper_dx = math.sin(step * 0.45 - 0.5) * (8 * BELL_SCALE)

        self.draw_bell(center_x + offset_x, center_y, clapper_dx)
        self.bell_anim_id = self.root.after(
            BELL_FRAME_MS, lambda: self.animate_bell(step + 1)
        )

    # ---------- game state ----------
    def reset(self):
        if self.bot_after_id is not None:
            self.root.after_cancel(self.bot_after_id)
            self.bot_after_id = None
        if self.pulse_id is not None:
            self.root.after_cancel(self.pulse_id)
            self.pulse_id = None
        self.board = [[0] * COLS for _ in range(ROWS)]
        self.current = 1
        self.game_over = False
        self.animating = False
        self.win_cells = []
        self.result = None
        self.draw_board()
        self.update_status()
        self.update_scoreboard()
        self.reset_idle_timer()

    # ---------- drawing ----------
    def cell_xy(self, r, c):
        x1 = MARGIN + c * CELL + 4
        y1 = TOP + MARGIN + r * CELL + 4
        return x1, y1, x1 + CELL - 8, y1 + CELL - 8

    def set_cell(self, r, c, player):
        """Paint one cell as empty (0) or as a player's glossy piece."""
        if player:
            color = self.colors[player]
            self.canvas.itemconfig(f"cell_{r}_{c}", fill=color,
                                   outline=darken(color, 0.75))
            self.canvas.itemconfig(f"shine_{r}_{c}", fill=lighten(color, 0.55),
                                   state="normal")
        else:
            self.canvas.itemconfig(f"cell_{r}_{c}", fill=EMPTY_COLOR,
                                   outline="#081027")
            self.canvas.itemconfig(f"shine_{r}_{c}", state="hidden")

    def draw_board(self):
        self.clear_fx()
        self.canvas.delete("all")
        w, h = self.board_w, self.board_h
        # shadow + board body
        round_rect(self.canvas, 3, TOP + 6, w - 3, TOP + h + 6, 26,
                   fill=BOARD_SHADOW, outline="")
        round_rect(self.canvas, 3, TOP, w - 3, TOP + h, 26,
                   fill=BOARD_COLOR, outline=BOARD_EDGE, width=3)
        for r in range(ROWS):
            for c in range(COLS):
                x1, y1, x2, y2 = self.cell_xy(r, c)
                # hole (dark ring) -> piece -> gloss
                self.canvas.create_oval(x1, y1, x2, y2, fill=HOLE_EDGE,
                                        outline=BOARD_EDGE, width=2)
                self.canvas.create_oval(x1 + 3, y1 + 3, x2 - 3, y2 - 3,
                                        fill=EMPTY_COLOR, outline="#081027",
                                        width=2, tags=f"cell_{r}_{c}")
                self.canvas.create_oval(x1 + 11, y1 + 9, x1 + 25, y1 + 18,
                                        fill="#ffffff", outline="",
                                        state="hidden", tags=f"shine_{r}_{c}")
                self.set_cell(r, c, self.board[r][c])
        for (wr, wc) in self.win_cells:
            self.canvas.itemconfig(f"cell_{wr}_{wc}", outline="white", width=5)
        self.draw_banner()

    def draw_banner(self):
        """Result pill in the strip above the board."""
        self.canvas.delete("banner")
        if not self.result:
            return
        if self.result[0] == "win":
            p = self.result[1]
            col, text = self.colors[p], f"{self.name(p)} wins!"
        else:
            col, text = MUTED, "It's a draw!"
        cx = self.board_w / 2
        round_rect(self.canvas, cx - 200, 8, cx + 200, TOP - 8, 20,
                   fill=PANEL, outline=col, width=3, tags="banner")
        self.canvas.create_text(cx, TOP / 2,
                                text=f"{text}   \u00b7   click for a new game",
                                font=(FONT, 14, "bold"),
                                fill=lighten(col, 0.3), tags="banner")

    def pulse_win(self, n=0):
        if not self.win_cells:
            return
        if n >= 12:
            color = "white"
        else:
            color = "white" if n % 2 == 0 else "#fde047"
        for (wr, wc) in self.win_cells:
            self.canvas.itemconfig(f"cell_{wr}_{wc}", outline=color, width=5)
        if n < 12:
            self.pulse_id = self.root.after(220, lambda: self.pulse_win(n + 1))
        else:
            self.pulse_id = None

    def on_hover(self, event):
        self.canvas.delete("hover")
        if self.game_over or self.animating or self.is_bot_turn():
            return
        c = (event.x - MARGIN) // CELL
        if 0 <= c < COLS:
            color = self.colors[self.current]
            x1 = MARGIN + c * CELL
            # column outline
            round_rect(self.canvas, x1 + 2, TOP + 2, x1 + CELL - 2,
                       TOP + self.board_h - 2, 18, fill="", outline=color,
                       width=3, tags="hover")
            # ghost piece above the board
            cx, cy = x1 + CELL / 2, TOP / 2
            self.canvas.create_oval(cx - 17, cy - 17, cx + 17, cy + 17,
                                    fill=color, outline=darken(color, 0.75),
                                    width=2, tags="hover")
            self.canvas.create_oval(cx - 9, cy - 11, cx + 1, cy - 4,
                                    fill=lighten(color, 0.55), outline="",
                                    tags="hover")

    # ---------- moves ----------
    def drop_row(self, c):
        """Lowest empty row in column c, or None if the column is full."""
        for r in range(ROWS - 1, -1, -1):
            if self.board[r][c] == 0:
                return r
        return None

    def on_click(self, event):
        self.reset_idle_timer()
        if self.game_over:
            # short guard so a fast last click doesn't instantly restart
            if time.monotonic() - self.end_time > 0.8:
                self.reset()
            return
        if self.animating or self.is_bot_turn():
            return
        c = (event.x - MARGIN) // CELL
        if not (0 <= c < COLS):
            return
        target = self.drop_row(c)
        if target is None:
            return  # column full
        self.canvas.delete("hover")
        self.animate_drop(c, target, 0)

    def animate_drop(self, c, target, r):
        """Piece falls from the top down to the target row."""
        self.animating = True
        if r > 0:
            self.set_cell(r - 1, c, 0)
        self.set_cell(r, c, self.current)
        if r < target:
            self.root.after(25, lambda: self.animate_drop(c, target, r + 1))
        else:
            self.board[target][c] = self.current
            self.animating = False
            self.play("drop")
            self.after_move(target, c)

    def after_move(self, r, c):
        win_cells = self.check_win(r, c)
        if win_cells:
            self.game_over = True
            self.end_time = time.monotonic()
            self.reset_idle_timer()
            self.win_cells = win_cells
            self.result = ("win", self.current)
            self.scores[self.current] += 1
            self.update_scoreboard()
            self.update_status()
            self.draw_banner()
            self.play("win")
            self.pulse_win()
            self.start_celebration(win_cells, self.colors[self.current])
            return
        if all(self.board[0][col] != 0 for col in range(COLS)):
            self.game_over = True
            self.end_time = time.monotonic()
            self.reset_idle_timer()
            self.result = ("draw",)
            self.scores["draw"] += 1
            self.update_scoreboard()
            self.update_status()
            self.draw_banner()
            self.play("draw")
            return
        self.current = 2 if self.current == 1 else 1
        self.update_status()
        self.reset_idle_timer()

        if self.is_bot_turn():
            self.bot_after_id = self.root.after(BOT_DELAY_MS, self.bot_move)

        if self.flash_enabled.get() and random.random() < FLASH_CHANCE:
            self.flashbang()

    # ---------- effects: confetti, sparkles, flashbang ----------
    def clear_fx(self):
        if self.fx_id is not None:
            self.root.after_cancel(self.fx_id)
            self.fx_id = None
        self.confetti, self.sparkles = [], []
        self.canvas.delete("fx")

    def _new_confetti(self, x, y, vx, vy, palette):
        item = self.canvas.create_polygon(0, 0, 0, 0, 0, 0, 0, 0,
                                          fill=random.choice(palette),
                                          outline="", tags="fx")
        self.confetti.append({
            "id": item, "x": x, "y": y, "vx": vx, "vy": vy,
            "size": random.uniform(5, 10),
            "rot": random.uniform(0, math.tau),
            "vrot": random.uniform(-0.25, 0.25),
            "phase": random.uniform(0, math.tau),
            "spin": random.uniform(0.1, 0.3),
        })

    def start_celebration(self, win_cells, color):
        if not self.fx_enabled.get():
            return
        self.clear_fx()
        palette = [color, lighten(color, 0.4), "#fde047", "#ffffff",
                   "#38bdf8", "#f472b6", "#4ade80", "#fb923c"]
        w = self.board_w
        h = TOP + self.board_h
        for _ in range(110):                      # rain from the top
            self._new_confetti(random.uniform(0, w), random.uniform(-300, -10),
                               random.uniform(-1, 1), random.uniform(0.5, 2.5),
                               palette)
        for side in (0, 1):                       # cannons in the bottom corners
            for _ in range(35):
                x = 6 if side == 0 else w - 6
                vx = random.uniform(1.5, 6) * (1 if side == 0 else -1)
                self._new_confetti(x, h, vx, random.uniform(-15, -8), palette)
        self.sparkle_cells = list(win_cells)
        self.sparkle_colors = ["#ffffff", "#fde047", lighten(color, 0.6)]
        self.fx_frames = 0
        self.fx_tick()

    def fx_tick(self):
        self.fx_id = None
        self.fx_frames += 1
        bottom = TOP + self.board_h + 30

        # confetti
        alive = []
        for p in self.confetti:
            p["vy"] = min(p["vy"] + 0.18, 3.2)
            p["vx"] *= 0.985
            p["phase"] += p["spin"]
            p["rot"] += p["vrot"]
            p["x"] += p["vx"] + math.sin(p["phase"] * 0.5) * 0.7
            p["y"] += p["vy"]
            if p["y"] > bottom:
                self.canvas.delete(p["id"])
                continue
            hw = p["size"]
            hh = p["size"] * 0.5 * abs(math.cos(p["phase"])) + 0.8   # flutter
            ca, sa = math.cos(p["rot"]), math.sin(p["rot"])
            pts = []
            for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                pts += [p["x"] + dx * ca - dy * sa, p["y"] + dx * sa + dy * ca]
            self.canvas.coords(p["id"], *pts)
            alive.append(p)
        self.confetti = alive

        # sparkles around the winning line
        if self.fx_frames < 100 and self.sparkle_cells:
            for _ in range(2):
                r, c = random.choice(self.sparkle_cells)
                x1, y1, x2, y2 = self.cell_xy(r, c)
                item = self.canvas.create_polygon(
                    *([0] * 16), fill=random.choice(self.sparkle_colors),
                    outline="", tags="fx")
                self.sparkles.append({
                    "id": item,
                    "x": (x1 + x2) / 2 + random.uniform(-26, 26),
                    "y": (y1 + y2) / 2 + random.uniform(-26, 26),
                    "size": random.uniform(7, 15), "age": 0,
                    "life": random.randint(16, 26),
                })
        alive_s = []
        for sp in self.sparkles:
            sp["age"] += 1
            t = sp["age"] / sp["life"]
            if t >= 1:
                self.canvas.delete(sp["id"])
                continue
            k = sp["size"] * math.sin(math.pi * t)
            q = k * 0.22
            x, y = sp["x"], sp["y"]
            self.canvas.coords(sp["id"], x, y - k, x + q, y - q, x + k, y,
                               x + q, y + q, x, y + k, x - q, y + q,
                               x - k, y, x - q, y - q)
            alive_s.append(sp)
        self.sparkles = alive_s

        if self.confetti or self.sparkles or self.fx_frames < 100:
            self.fx_id = self.root.after(30, self.fx_tick)
        else:
            self.canvas.delete("fx")

    def flashbang(self):
        if self.flashing:
            return
        self.flashing = True
        self.play("flash")
        self.root.update_idletasks()
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg="#ffffff")
        win.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}"
                     f"+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}")
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.flash_win = win
        self.flash_step(0)

    def flash_step(self, n):
        hold, fade = 12, 55          # 40 ms per step: ~0.5 s white, ~2.2 s fade
        if n >= hold + fade:
            if self.flash_win is not None:
                self.flash_win.destroy()
            self.flash_win = None
            self.flashing = False
            return
        t = 0.0 if n < hold else (n - hold) / fade
        try:
            self.flash_win.attributes("-alpha", 1.0 - t)
        except tk.TclError:
            pass  # no transparency support: stays white until the end
        self.root.after(40, lambda: self.flash_step(n + 1))

    def check_win(self, r, c):
        player = self.board[r][c]
        for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            cells = [(r, c)]
            for sign in (1, -1):
                nr, nc = r + dr * sign, c + dc * sign
                while 0 <= nr < ROWS and 0 <= nc < COLS and self.board[nr][nc] == player:
                    cells.append((nr, nc))
                    nr += dr * sign
                    nc += dc * sign
            if len(cells) >= WIN_LENGTH:
                return cells
        return None

    # ---------- bot ----------
    def line_length(self, r, c, player):
        """Longest line through (r, c) if `player` had a piece there."""
        best = 1
        for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            count = 1
            for sign in (1, -1):
                nr, nc = r + dr * sign, c + dc * sign
                while 0 <= nr < ROWS and 0 <= nc < COLS and self.board[nr][nc] == player:
                    count += 1
                    nr += dr * sign
                    nc += dc * sign
            best = max(best, count)
        return best

    def choose_bot_column(self):
        bot, human = 2, 1
        options = [(c, self.drop_row(c)) for c in range(COLS)
                   if self.drop_row(c) is not None]

        # 1) win immediately
        for c, r in options:
            if self.line_length(r, c, bot) >= WIN_LENGTH:
                return c
        # 2) block the human's immediate win
        for c, r in options:
            if self.line_length(r, c, human) >= WIN_LENGTH:
                return c

        # 3) score the rest
        best_score, best_cols = None, []
        for c, r in options:
            score = self.line_length(r, c, bot) * 2 + self.line_length(r, c, human)
            score -= abs(c - (COLS - 1) / 2) * 0.3   # slight centre preference
            # don't hand the human a winning spot right above
            if r - 1 >= 0 and self.line_length(r - 1, c, human) >= WIN_LENGTH:
                score -= 100
            if best_score is None or score > best_score + 1e-9:
                best_score, best_cols = score, [c]
            elif abs(score - best_score) <= 1e-9:
                best_cols.append(c)
        return random.choice(best_cols)

    def bot_move(self):
        self.bot_after_id = None
        if self.game_over or self.animating or not self.is_bot_turn():
            return
        c = self.choose_bot_column()
        target = self.drop_row(c)
        if target is None:
            return
        self.animate_drop(c, target, 0)


if __name__ == "__main__":
    root = tk.Tk()
    Connect10(root)
    root.mainloop()
