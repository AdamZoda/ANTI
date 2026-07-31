import tkinter as tk
import traceback
import threading
import time

# ══════════════════════════════════════════════
#  ANTI DEFENSE SYSTEM — Terminal UI v2.7
#  Style : terminal neon, sans barre Windows
#  Features : Always on Top, Mini Widget Mode
# ══════════════════════════════════════════════

BG          = "#0b0f19"
NEON        = "#00f2fe"
NEON_DIM    = "#006070"
WHITE       = "#e8f4fd"
GRAY        = "#4a6a8a"
GRAY_DIM    = "#1e2d3d"


class AntiScanGUI:
    def __init__(self, root, scan_runner_callback, on_complete_callback, on_crash_callback=None):
        self.root = root
        self.scan_runner_callback  = scan_runner_callback
        self.on_complete_callback  = on_complete_callback
        self.on_crash_callback     = on_crash_callback
        self.log_history           = []
        self._scan_done            = False
        self.current_percent       = 0
        self.current_stage         = "Initialisation"

        # ── Fenêtre sans barre Windows & Toujours au premier plan ──
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)  # Reste TOUJOURS devant
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # Taille & centrage de la grande fenêtre
        self.normal_w, self.normal_h = 820, 480
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.normal_x = (sw - self.normal_w) // 2
        self.normal_y = (sh - self.normal_h) // 2
        self.root.geometry(f"{self.normal_w}x{self.normal_h}+{self.normal_x}+{self.normal_y}")

        # États de drag
        self._drag_x = 0
        self._drag_y = 0

        # Bloquer fermeture Alt+F4
        self.root.protocol("WM_DELETE_WINDOW", self._block_close)

        # Création du mini-widget (masqué au départ)
        self.mini_mode = False
        self.mini_window = None

        self._build_ui()

    def _block_close(self):
        if not self._scan_done:
            pass

    # ─────────────────────────────────────────────────────────
    #  BUILD UI
    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Barre de titre custom (draggable) ────────────────
        self.title_bar = tk.Frame(self.root, bg=GRAY_DIM, height=28)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)

        tk.Label(self.title_bar, text=" ANTI DEFENSE SYSTEM  v2.7",
                 font=("Consolas", 9, "bold"),
                 fg=NEON, bg=GRAY_DIM).pack(side=tk.LEFT, padx=8, pady=5)

        # Bouton Réduire en mini widget (Style terminal néon)
        self.minimize_btn = tk.Label(self.title_bar, text="[ _ ] ",
                                     font=("Consolas", 10, "bold"),
                                     fg=NEON, bg=GRAY_DIM, cursor="hand2")
        self.minimize_btn.pack(side=tk.RIGHT, padx=8, pady=4)
        self.minimize_btn.bind("<Button-1>", lambda e: self.switch_to_mini())

        # Drag handlers sur la barre de titre
        self.title_bar.bind("<ButtonPress-1>",   self._drag_start)
        self.title_bar.bind("<B1-Motion>",        self._drag_move)

        # Bordure néon sous la barre titre
        sep = tk.Frame(self.root, bg=NEON, height=1)
        sep.pack(fill=tk.X)

        # ── Zone principale ───────────────────────────────────
        main = tk.Frame(self.root, bg=BG, padx=28, pady=18)
        main.pack(fill=tk.BOTH, expand=True)

        # ── ASCII Art Banner ──────────────────────────────────
        ascii_art = (
            "=========================================================================\n"
            "   ██████╗   ███╗  ██╗  ████████╗  ██╗      🛡  ANTI DEFENSE SYSTEM\n"
            "  ██╔══██╗  ████╗ ██║  ╚══██╔══╝  ██║         System Integrity & Telemetry Scanner\n"
            "  ███████║  ██╔██╗██║     ██║     ██║         Version 2.7  (MAJESTIC)\n"
            "  ██╔══██║  ██║╚████║     ██║     ██║         100% Defensive Security Engine\n"
            "  ██║  ██║  ██║ ╚███║     ██║     ██║\n"
            "  ╚═╝  ╚═╝  ╚═╝  ╚══╝    ╚═╝     ╚═╝\n"
            "========================================================================="
        )
        tk.Label(main, text=ascii_art,
                 font=("Consolas", 8, "bold"),
                 fg=NEON, bg=BG,
                 justify=tk.LEFT).pack(anchor="w", pady=(0, 14))

        # ── Status ────────────────────────────────────────────
        self.status_label = tk.Label(main,
                                     text="⏳  Démarrage du scan système...",
                                     font=("Consolas", 11, "bold"),
                                     fg=WHITE, bg=BG, anchor="w")
        self.status_label.pack(fill=tk.X, pady=(0, 4))

        self.info_label = tk.Label(main,
                                   text="Initialisation des modules de sécurité...",
                                   font=("Consolas", 9),
                                   fg=GRAY, bg=BG, anchor="w")
        self.info_label.pack(fill=tk.X, pady=(0, 10))

        # ── Barre ASCII style terminal ────────────────────────
        self.progress_label = tk.Label(main,
                                       text=".: [" + "-"*40 + "]   0%",
                                       font=("Consolas", 11, "bold"),
                                       fg=NEON, bg=BG, anchor="w")
        self.progress_label.pack(fill=tk.X)

        # ── Panneau erreur (masqué par défaut) ────────────────
        self.error_frame = tk.Frame(main, bg="#180a0a",
                                    highlightbackground="#ff2d55",
                                    highlightthickness=1)

        self.error_title = tk.Label(self.error_frame,
                                    text="❌  ERREUR DÉTECTÉE",
                                    font=("Consolas", 10, "bold"),
                                    fg="#ff2d55", bg="#180a0a", anchor="w")
        self.error_title.pack(anchor="w", padx=10, pady=(8, 2))

        self.error_msg = tk.Label(self.error_frame,
                                  text="",
                                  font=("Consolas", 8),
                                  fg="#ffb3b3", bg="#180a0a",
                                  justify=tk.LEFT, wraplength=740, anchor="w")
        self.error_msg.pack(anchor="w", padx=10, pady=(0, 8))

    # ─────────────────────────────────────────────────────────
    #  DRAG WINDOW (Pour déplacer la grande fenêtre)
    # ─────────────────────────────────────────────────────────
    def _drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        self.normal_x = self.root.winfo_x() + dx
        self.normal_y = self.root.winfo_y() + dy
        self.root.geometry(f"+{self.normal_x}+{self.normal_y}")

    # ─────────────────────────────────────────────────────────
    #  MINI WIDGET SYSTEM (Bulle discrète dans le coin)
    # ─────────────────────────────────────────────────────────
    def switch_to_mini(self):
        """Masque la grande fenêtre et ouvre un mini widget discret en bas à droite."""
        if self._scan_done:
            return  # Pas besoin si scan fini

        self.mini_mode = True
        self.root.withdraw()  # Masque la grande fenêtre

        # Création de la fenêtre mini widget flottante
        self.mini_window = tk.Toplevel(self.root)
        self.mini_window.overrideredirect(True)
        self.mini_window.attributes("-topmost", True)
        self.mini_window.configure(bg=BG, highlightbackground=NEON, highlightthickness=1)

        # Taille mini widget (cercle/carré discret de 56x56)
        w, h = 60, 60
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # Placé dans le coin inférieur droit (juste au dessus de la barre des tâches)
        pos_x = sw - w - 25
        pos_y = sh - h - 55
        self.mini_window.geometry(f"{w}x{h}+{pos_x}+{pos_y}")

        # Contenu : Pourcentage en gros néon cyan
        self.mini_pct_label = tk.Label(self.mini_window, text=f"{self.current_percent}%",
                                       font=("Consolas", 11, "bold"),
                                       fg=NEON, bg=BG)
        self.mini_pct_label.pack(expand=True)

        # Label d'information au survol
        self.mini_tooltip = tk.Label(self.mini_window, text="Clic pour restaurer",
                                     font=("Consolas", 6), fg=GRAY, bg=BG)
        self.mini_tooltip.pack(side=tk.BOTTOM, pady=(0, 2))

        # Événement clic pour restaurer la fenêtre normale
        self.mini_window.bind("<Button-1>", lambda e: self.switch_to_normal())
        self.mini_pct_label.bind("<Button-1>", lambda e: self.switch_to_normal())

    def switch_to_normal(self):
        """Restaure la fenêtre principale normale."""
        if not self.mini_mode:
            return
        self.mini_mode = False
        if self.mini_window:
            self.mini_window.destroy()
            self.mini_window = None

        self.root.deiconify()  # Réaffiche la grande fenêtre
        self.root.geometry(f"{self.normal_w}x{self.normal_h}+{self.normal_x}+{self.normal_y}")
        self.root.attributes("-topmost", True)  # S'assurer qu'elle revient devant

    # ─────────────────────────────────────────────────────────
    #  UPDATE PROGRESS
    # ─────────────────────────────────────────────────────────
    def update_progress(self, stage, percent, info=""):
        self.current_percent = percent
        self.current_stage = stage

        def _update():
            # Mettre à jour les labels de la fenêtre normale
            filled = int(percent / 2.5)
            bar = "=" * max(0, filled - 1) + (">" if filled > 0 else "")
            bar = bar.ljust(40, ".")
            self.progress_label.config(text=f".: [{bar}]  {percent:3d}%")
            self.status_label.config(text=f"🔄  {stage}")
            self.info_label.config(text=info or "Traitement des données...")

            # Si on est en mode mini widget, mettre à jour la bulle
            if self.mini_mode and self.mini_window:
                self.mini_pct_label.config(text=f"{percent}%")

            log_line = f"[{time.strftime('%H:%M:%S')}] [{percent:3d}%] {stage} — {info}"
            self.log_history.append(log_line)

        self.root.after(0, _update)

    # ─────────────────────────────────────────────────────────
    #  ERREUR + COUNTDOWN
    # ─────────────────────────────────────────────────────────
    def start_crash_countdown(self, seconds=30):
        def _tick(rem):
            if rem > 0:
                self.error_title.config(text=f"❌  ERREUR — AUTO-DESTRUCTION DANS {rem}s")
                self.root.after(1000, lambda: _tick(rem - 1))
            else:
                self.error_title.config(text="💥  SUPPRESSION EN COURS...")
        _tick(seconds)

    def show_error(self, err_msg, is_antivirus=False):
        def _show():
            # Si on était en mode réduit, on restaure pour montrer l'erreur
            if self.mini_mode:
                self.switch_to_normal()

            self.error_frame.pack(fill=tk.X, pady=10)
            if is_antivirus:
                self.error_title.config(
                    text="⚠  BLOCAGE ANTIVIRUS — AUTO-DESTRUCTION 30s")
                self.error_msg.config(
                    text="Un antivirus (Windows Defender, SmartScreen ou tiers) bloque l'accès aux télémétries système.\n"
                         "👉  Désactiver l'antivirus temporairement puis relancer le scanner.")
            else:
                self.error_title.config(
                    text="❌  ERREUR DE SCAN — AUTO-DESTRUCTION 30s")
                self.error_msg.config(
                    text=f"Erreur : {err_msg}")

            self.start_crash_countdown(30)
            if self.on_crash_callback:
                self.on_crash_callback()

        self.root.after(0, _show)

    # ─────────────────────────────────────────────────────────
    #  SCAN THREAD
    # ─────────────────────────────────────────────────────────
    def start_scan_thread(self):
        def _worker():
            try:
                self.scan_runner_callback(self.update_progress)
                self._scan_done = True
                # Si on était réduit, on s'assure d'avoir détruit la bulle avant de fermer
                if self.mini_mode:
                    self.root.after(0, self.switch_to_normal)
                self.root.after(1000, self.on_complete_callback)
            except Exception as e:
                err_str = str(e)
                tb_str  = traceback.format_exc()
                self.log_history.append(f"\nCRASH:\n{tb_str}")
                is_av = any(k in err_str.lower() for k in
                            ["permission", "access denied", "blocked",
                             "antivirus", "unauthorized"])
                # S'assurer de restaurer la fenêtre principale pour montrer le crash
                if self.mini_mode:
                    self.root.after(0, self.switch_to_normal)
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
