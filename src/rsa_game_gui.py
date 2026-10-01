import time
import math
import random
import csv
import os
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as tb
from ttkbootstrap.constants import *

import rsa_game as core  # IMPORTANT


THEMES_DARK = ["darkly", "superhero", "cyborg", "vapor"]
THEMES_LIGHT = ["flatly", "minty", "litera", "cosmo"]


class RSAQuestGUI(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")

        self.title("RSA QUEST: Escape the Cipher Vault! (NO SOUND)")
        self.geometry("1100x720")
        self.minsize(980, 650)

        # ---- State ----
        self.run_started_at = None
        self.deadline = None
        self.timer_job = None

        self.player_name = tb.StringVar(value="Player")
        self.explain_mode = tb.BooleanVar(value=True)
        self.diff_choice = tb.StringVar(value="1")

        # Theme state
        self.mode_var = tb.StringVar(value="dark")  # "dark" / "light"
        self.theme_var = tb.StringVar(value="darkly")

        self.diff = core.DIFFS["1"]
        self.p = self.q = self.n = self.phi = self.e = self.d = None
        self.original_msg = None
        self.cipher = None
        self.mistakes = 0

        # Will be set when UI builds
        self.diff_box = None

        self._build_ui()
        self._apply_text_theme()
        self._refresh_leaderboard()

        # Splash after UI draws
        self.after(60, self.show_splash)

    # =========================
    # Splash / Confetti / Export
    # =========================
    def show_splash(self):
        splash = tb.Toplevel(self)
        splash.overrideredirect(True)
        splash.geometry("520x240")

        x = (self.winfo_screenwidth() // 2) - 260
        y = (self.winfo_screenheight() // 2) - 120
        splash.geometry(f"+{x}+{y}")

        card = tb.Frame(splash, padding=18, bootstyle="secondary")
        card.pack(fill="both", expand=True)

        tb.Label(card, text="RSA QUEST", font=("Segoe UI", 22, "bold")).pack(pady=(8, 2))
        tb.Label(card, text="Loading Cipher Vault...", font=("Segoe UI", 11)).pack(pady=(0, 12))

        bar = tb.Progressbar(card, maximum=100, mode="determinate", bootstyle="info-striped")
        bar.pack(fill="x", padx=14)

        def step(v=0):
            bar["value"] = v
            if v >= 100:
                splash.destroy()
                return
            splash.after(18, lambda: step(v + 2))

        step()

    def confetti_popup(self, duration_ms=1800):
        pop = tb.Toplevel(self)
        pop.title("🎉 Victory!")
        pop.geometry("520x320")
        pop.transient(self)
        pop.grab_set()

        x = (self.winfo_screenwidth() // 2) - 260
        y = (self.winfo_screenheight() // 2) - 160
        pop.geometry(f"+{x}+{y}")

        frame = tb.Frame(pop, padding=10, bootstyle="secondary")
        frame.pack(fill="both", expand=True)

        tb.Label(frame, text="YOU ESCAPED THE CIPHER VAULT!", font=("Segoe UI", 14, "bold")).pack(pady=(6, 8))

        canvas = tk.Canvas(frame, width=480, height=220, bd=0, highlightthickness=0)
        canvas.pack()

        particles = []
        for _ in range(140):
            x0 = random.randint(0, 480)
            y0 = random.randint(-220, 0)
            size = random.randint(3, 9)
            dx = random.randint(-2, 2)
            dy = random.randint(2, 7)
            color = random.choice(["#ff4d4d", "#4dff88", "#4da6ff", "#ffd24d", "#c44dff", "#ffffff"])
            p = canvas.create_oval(x0, y0, x0 + size, y0 + size, fill=color, outline="")
            particles.append((p, dx, dy))

        start = time.perf_counter()

        def animate():
            elapsed = (time.perf_counter() - start) * 1000
            if elapsed >= duration_ms:
                pop.destroy()
                return

            for p, dx, dy in particles:
                canvas.move(p, dx, dy)
                x1, y1, x2, y2 = canvas.coords(p)
                if y1 > 230:
                    nx = random.randint(0, 480)
                    ny = random.randint(-90, 0)
                    canvas.coords(p, nx, ny, nx + (x2 - x1), ny + (y2 - y1))

            pop.after(16, animate)

        animate()

    def export_leaderboard_csv(self, filename=None):
        if filename is None:
            filename = os.path.join(core.DATA_DIR, "leaderboard_export.csv")

        board = core.load_board()
        if not board:
            messagebox.showinfo("Export", "Leaderboard empty.")
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(
                f,
                fieldnames=["name", "difficulty", "time_sec", "timestamp"]
                )
                w.writeheader()
                for row in board:
                    w.writerow(row)

            messagebox.showinfo("Export", f"✅ Exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    # =========================
    # UI
    # =========================
    def _build_ui(self):
        root = tb.Frame(self, padding=12)
        root.pack(fill=BOTH, expand=YES)

        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)
        root.rowconfigure(0, weight=1)

        left = tb.Frame(root)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        right = tb.Frame(root)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        # Header
        header = tb.Frame(left, padding=14, bootstyle="secondary")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        tb.Label(
            header,
            text="🔐 RSA QUEST: Escape the Cipher Vault!",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self.timer_label = tb.Label(header, text="⏳ Stage Timer: -", font=("Segoe UI", 11, "bold"))
        self.timer_label.grid(row=0, column=1, sticky="e")

        self.timer_bar = tb.Progressbar(header, maximum=1, mode="determinate", bootstyle="info-striped")
        self.timer_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # Notebook
        self.nb = tb.Notebook(left, bootstyle="secondary")
        self.nb.grid(row=1, column=0, sticky="nsew")

        self.tab_setup = tb.Frame(self.nb, padding=14)
        self.tab_s1 = tb.Frame(self.nb, padding=14)
        self.tab_s2 = tb.Frame(self.nb, padding=14)
        self.tab_s3 = tb.Frame(self.nb, padding=14)
        self.tab_s4 = tb.Frame(self.nb, padding=14)

        self.nb.add(self.tab_setup, text="0) Setup")
        self.nb.add(self.tab_s1, text="1) Prime Select")
        self.nb.add(self.tab_s2, text="2) Key Gen")
        self.nb.add(self.tab_s3, text="3) Encrypt")
        self.nb.add(self.tab_s4, text="4) Decrypt")

        self._build_setup_tab()
        self._build_stage1_tab()
        self._build_stage2_tab()
        self._build_stage3_tab()
        self._build_stage4_tab()

        # Sidebar: Theme switch
        theme_card = tb.Labelframe(right, text="🎨 Theme", padding=10, bootstyle="secondary")
        theme_card.grid(row=0, column=0, sticky="ew")
        theme_card.columnconfigure(1, weight=1)

        tb.Label(theme_card, text="Mode:").grid(row=0, column=0, sticky="w")
        mode_row = tb.Frame(theme_card)
        mode_row.grid(row=0, column=1, sticky="w")

        tb.Radiobutton(
            mode_row, text="Dark", value="dark", variable=self.mode_var, bootstyle="secondary",
            command=self._on_mode_change
        ).pack(side=LEFT, padx=(0, 8))
        tb.Radiobutton(
            mode_row, text="Light", value="light", variable=self.mode_var, bootstyle="secondary",
            command=self._on_mode_change
        ).pack(side=LEFT)

        tb.Label(theme_card, text="Theme:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.theme_combo = tb.Combobox(theme_card, state="readonly", textvariable=self.theme_var, values=THEMES_DARK)
        self.theme_combo.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        self.theme_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_theme())

        tb.Button(theme_card, text="Apply", bootstyle="primary", command=self._apply_theme).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        # Sidebar: Leaderboard
        lb_card = tb.Labelframe(right, text="🏆 Leaderboard (Top 10)", padding=10, bootstyle="secondary")
        lb_card.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        lb_card.columnconfigure(0, weight=1)

        self.lb_text = tk.Text(lb_card, height=10, wrap="none", bd=0, highlightthickness=0)
        self.lb_text.pack(fill=BOTH, expand=YES)

        # Sidebar: status + controls
        status_card = tb.Labelframe(right, text="📌 Run Status", padding=10, bootstyle="secondary")
        status_card.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        status_card.columnconfigure(1, weight=1)

        tb.Label(status_card, text="Difficulty:").grid(row=0, column=0, sticky="w")
        self.status_diff = tb.Label(status_card, text="-", font=("Segoe UI", 10, "bold"))
        self.status_diff.grid(row=0, column=1, sticky="w")

        tb.Label(status_card, text="Mistakes:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.status_mistakes = tb.Label(status_card, text="0", font=("Segoe UI", 10, "bold"))
        self.status_mistakes.grid(row=1, column=1, sticky="w", pady=(6, 0))

        tb.Label(status_card, text="Total time:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.status_time = tb.Label(status_card, text="-", font=("Segoe UI", 10, "bold"))
        self.status_time.grid(row=2, column=1, sticky="w", pady=(6, 0))

        controls = tb.Frame(right)
        controls.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        controls.columnconfigure(0, weight=1)

        tb.Button(controls, text="🔄 Reset Run", bootstyle="warning", command=self.reset_run).pack(fill=X, pady=(0, 8))
        tb.Button(controls, text="📋 Refresh Leaderboard", bootstyle="secondary", command=self._refresh_leaderboard).pack(fill=X)
        tb.Button(controls, text="⬇️ Export Leaderboard CSV", bootstyle="primary",
                  command=self.export_leaderboard_csv).pack(fill=X, pady=(8, 0))

    def _build_setup_tab(self):
        f = self.tab_setup
        f.columnconfigure(1, weight=1)

        tb.Label(f, text="Player name:", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        tb.Entry(f, textvariable=self.player_name).grid(row=0, column=1, sticky="ew")

        tb.Checkbutton(f, text="Enable Explain/Hint Mode", variable=self.explain_mode, bootstyle="round-toggle").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

        # ✅ STORE THIS labelframe reference so we can recolor its title dynamically
        self.diff_box = tb.Labelframe(f, text="Difficulty", padding=12, bootstyle="secondary")
        diff_box = self.diff_box
        diff_box.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        for i, (key, d) in enumerate(core.DIFFS.items()):
            tb.Radiobutton(
                diff_box,
                text=f"{d.name}  (prime digits={d.prime_digits}, {int(d.stage_time_limit)}s per stage)",
                value=key,
                variable=self.diff_choice,
                bootstyle="secondary",
            ).grid(row=i, column=0, sticky="w", pady=3)

        tb.Label(
            f,
            text="Tip: Start with EASY. Each stage has a timer ⏳",
            foreground="#9aa0a6",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))

        tb.Button(f, text="▶ Start Run", bootstyle="success", command=self.start_run).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(14, 0)
        )

    def _build_stage1_tab(self):
        f = self.tab_s1
        f.columnconfigure(0, weight=3)
        f.columnconfigure(1, weight=2)
        f.rowconfigure(2, weight=1)

        tb.Label(f, text="Stage 1: Pick TWO primes (p and q).", font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )

        self.s1_hint = tb.Label(f, text="", wraplength=860, foreground="#cfd8dc")
        self.s1_hint.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 10))

        table_card = tb.Labelframe(f, text="Candidates", padding=10, bootstyle="secondary")
        table_card.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        table_card.rowconfigure(0, weight=1)
        table_card.columnconfigure(0, weight=1)

        cols = ("idx", "value", "type")
        self.cand_tree = tb.Treeview(table_card, columns=cols, show="headings", bootstyle="secondary")
        self.cand_tree.heading("idx", text="#")
        self.cand_tree.heading("value", text="Number")
        self.cand_tree.heading("type", text="Prime?")
        self.cand_tree.column("idx", width=60, anchor="center")
        self.cand_tree.column("value", width=180, anchor="center")
        self.cand_tree.column("type", width=120, anchor="center")
        self.cand_tree.grid(row=0, column=0, sticky="nsew")

        scroll = tb.Scrollbar(table_card, orient="vertical", command=self.cand_tree.yview, bootstyle="secondary")
        scroll.grid(row=0, column=1, sticky="ns")
        self.cand_tree.configure(yscrollcommand=scroll.set)

        right = tb.Labelframe(f, text="Selection", padding=12, bootstyle="secondary")
        right.grid(row=2, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        tb.Label(right, text="Selected p:").grid(row=0, column=0, sticky="w")
        self.p_var = tb.StringVar(value="-")
        tb.Label(right, textvariable=self.p_var, font=("Consolas", 12, "bold")).grid(row=0, column=1, sticky="w")

        tb.Label(right, text="Selected q:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.q_var = tb.StringVar(value="-")
        tb.Label(right, textvariable=self.q_var, font=("Consolas", 12, "bold")).grid(row=1, column=1, sticky="w", pady=(8, 0))

        tb.Button(right, text="Set as p", bootstyle="primary", command=self.stage1_set_p).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0)
        )
        tb.Button(right, text="Set as q", bootstyle="primary", command=self.stage1_set_q).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )
        tb.Button(right, text="✅ Confirm Stage 1", bootstyle="success", command=self.stage1_confirm).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(16, 0)
        )

        tb.Label(right, text="Tip: click a row in the table first.", foreground="#9aa0a6").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

    def _build_stage2_tab(self):
        f = self.tab_s2
        f.columnconfigure(0, weight=1)

        tb.Label(f, text="Stage 2: Key Generation", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")

        self.s2_hint = tb.Label(f, text="", wraplength=860, foreground="#cfd8dc")
        self.s2_hint.grid(row=1, column=0, sticky="w", pady=(6, 10))

        card = tb.Labelframe(f, text="Computed Values", padding=12, bootstyle="secondary")
        card.grid(row=2, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)

        tb.Label(card, text="n =").grid(row=0, column=0, sticky="w")
        self.n_var = tb.StringVar(value="-")
        tb.Label(card, textvariable=self.n_var, font=("Consolas", 12, "bold")).grid(row=0, column=1, sticky="w")

        tb.Label(card, text="phi =").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.phi_var = tb.StringVar(value="-")
        tb.Label(card, textvariable=self.phi_var, font=("Consolas", 12, "bold")).grid(row=1, column=1, sticky="w", pady=(8, 0))

        tb.Label(card, text="Choose e:").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.e_combo = tb.Combobox(card, state="readonly", values=[])
        self.e_combo.grid(row=2, column=1, sticky="w", pady=(12, 0))

        tb.Button(f, text="✅ Confirm Stage 2", bootstyle="success", command=self.stage2_confirm).grid(
            row=3, column=0, sticky="ew", pady=(14, 0)
        )

        self.s2_result = tb.Label(f, text="", wraplength=860, foreground="#7CFC9A")
        self.s2_result.grid(row=4, column=0, sticky="w", pady=(12, 0))

    def _build_stage3_tab(self):
        f = self.tab_s3
        f.columnconfigure(0, weight=1)
        f.rowconfigure(4, weight=1)

        tb.Label(f, text="Stage 3: Encrypt", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")

        self.s3_hint = tb.Label(f, text="", wraplength=860, foreground="#cfd8dc")
        self.s3_hint.grid(row=1, column=0, sticky="w", pady=(6, 10))

        row = tb.Labelframe(f, text="Plaintext Input", padding=12, bootstyle="secondary")
        row.grid(row=2, column=0, sticky="ew")
        row.columnconfigure(1, weight=1)

        tb.Label(row, text="Plaintext:").grid(row=0, column=0, sticky="w")
        self.msg_entry = tb.Entry(row)
        self.msg_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        btn_row = tb.Frame(f)
        btn_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        btn_row.columnconfigure(0, weight=1)
        btn_row.columnconfigure(1, weight=1)

        tb.Button(btn_row, text="🔒 Encrypt", bootstyle="primary", command=self.stage3_encrypt).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        tb.Button(btn_row, text="📋 Copy Ciphertext", bootstyle="secondary", command=self.copy_ciphertext).grid(row=0, column=1, sticky="ew")

        out = tb.Labelframe(f, text="Ciphertext (integers)", padding=12, bootstyle="secondary")
        out.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        out.columnconfigure(0, weight=1)
        out.rowconfigure(0, weight=1)

        self.cipher_text = tk.Text(out, height=8, wrap="word", bd=0, highlightthickness=0)
        self.cipher_text.grid(row=0, column=0, sticky="nsew")

        tb.Button(f, text="✅ Confirm Stage 3", bootstyle="success", command=self.stage3_confirm).grid(
            row=5, column=0, sticky="ew", pady=(12, 0)
        )

    def _build_stage4_tab(self):
        f = self.tab_s4
        f.columnconfigure(0, weight=1)
        f.rowconfigure(4, weight=1)

        tb.Label(f, text="Stage 4: Decrypt + Finish", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")

        self.s4_hint = tb.Label(f, text="", wraplength=860, foreground="#cfd8dc")
        self.s4_hint.grid(row=1, column=0, sticky="w", pady=(6, 10))

        row = tb.Labelframe(f, text="Enter Private Key", padding=12, bootstyle="secondary")
        row.grid(row=2, column=0, sticky="ew")
        row.columnconfigure(1, weight=1)

        tb.Label(row, text="Enter d:").grid(row=0, column=0, sticky="w")
        self.d_entry = tb.Entry(row, width=20)
        self.d_entry.grid(row=0, column=1, sticky="w", padx=(8, 0))

        tb.Button(f, text="🔓 Decrypt + Finish", bootstyle="success", command=self.stage4_finish).grid(
            row=3, column=0, sticky="ew", pady=(12, 0)
        )

        self.final_text = tk.Text(f, height=12, wrap="word", bd=0, highlightthickness=0)
        self.final_text.grid(row=4, column=0, sticky="nsew", pady=(12, 0))

    # =========================
    # Theme
    # =========================
    def _on_mode_change(self):
        mode = self.mode_var.get()
        if mode == "dark":
            self.theme_combo.configure(values=THEMES_DARK)
            if self.theme_var.get() not in THEMES_DARK:
                self.theme_var.set("darkly")
        else:
            self.theme_combo.configure(values=THEMES_LIGHT)
            if self.theme_var.get() not in THEMES_LIGHT:
                self.theme_var.set("flatly")
        self._apply_theme()

    def _apply_theme(self):
        theme = self.theme_var.get().strip() or "darkly"
        try:
            self.style.theme_use(theme)
        except Exception:
            messagebox.showwarning("Theme", f"Theme '{theme}' not available. Using default.")
        self._apply_text_theme()

    def _apply_text_theme(self):
        mode = self.mode_var.get()
        if mode == "dark":
            bg, fg, ins = "#111418", "#E6E6E6", "#7CFC9A"
            title_color = "#FFFFFF"   # bright in dark mode
        else:
            bg, fg, ins = "#FFFFFF", "#111111", "#0A7D2C"
            title_color = "#111111"   # dark in light mode

        for t in [self.lb_text, self.cipher_text, self.final_text]:
            t.configure(bg=bg, fg=fg, insertbackground=ins)

        # ✅ Make "Difficulty" label more visible (dynamic)
        if self.diff_box is not None:
            try:
                self.diff_box.configure(foreground=title_color)
            except Exception:
                pass

    # =========================
    # Run lifecycle
    # =========================
    def start_run(self):
        choice = self.diff_choice.get().strip()
        self.diff = core.DIFFS.get(choice, core.DIFFS["1"])
        self.status_diff.config(text=self.diff.name)

        self.reset_run(keep_setup=True)

        self.run_started_at = time.perf_counter()
        self._update_total_time_label()

        self._set_stage_hints()
        self._stage1_generate_candidates()

        self.nb.select(self.tab_s1)
        self._start_stage_timer()

    def reset_run(self, keep_setup=False):
        self._stop_stage_timer()

        self.p = self.q = self.n = self.phi = self.e = self.d = None
        self.original_msg = None
        self.cipher = None

        self.mistakes = 0
        self.status_mistakes.config(text="0")
        self.status_time.config(text="-")
        self.timer_label.config(text="⏳ Stage Timer: -")
        self.timer_bar.configure(maximum=1)
        self.timer_bar["value"] = 0

        self.p_var.set("-")
        self.q_var.set("-")
        self.n_var.set("-")
        self.phi_var.set("-")
        self.e_combo["values"] = []
        self.e_combo.set("")
        self.s2_result.config(text="")
        self.msg_entry.delete(0, END)
        self.cipher_text.delete("1.0", END)
        self.d_entry.delete(0, END)
        self.final_text.delete("1.0", END)

        for item in self.cand_tree.get_children():
            self.cand_tree.delete(item)

        if not keep_setup:
            self.run_started_at = None

        self._set_stage_hints()
        self._apply_text_theme()

    # =========================
    # Timer
    # =========================
    def _start_stage_timer(self):
        self.deadline = time.perf_counter() + float(self.diff.stage_time_limit)
        self.timer_bar.configure(maximum=float(self.diff.stage_time_limit))
        self._tick_timer()

    def _stop_stage_timer(self):
        if self.timer_job is not None:
            try:
                self.after_cancel(self.timer_job)
            except Exception:
                pass
        self.timer_job = None
        self.deadline = None

    def _tick_timer(self):
        if self.deadline is None:
            return
        remain = self.deadline - time.perf_counter()
        if remain <= 0:
            self.timer_label.config(text="⏳ Stage Timer: 0.0s")
            self.timer_bar["value"] = 0
            self._on_stage_timeout()
            return

        self.timer_label.config(text=f"⏳ Stage Timer: {remain:.1f}s")
        self.timer_bar["value"] = max(0.0, remain)
        self._update_total_time_label()
        self.timer_job = self.after(100, self._tick_timer)

    def _on_stage_timeout(self):
        self._stop_stage_timer()
        messagebox.showerror("Time's up!", "⏰ Time's up for this stage. Run ended.")
        self._game_over("Timeout")

    def _update_total_time_label(self):
        if self.run_started_at is None:
            return
        t = time.perf_counter() - self.run_started_at
        self.status_time.config(text=f"{t:.3f}s")

    # =========================
    # Helpers
    # =========================
    def _set_stage_hints(self):
        if self.explain_mode.get():
            self.s1_hint.config(text="💡 Choose two PRIME numbers p and q. RSA uses n=p×q.")
            self.s2_hint.config(text="💡 Compute n and φ(n)=(p−1)(q−1). Choose e with gcd(e,φ)=1, then d=e⁻¹ mod φ.")
            self.s3_hint.config(text="💡 Encrypt each char: C = M^e mod n (M is ASCII).")
            self.s4_hint.config(text="💡 Decrypt: M = C^d mod n. If d correct, message returns exactly.")
        else:
            self.s1_hint.config(text="")
            self.s2_hint.config(text="")
            self.s3_hint.config(text="")
            self.s4_hint.config(text="")

    def _inc_mistake(self, msg="Invalid input"):
        self.mistakes += 1
        self.status_mistakes.config(text=str(self.mistakes))
        messagebox.showwarning("❌ Try again", msg)

    def _game_over(self, reason):
        self._refresh_leaderboard()
        elapsed = (time.perf_counter() - self.run_started_at) if self.run_started_at else 0.0
        self.final_text.delete("1.0", END)
        self.final_text.insert("end", f"💥 GAME OVER!\nReason: {reason}\nTime before fail: {elapsed:.3f}s\nMistakes: {self.mistakes}\n")
        self.nb.select(self.tab_s4)

    # =========================
    # Stage 1
    # =========================
    def _stage1_generate_candidates(self):
        self.candidates = core.make_candidates(self.diff.prime_digits, total=10, prime_count=6)

        for item in self.cand_tree.get_children():
            self.cand_tree.delete(item)

        for i, v in enumerate(self.candidates, 1):
            is_p = "YES" if core.is_probable_prime(v) else "NO"
            self.cand_tree.insert("", END, values=(i, v, is_p))

        kids = self.cand_tree.get_children()
        if kids:
            self.cand_tree.selection_set(kids[0])

    def _get_selected_candidate_value(self):
        sel = self.cand_tree.selection()
        if not sel:
            return None
        values = self.cand_tree.item(sel[0], "values")
        if not values:
            return None
        idx = int(values[0]) - 1
        if idx < 0 or idx >= len(self.candidates):
            return None
        return self.candidates[idx]

    def stage1_set_p(self):
        v = self._get_selected_candidate_value()
        if v is None:
            self._inc_mistake("Select a row in the table first.")
            return
        self.p = v
        self.p_var.set(str(v))

    def stage1_set_q(self):
        v = self._get_selected_candidate_value()
        if v is None:
            self._inc_mistake("Select a row in the table first.")
            return
        self.q = v
        self.q_var.set(str(v))

    def stage1_confirm(self):
        if self.p is None or self.q is None:
            self._inc_mistake("Set both p and q first.")
            return
        if self.p == self.q:
            self._inc_mistake("p and q must be different.")
            return
        if (not core.is_probable_prime(self.p)) or (not core.is_probable_prime(self.q)):
            self._inc_mistake("One (or both) numbers are not prime.")
            return

        self._stop_stage_timer()
        messagebox.showinfo("Stage 1 ✅", f"Prime selection complete!\np={self.p}\nq={self.q}")
        self._stage2_prepare()
        self.nb.select(self.tab_s2)
        self._start_stage_timer()

    # =========================
    # Stage 2
    # =========================
    def _stage2_prepare(self):
        self.n = self.p * self.q
        self.phi = (self.p - 1) * (self.q - 1)
        self.n_var.set(str(self.n))
        self.phi_var.set(str(self.phi))

        options = core.candidate_es(self.phi, count=7)
        self.e_options = options
        self.e_combo["values"] = [str(x) for x in options]
        if options:
            self.e_combo.current(0)

    def stage2_confirm(self):
        if self.n is None or self.phi is None:
            self._inc_mistake("Complete Stage 1 first.")
            return

        raw = self.e_combo.get().strip()
        if not raw.isdigit():
            self._inc_mistake("Pick a valid e from the dropdown.")
            return
        e = int(raw)

        if e not in getattr(self, "e_options", []):
            self._inc_mistake("Pick e from the dropdown list.")
            return
        if math.gcd(e, self.phi) != 1:
            self._inc_mistake("Selected e is not coprime with φ(n).")
            return

        self.e = e
        self.d = core.modinv(e, self.phi)

        self._stop_stage_timer()
        self.s2_result.config(text=f"✅ Keys ready!\nPublic: (e={self.e}, n={self.n})\nPrivate: (d={self.d}, n={self.n})")
        messagebox.showinfo("Stage 2 ✅", f"Key generation complete!\ne={self.e}\nd={self.d}")

        self.nb.select(self.tab_s3)
        self._start_stage_timer()

    # =========================
    # Stage 3
    # =========================
    def stage3_encrypt(self):
        if self.e is None or self.n is None:
            self._inc_mistake("Complete Stage 2 first.")
            return

        msg = self.msg_entry.get()
        if msg == "":
            self._inc_mistake("Message cannot be empty.")
            return

        nums = [ord(ch) for ch in msg]
        if any(m >= self.n for m in nums):
            self._inc_mistake("Some ASCII values are >= n. Use shorter message or higher difficulty.")
            return

        self.original_msg = msg
        self.cipher = [pow(ord(ch), self.e, self.n) for ch in msg]

        self.cipher_text.delete("1.0", END)
        self.cipher_text.insert(END, " ".join(map(str, self.cipher)))

    def copy_ciphertext(self):
        text = self.cipher_text.get("1.0", END).strip()
        if not text:
            messagebox.showinfo("Copy", "Ciphertext is empty. Click Encrypt first.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copy", "✅ Ciphertext copied to clipboard!")

    def stage3_confirm(self):
        if not self.cipher or self.original_msg is None:
            self._inc_mistake("Click Encrypt first to generate ciphertext.")
            return

        self._stop_stage_timer()
        messagebox.showinfo("Stage 3 ✅", "Encryption complete! Proceed to Stage 4.")
        self.nb.select(self.tab_s4)
        self._start_stage_timer()

    # =========================
    # Stage 4
    # =========================
    def stage4_finish(self):
        if self.d is None or self.cipher is None:
            self._inc_mistake("Complete previous stages first.")
            return

        raw = self.d_entry.get().strip()
        if not raw.lstrip("-").isdigit():
            self._inc_mistake("d must be an integer.")
            return
        user_d = int(raw)

        if user_d != self.d:
            self._inc_mistake("Wrong d. Try again.")
            return

        plain_nums = [pow(c, self.d, self.n) for c in self.cipher]
        decrypted = "".join(chr(x) for x in plain_nums)

        if decrypted != self.original_msg:
            self._stop_stage_timer()
            self._game_over("Decryption mismatch (does not match original).")
            return

        self._stop_stage_timer()
        total_time = time.perf_counter() - self.run_started_at

        rank, is_champion = core.update_board(self.player_name.get().strip() or "Player", self.diff.name, total_time)
        self._refresh_leaderboard()

        badges = core.compute_achievements(
            success=True,
            total_time=total_time,
            difficulty_name=self.diff.name,
            total_mistakes=self.mistakes,
            is_champion=is_champion,
        )

        self.final_text.delete("1.0", END)
        self.final_text.insert(
            END,
            "🎉 SUCCESS!\n"
            f"Decrypted message: {decrypted}\n\n"
            f"⏱️ Total time: {total_time:.3f}s\n"
            f"❌ Mistakes: {self.mistakes}\n"
            f"🏆 Leaderboard rank: #{rank if rank != 999 else 'N/A'}\n\n",
        )

        if badges:
            self.final_text.insert(END, "🎖️ Achievements:\n")
            for b in badges:
                self.final_text.insert(END, f"  • {b}\n")
        else:
            self.final_text.insert(END, "🎖️ Achievements:\n  (none this run)\n")

        self.confetti_popup()

    # =========================
    # Leaderboard
    # =========================
    def _refresh_leaderboard(self):
        board = core.load_board()
        self.lb_text.delete("1.0", END)
        if not board:
            self.lb_text.insert(END, "(empty) Be the first! 😄\n")
            return
        for i, row in enumerate(board, 1):
            self.lb_text.insert(
                END,
                f"{i:>2}. {row['name']} | {row['difficulty']} | {row['time_sec']}s | {row['timestamp']}\n",
            )


if __name__ == "__main__":
    app = RSAQuestGUI()
    app.mainloop()
