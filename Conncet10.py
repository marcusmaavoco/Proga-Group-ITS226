import math
import tkinter as tk
from tkinter import messagebox

ROWS = 10
COLS = 10
WIN_LENGTH = 10
CELL = 56
MARGIN = 12

BOARD_COLOR = "#1d4ed8"
EMPTY_COLOR = "#e5e7eb"
PLAYER_COLORS = {1: "#ef4444", 2: "#facc15"}   # Red, Yellow
PLAYER_NAMES = {1: "Red", 2: "Yellow"}

IDLE_DELAY_MS = 5000      # 5 seconds before bell appears
BELL_DURATION_MS = 2000   # 2 seconds of left-right movement
BELL_FRAME_MS = 25        # animation frame interval


class Connect10:
    def __init__(self, root):
        self.root = root
        root.title("Connect 10")
        root.resizable(False, False)

        self.idle_timer = None
        self.bell_anim_id = None

        self.status = tk.Label(root, text="", font=("Arial", 16, "bold"), pady=8)
        self.status.pack()

        w = COLS * CELL + 2 * MARGIN
        h = ROWS * CELL + 2 * MARGIN
        self.canvas = tk.Canvas(root, width=w, height=h, bg=BOARD_COLOR,
                                highlightthickness=0)
        self.canvas.pack(padx=10)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_hover)
        self.canvas.bind("<Leave>", lambda e: self.canvas.delete("hover"))

        # Track mouse movement anywhere on the window to reset the 5s timer
        root.bind("<Motion>", self.on_mouse_move)

        tk.Button(root, text="New Game", font=("Arial", 12),
                  command=self.reset).pack(pady=8)

        self.reset()

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
        if self.game_over or self.animating:
            self.reset_idle_timer()
            return
        self.animate_bell(0)

    def draw_bell(self, cx, cy, clapper_dx):
        self.canvas.delete("bell")
        # Top handle loop
        self.canvas.create_oval(cx - 10, cy - 44, cx + 10, cy - 26,
                                outline="#451a03", width=4, tags="bell")
        # Swinging clapper
        self.canvas.create_oval(cx - 11 + clapper_dx, cy + 20,
                                cx + 11 + clapper_dx, cy + 40,
                                fill="#d97706", outline="#451a03", width=3,
                                tags="bell")
        # Bell body
        body_points = [
            cx - 18, cy - 24,
            cx - 12, cy - 33,
            cx,      cy - 36,
            cx + 12, cy - 33,
            cx + 18, cy - 24,
            cx + 22, cy - 4,
            cx + 34, cy + 16,
            cx + 38, cy + 22,
            cx + 38, cy + 27,
            cx - 38, cy + 27,
            cx - 38, cy + 22,
            cx - 34, cy + 16,
            cx - 22, cy - 4,
        ]
        self.canvas.create_polygon(body_points, fill="#fbbf24",
                                   outline="#451a03", width=3, tags="bell")
        # Rim detail and highlight
        self.canvas.create_line(cx - 33, cy + 16, cx + 33, cy + 16,
                                fill="#451a03", width=2, tags="bell")
        self.canvas.create_line(cx - 14, cy - 22, cx - 24, cy + 10,
                                fill="#fef08a", width=3, capstyle=tk.ROUND,
                                tags="bell")

    def animate_bell(self, step):
        total_steps = BELL_DURATION_MS // BELL_FRAME_MS
        if step >= total_steps or self.game_over:
            self.canvas.delete("bell")
            self.bell_anim_id = None
            self.reset_idle_timer()
            return

        center_x = (COLS * CELL + 2 * MARGIN) / 2
        center_y = (ROWS * CELL + 2 * MARGIN) / 2

        # Smooth left-and-right oscillation
        offset_x = math.sin(step * 0.45) * 30
        clapper_dx = math.sin(step * 0.45 - 0.5) * 8

        self.draw_bell(center_x + offset_x, center_y, clapper_dx)
        self.bell_anim_id = self.root.after(
            BELL_FRAME_MS, lambda: self.animate_bell(step + 1)
        )

    # ---------- game state ----------
    def reset(self):
        self.board = [[0] * COLS for _ in range(ROWS)]
        self.current = 1
        self.game_over = False
        self.animating = False
        self.draw_board()
        self.update_status()
        self.reset_idle_timer()

    def update_status(self):
        self.status.config(
            text=f"{PLAYER_NAMES[self.current]}'s turn",
            fg=PLAYER_COLORS[self.current] if self.current == 1 else "#a16207")

    # ---------- drawing ----------
    def cell_xy(self, r, c):
        x1 = MARGIN + c * CELL + 4
        y1 = MARGIN + r * CELL + 4
        return x1, y1, x1 + CELL - 8, y1 + CELL - 8

    def draw_board(self):
        self.canvas.delete("all")
        for r in range(ROWS):
            for c in range(COLS):
                color = PLAYER_COLORS.get(self.board[r][c], EMPTY_COLOR)
                self.canvas.create_oval(*self.cell_xy(r, c), fill=color,
                                        outline="#1e3a8a", width=2,
                                        tags=f"cell_{r}_{c}")

    def on_hover(self, event):
        self.canvas.delete("hover")
        if self.game_over or self.animating:
            return
        c = (event.x - MARGIN) // CELL
        if 0 <= c < COLS:
            x1 = MARGIN + c * CELL
            self.canvas.create_rectangle(x1, 0, x1 + CELL, ROWS * CELL + 2 * MARGIN,
                                         outline=PLAYER_COLORS[self.current],
                                         width=3, tags="hover")

    # ---------- moves ----------
    def on_click(self, event):
        self.reset_idle_timer()
        if self.game_over or self.animating:
            return
        c = (event.x - MARGIN) // CELL
        if not (0 <= c < COLS):
            return
        # find lowest empty row in this column
        target = None
        for r in range(ROWS - 1, -1, -1):
            if self.board[r][c] == 0:
                target = r
                break
        if target is None:
            return  # column full
        self.canvas.delete("hover")
        self.animate_drop(c, target, 0)

    def animate_drop(self, c, target, r):
        """Piece falls from the top down to the target row."""
        self.animating = True
        # clear previous frame's position
        if r > 0:
            self.canvas.itemconfig(f"cell_{r-1}_{c}", fill=EMPTY_COLOR)
        self.canvas.itemconfig(f"cell_{r}_{c}", fill=PLAYER_COLORS[self.current])
        if r < target:
            self.root.after(25, lambda: self.animate_drop(c, target, r + 1))
        else:
            self.board[target][c] = self.current
            self.animating = False
            self.after_move(target, c)

    def after_move(self, r, c):
        win_cells = self.check_win(r, c)
        if win_cells:
            self.game_over = True
            self.reset_idle_timer()
            for (wr, wc) in win_cells:
                self.canvas.itemconfig(f"cell_{wr}_{wc}", outline="white", width=4)
            self.status.config(text=f"{PLAYER_NAMES[self.current]} wins!",
                               fg="#16a34a")
            messagebox.showinfo("Game Over",
                                f"{PLAYER_NAMES[self.current]} connected 10!")
            return
        if all(self.board[0][col] != 0 for col in range(COLS)):
            self.game_over = True
            self.reset_idle_timer()
            self.status.config(text="It's a draw!", fg="black")
            messagebox.showinfo("Game Over", "It's a draw!")
            return
        self.current = 2 if self.current == 1 else 1
        self.update_status()
        self.reset_idle_timer()

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


if __name__ == "__main__":
    root = tk.Tk()
    Connect10(root)
    root.mainloop()
