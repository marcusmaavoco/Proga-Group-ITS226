import random
import tkinter as tk

# Game state & settings
board = [""] * 9
human, ai = "X", "O"
scores = {"X": 0, "O": 0, "Ties": 0}
mode = "AI"
ai_difficulty = "Unbeatable"
game_over = False

root = tk.Tk()
root.title("Tic-Tac-Toe Ultimate")
root.resizable(False, False)
root.lift()
root.attributes("-topmost", True)
root.after_idle(root.attributes, "-topmost", False)

score_lbl = tk.Label(root, text="X: 0 | O: 0 | Ties: 0", font=("Arial", 11, "bold"))
score_lbl.pack(pady=4)

status_lbl = tk.Label(root, text="Player X's Turn", font=("Arial", 13, "bold"), fg="#2196F3")
status_lbl.pack(pady=2)

frame = tk.Frame(root, bg="#333")
frame.pack(padx=10, pady=5)

buttons = []
current_player = "X"

WIN_PATTERNS = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]

def check_win(b):
    for a, p, c in WIN_PATTERNS:
        if b[a] and b[a] == b[p] == b[c]:
            return b[a], (a, p, c)
    if "" not in b:
        return "Tie", None
    return None, None

def minimax(b, depth, is_max):
    winner, _ = check_win(b)
    if winner == ai:
        return 10 - depth
    if winner == human:
        return depth - 10
    if winner == "Tie":
        return 0

    if is_max:
        best = -1000
        for i in range(9):
            if b[i] == "":
                b[i] = ai
                best = max(best, minimax(b, depth + 1, False))
                b[i] = ""
        return best
    else:
        best = 1000
        for i in range(9):
            if b[i] == "":
                b[i] = human
                best = min(best, minimax(b, depth + 1, True))
                b[i] = ""
        return best

def get_ai_move():
    avail = [i for i, v in enumerate(board) if v == ""]
    if ai_difficulty == "Easy":
        return random.choice(avail)
    if ai_difficulty == "Medium" and random.random() < 0.5:
        return random.choice(avail)

    best_val, best_move = -1000, avail[0]
    for i in avail:
        board[i] = ai
        val = minimax(board, 0, False)
        board[i] = ""
        if val > best_val:
            best_val, best_move = val, i
    return best_move

def handle_end(winner, combo):
    global game_over
    game_over = True
    if winner == "Tie":
        scores["Ties"] += 1
        status_lbl.config(text="It's a Tie!", fg="#FF9800")
    else:
        scores[winner] += 1
        for i in combo:
            buttons[i].config(bg="#4CAF50", fg="white")
        col = "#2196F3" if winner == "X" else "#F44336"
        status_lbl.config(text=f"Player {winner} Wins!", fg=col)

    score_lbl.config(text=f"X: {scores['X']} | O: {scores['O']} | Ties: {scores['Ties']}")

def make_move(idx):
    global current_player
    board[idx] = current_player
    col = "#2196F3" if current_player == "X" else "#F44336"
    buttons[idx].config(text=current_player, fg=col)

    winner, combo = check_win(board)
    if winner:
        handle_end(winner, combo)
        return True

    current_player = "O" if current_player == "X" else "X"
    col = "#2196F3" if current_player == "X" else "#F44336"
    status_lbl.config(text=f"Player {current_player}'s Turn", fg=col)
    return False

def on_click(idx):
    if board[idx] or game_over:
        return
    ended = make_move(idx)
    if not ended and mode == "AI" and current_player == ai:
        root.after(250, ai_turn)

def ai_turn():
    if not game_over:
        move = get_ai_move()
        make_move(move)

def reset_game():
    global current_player, game_over, board
    board = [""] * 9
    current_player = "X"
    game_over = False
    status_lbl.config(text="Player X's Turn", fg="#2196F3")
    for btn in buttons:
        btn.config(text="", bg="white")

def toggle_mode():
    global mode
    mode = "2P" if mode == "AI" else "AI"
    mode_btn.config(text=f"Mode: {mode}")
    diff_btn.config(state="normal" if mode == "AI" else "disabled")
    reset_game()

def toggle_diff():
    global ai_difficulty
    diffs = ["Easy", "Medium", "Unbeatable"]
    ai_difficulty = diffs[(diffs.index(ai_difficulty) + 1) % 3]
    diff_btn.config(text=f"AI: {ai_difficulty}")
    reset_game()

for i in range(9):
    r, c = divmod(i, 3)
    btn = tk.Button(
        frame, text="", font=("Arial", 22, "bold"), width=5, height=2,
        bg="white", command=lambda idx=i: on_click(idx)
    )
    btn.grid(row=r, column=c, padx=3, pady=3)
    buttons.append(btn)

ctrl = tk.Frame(root)
ctrl.pack(pady=5)

tk.Button(ctrl, text="Next Round", font=("Arial", 10, "bold"), bg="#E0E0E0", command=reset_game).grid(row=0, column=0, padx=2)
mode_btn = tk.Button(ctrl, text="Mode: AI", font=("Arial", 10), command=toggle_mode)
mode_btn.grid(row=0, column=1, padx=2)
diff_btn = tk.Button(ctrl, text="AI: Unbeatable", font=("Arial", 10), command=toggle_diff)
diff_btn.grid(row=0, column=2, padx=2)

root.mainloop()