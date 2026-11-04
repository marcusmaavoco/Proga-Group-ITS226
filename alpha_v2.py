import tkinter as tk
from tkinter import messagebox


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Tkinter App")
        self.root.geometry("400x300")

        self.label = tk.Label(root, text="Tere tulemast!", font=("Arial", 14))
        self.label.pack(pady=20)

        self.entry = tk.Entry(root, width=30)
        self.entry.pack(pady=10)

        self.button = tk.Button(root, text="Vajuta siia", command=self.on_click)
        self.button.pack(pady=10)

    def on_click(self):
        text = self.entry.get()
        messagebox.showinfo("Info", f"Sisestus: {text}" if text else "Väli on tühi!")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()