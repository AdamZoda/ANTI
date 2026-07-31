import tkinter as tk
from tkinter import ttk
import traceback
import sys
import os
import threading
import time
import math

# ══════════════════════════════════════════════
#  ANTI DEFENSE SYSTEM — Modern Neon UI v2.7
# ══════════════════════════════════════════════

BG_DARK      = "#070b14"
BG_CARD      = "#0d1526"
BG_CARD2     = "#111d35"
NEON_CYAN    = "#00f2fe"
NEON_BLUE    = "#4facfe"
NEON_GREEN   = "#00ff9d"
NEON_RED     = "#ff2d55"
NEON_ORANGE  = "#ff9500"
TEXT_PRIMARY  = "#e8f4fd"
TEXT_SECONDARY= "#5b7fa6"
TEXT_DIM      = "#2a4166"
BORDER_DIM    = "#1a2f52"
BORDER_NEON   = "#00f2fe"


class AntiScanGUI:
    def __init__(self, root, scan_runner_callback, on_complete_callback, on_crash_callback=None):
        self.root = root
        self.scan_runner_callback = scan_runner_callback
        self.on_complete_callback = on_complete_callback
        self.on_crash_callback = on_crash_callback

        self.log_history = []
        self.show_debug  = False
        self._pulse_job  = None
        self._pulse_state = 0

        # ── Fenêtre principale ──────────────────────────
        self.root.title("ANTI DEFENSE SYSTEM")
        self.root.geometry("860x560")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(False, False)
        self.root.overrideredirect(False)

        # Centrer sur l'écran
        self.root.update_idletasks()
        w = 860; h = 560
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Raccourcis
        self.root.bind("<Control-i>", self.toggle_debug_panel)
        self.root.bind("<Control-I>", self.toggle_debug_panel)

        self._build_ui()
        self._start_pulse()

    # ─────────────────────────────────────────────────────────
    #  BUILD UI
    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── HEADER ──────────────────────────────────────────
        header = tk.Frame(self.root, bg=BG_DARK, height=90)
        header.pack(fill=tk.X, padx=0, pady=0)
        header.pack_propagate(False)

        # Logo ANTI (Canvas avec glow)
        logo_canvas = tk.Canvas(header, width=180, height=72,
                                bg=BG_DARK, highlightthickness=0)
        logo_canvas.place(x=30, y=10)
        self._draw_logo(logo_canvas)

        # Texte info droite du logo
        info_block = tk.Frame(header, bg=BG_DARK)
        info_block.place(x=222, y=18)

        tk.Label(info_block, text="ANTI DEFENSE SYSTEM",
                 font=("Consolas", 13, "bold"),
                 fg=NEON_CYAN, bg=BG_DARK).pack(anchor="w")
        tk.Label(info_block, text="System Integrity & Telemetry Scanner  ·  v2.7",
                 font=("Consolas", 9),
                 fg=TEXT_SECONDARY, bg=BG_DARK).pack(anchor="w", pady=(2,0))
        tk.Label(info_block, text="100% Defensive Security Engine",
                 font=("Consolas", 8),
                 fg=TEXT_DIM, bg=BG_DARK).pack(anchor="w")

        # Indicateur statut (coin haut droit)
        self.status_dot_canvas = tk.Canvas(header, width=12, height=12,
                                           bg=BG_DARK, highlightthickness=0)
        self.status_dot_canvas.place(x=800, y=20)
        self.status_dot = self.status_dot_canvas.create_oval(1,1,11,11,
                            fill=NEON_CYAN, outline=NEON_BLUE)

        tk.Label(header, text="SCANNING", font=("Consolas", 7, "bold"),
                 fg=NEON_CYAN, bg=BG_DARK).place(x=815, y=19)

        # Ligne séparatrice néon
        sep = tk.Canvas(self.root, height=2, bg=BG_DARK, highlightthickness=0)
        sep.pack(fill=tk.X, padx=0)
        sep.create_line(0, 1, 860, 1, fill=NEON_CYAN, width=1)
        # fade gradient simulé avec 2 lignes
        sep.create_line(0, 0, 860, 0, fill=BG_CARD2, width=1)

        # ── MAIN CONTENT CARD ───────────────────────────────
        card = tk.Frame(self.root, bg=BG_CARD,
                        highlightbackground=BORDER_DIM,
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        inner = tk.Frame(card, bg=BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)

        # ── Étape active ─────────────────────────────────────
        step_row = tk.Frame(inner, bg=BG_CARD)
        step_row.pack(fill=tk.X, pady=(0, 6))

        self.step_icon = tk.Label(step_row, text="◈", font=("Consolas", 14, "bold"),
                                  fg=NEON_CYAN, bg=BG_CARD)
        self.step_icon.pack(side=tk.LEFT, padx=(0, 10))

        step_texts = tk.Frame(step_row, bg=BG_CARD)
        step_texts.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.status_label = tk.Label(step_texts,
                                     text="Initialisation du moteur d'analyse...",
                                     font=("Consolas", 11, "bold"),
                                     fg=TEXT_PRIMARY, bg=BG_CARD, anchor="w")
        self.status_label.pack(fill=tk.X)

        self.info_label = tk.Label(step_texts,
                                   text="Chargement des modules de sécurité...",
                                   font=("Consolas", 9),
                                   fg=TEXT_SECONDARY, bg=BG_CARD, anchor="w")
        self.info_label.pack(fill=tk.X, pady=(2,0))

        # ── Barre de progression custom ──────────────────────
        prog_container = tk.Frame(inner, bg=BG_CARD)
        prog_container.pack(fill=tk.X, pady=(14, 6))

        # Labels haut : label "PROGRESS" + pourcentage
        prog_top = tk.Frame(prog_container, bg=BG_CARD)
        prog_top.pack(fill=tk.X, pady=(0,5))

        tk.Label(prog_top, text="PROGRESSION",
                 font=("Consolas", 7, "bold"),
                 fg=TEXT_DIM, bg=BG_CARD).pack(side=tk.LEFT)

        self.pct_label = tk.Label(prog_top, text="0%",
                                   font=("Consolas", 9, "bold"),
                                   fg=NEON_CYAN, bg=BG_CARD)
        self.pct_label.pack(side=tk.RIGHT)

        # Canvas barre néon
        self.bar_canvas = tk.Canvas(prog_container, height=18,
                                    bg=BG_CARD2, highlightthickness=1,
                                    highlightbackground=BORDER_DIM)
        self.bar_canvas.pack(fill=tk.X)
        self._bar_width = 816  # sera mis à jour
        self._draw_bar(0)

        # ASCII mini bar (style terminal, sous la barre graphique)
        self.ascii_bar = tk.Label(inner,
                                  text=".: [" + "-"*40 + "]   0%",
                                  font=("Consolas", 9),
                                  fg=TEXT_DIM, bg=BG_CARD, anchor="w")
        self.ascii_bar.pack(fill=tk.X, pady=(4, 0))

        # ── Ligne de séparation ──────────────────────────────
        sep2 = tk.Canvas(inner, height=1, bg=BG_CARD, highlightthickness=0)
        sep2.pack(fill=tk.X, pady=10)
        sep2.create_line(0, 0, 900, 0, fill=BORDER_DIM)

        # ── Footer info ──────────────────────────────────────
        footer_row = tk.Frame(inner, bg=BG_CARD)
        footer_row.pack(fill=tk.X)

        tk.Label(footer_row, text="CTRL + I  →  Rapport technique / debug",
                 font=("Consolas", 8), fg=TEXT_DIM, bg=BG_CARD).pack(side=tk.LEFT)

        tk.Label(footer_row, text="⚡ ANTI v2.7",
                 font=("Consolas", 8, "bold"), fg=TEXT_DIM, bg=BG_CARD).pack(side=tk.RIGHT)

        # ── ERREUR FRAME (masquée par défaut) ───────────────
        self.error_frame = tk.Frame(self.root, bg="#14060f",
                                    highlightbackground=NEON_RED,
                                    highlightthickness=2)

        err_inner = tk.Frame(self.error_frame, bg="#14060f")
        err_inner.pack(fill=tk.BOTH, padx=14, pady=10)

        err_top = tk.Frame(err_inner, bg="#14060f")
        err_top.pack(fill=tk.X)

        self.error_icon = tk.Label(err_top, text="⛔",
                                   font=("Segoe UI", 14),
                                   fg=NEON_RED, bg="#14060f")
        self.error_icon.pack(side=tk.LEFT, padx=(0,8))

        self.error_title = tk.Label(err_top,
                                    text="ERREUR DÉTECTÉE",
                                    font=("Consolas", 11, "bold"),
                                    fg=NEON_RED, bg="#14060f")
        self.error_title.pack(side=tk.LEFT)

        self.error_msg_label = tk.Label(err_inner,
                                        text="",
                                        font=("Consolas", 8),
                                        fg="#ffb3b3", bg="#14060f",
                                        justify=tk.LEFT, wraplength=780)
        self.error_msg_label.pack(anchor="w", pady=(5,0))

        # ── DEBUG PANEL (masqué, CTRL+I) ────────────────────
        self.debug_frame = tk.Frame(self.root, bg="#050a10",
                                    highlightbackground=NEON_CYAN,
                                    highlightthickness=1)

        dbg_top = tk.Frame(self.debug_frame, bg="#050a10")
        dbg_top.pack(fill=tk.X, padx=10, pady=(8,4))

        tk.Label(dbg_top, text="🛠  DEBUG / CRASH REPORT",
                 font=("Consolas", 9, "bold"),
                 fg=NEON_CYAN, bg="#050a10").pack(side=tk.LEFT)

        self.copy_btn = tk.Button(dbg_top,
                                  text="  📋 Copier Crash Report  ",
                                  font=("Consolas", 8, "bold"),
                                  fg=BG_DARK, bg=NEON_CYAN,
                                  activebackground=NEON_BLUE,
                                  activeforeground=BG_DARK,
                                  relief=tk.FLAT, cursor="hand2",
                                  command=self.copy_debug_logs)
        self.copy_btn.pack(side=tk.RIGHT)

        self.debug_text = tk.Text(self.debug_frame,
                                  height=7,
                                  font=("Consolas", 8),
                                  fg=NEON_GREEN, bg="#020609",
                                  insertbackground=NEON_CYAN,
                                  relief=tk.FLAT, padx=8, pady=6)
        self.debug_text.pack(fill=tk.BOTH, expand=True,
                             padx=10, pady=(0,8))

    # ─────────────────────────────────────────────────────────
    #  LOGO CANVAS (ASCII Neon)
    # ─────────────────────────────────────────────────────────
    def _draw_logo(self, canvas):
        # Blocs A-N-T-I en style pixel / neon
        logo_lines = [
            "  ██╗  ██╗ ███╗  ██╗  ██████╗  ██╗",
            "  ██║  ██║ ████╗ ██║  ╚══██╔╝  ██║",
            "  ███████║ ██╔██╗██║    ██║    ██║",
            "  ██╔══██║ ██║╚████║    ██║    ██║",
            "  ██║  ██║ ██║ ╚███║  ██████╗  ██║",
            "  ╚═╝  ╚═╝ ╚═╝  ╚══╝  ╚═════╝  ╚═╝",
        ]
        # Ombre glow simulé (même texte, décalé, couleur sombre)
        for i, line in enumerate(logo_lines):
            canvas.create_text(3, 7 + i * 10, text=line,
                               anchor="nw", font=("Consolas", 7, "bold"),
                               fill="#003344")
        for i, line in enumerate(logo_lines):
            canvas.create_text(2, 6 + i * 10, text=line,
                               anchor="nw", font=("Consolas", 7, "bold"),
                               fill=NEON_CYAN)

    # ─────────────────────────────────────────────────────────
    #  BARRE DE PROGRESSION NÉON
    # ─────────────────────────────────────────────────────────
    def _draw_bar(self, percent):
        c = self.bar_canvas
        c.delete("all")
        w = c.winfo_width() or 816
        h = 18
        filled = int((percent / 100) * w)

        # Background
        c.create_rectangle(0, 0, w, h, fill=BG_CARD2, outline="")

        if filled > 0:
            # Couleur dynamique selon progression
            if percent < 40:
                color = NEON_BLUE
                glow  = "#1a3f7a"
            elif percent < 80:
                color = NEON_CYAN
                glow  = "#003344"
            else:
                color = NEON_GREEN
                glow  = "#00331f"

            # Glow (barre élargie semi-transparente simulée)
            c.create_rectangle(0, 3, filled, h-3, fill=glow, outline="")
            # Barre principale
            c.create_rectangle(0, 5, filled, h-5, fill=color, outline="")
            # Highlight
            c.create_rectangle(0, 5, filled, 8, fill="#ffffff", outline="",
                               stipple="gray25")
            # Tip glow
            c.create_rectangle(max(0, filled-8), 2, filled+2, h-2,
                               fill=color, outline="")

    # ─────────────────────────────────────────────────────────
    #  ANIMATION : PULSE ICÔNE
    # ─────────────────────────────────────────────────────────
    def _start_pulse(self):
        def _pulse():
            self._pulse_state = (self._pulse_state + 1) % 6
            icons = ["◈", "◇", "◈", "◆", "◈", "◇"]
            colors = [NEON_CYAN, NEON_BLUE, NEON_CYAN, "#38bdf8", NEON_CYAN, NEON_BLUE]
            if hasattr(self, 'step_icon'):
                try:
                    self.step_icon.config(text=icons[self._pulse_state],
                                          fg=colors[self._pulse_state])
                except Exception:
                    pass
            self._pulse_job = self.root.after(600, _pulse)
        _pulse()

    # ─────────────────────────────────────────────────────────
    #  UPDATE PROGRESS
    # ─────────────────────────────────────────────────────────
    def update_progress(self, stage, percent, info=""):
        def _update():
            # Barre néon graphique
            self._draw_bar(percent)

            # Pourcentage
            self.pct_label.config(text=f"{percent}%",
                                  fg=NEON_GREEN if percent >= 80 else
                                     NEON_CYAN  if percent >= 40 else NEON_BLUE)

            # Labels
            self.status_label.config(text=stage)
            self.info_label.config(text=info or "Traitement des données...")

            # ASCII bar (style terminal)
            filled = int(percent / 2.5)
            bar = "=" * max(0, filled - 1) + (">" if filled > 0 else "")
            bar = bar.ljust(40, ".")
            self.ascii_bar.config(text=f".: [{bar}]  {percent:3d}%")

            # Log debug
            log_line = f"[{time.strftime('%H:%M:%S')}] [{percent:3d}%] {stage} — {info}"
            self.log_history.append(log_line)
            self.debug_text.insert(tk.END, log_line + "\n")
            self.debug_text.see(tk.END)

        self.root.after(0, _update)

    # ─────────────────────────────────────────────────────────
    #  COUNTDOWN + ERREUR
    # ─────────────────────────────────────────────────────────
    def start_crash_countdown(self, seconds=30):
        def _tick(rem):
            if rem > 0:
                self.error_title.config(
                    text=f"ERREUR  —  AUTO-DESTRUCTION DANS {rem}s")
                self.root.after(1000, lambda: _tick(rem - 1))
            else:
                self.error_title.config(text="💥  SUPPRESSION EN COURS...")
        _tick(seconds)

    def show_error(self, err_msg, is_antivirus=False):
        def _show():
            # Masquer le card principal, afficher l'erreur
            self.error_frame.pack(fill=tk.X, padx=20, pady=(4, 4))

            if is_antivirus:
                self.error_title.config(
                    text="⚠  BLOCAGE ANTIVIRUS  —  AUTO-DESTRUCTION 30s")
                self.error_msg_label.config(
                    text="Windows Defender, SmartScreen ou un antivirus tiers bloque l'accès aux télémétries système.\n"
                         "👉  Désactivez l'antivirus temporairement, puis relancez.\n"
                         "     Appuyez sur CTRL + I pour copier le rapport avant suppression.")
            else:
                self.error_title.config(
                    text="⛔  ERREUR DE SCAN  —  AUTO-DESTRUCTION 30s")
                self.error_msg_label.config(
                    text=f"Erreur : {err_msg}\n"
                         "     Appuyez sur CTRL + I → 'Copier Crash Report' (30 secondes avant suppression).")

            # Ouvrir debug auto
            if not self.show_debug:
                self.toggle_debug_panel(None)

            self.start_crash_countdown(30)

            if self.on_crash_callback:
                self.on_crash_callback()

        self.root.after(0, _show)

    # ─────────────────────────────────────────────────────────
    #  DEBUG PANEL TOGGLE
    # ─────────────────────────────────────────────────────────
    def toggle_debug_panel(self, event=None):
        self.show_debug = not self.show_debug
        if self.show_debug:
            self.debug_frame.pack(fill=tk.BOTH, expand=True,
                                  padx=20, pady=(0, 14))
        else:
            self.debug_frame.pack_forget()

    def copy_debug_logs(self):
        full_logs = "\n".join(self.log_history)
        self.root.clipboard_clear()
        self.root.clipboard_append(full_logs)
        self.copy_btn.config(text="  ✓  Copié !  ",
                             bg=NEON_GREEN, fg=BG_DARK)
        self.root.after(2000, lambda: self.copy_btn.config(
            text="  📋 Copier Crash Report  ",
            bg=NEON_CYAN, fg=BG_DARK))

    # ─────────────────────────────────────────────────────────
    #  SCAN THREAD
    # ─────────────────────────────────────────────────────────
    def start_scan_thread(self):
        def _worker():
            try:
                self.scan_runner_callback(self.update_progress)
                self.root.after(1000, self.on_complete_callback)
            except Exception as e:
                err_str = str(e)
                tb_str  = traceback.format_exc()
                self.log_history.append(f"\nCRASH TRACEBACK:\n{tb_str}")
                is_av = any(k in err_str.lower() for k in
                            ["permission", "access denied", "blocked",
                             "antivirus", "unauthorized"])
                self.show_error(err_str, is_antivirus=is_av)
                if self.on_crash_callback:
                    self.on_crash_callback()

        threading.Thread(target=_worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────
def launch_gui_app(scan_runner_func, on_complete_func, on_crash_callback=None):
    root = tk.Tk()
    app  = AntiScanGUI(root, scan_runner_func, on_complete_func,
                       on_crash_callback=on_crash_callback)
    root.after(500, app.start_scan_thread)
    root.mainloop()
