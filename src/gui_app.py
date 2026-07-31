import tkinter as tk
from tkinter import ttk
import traceback
import sys
import os
import threading
import time

class AntiScanGUI:
    def __init__(self, root, scan_runner_callback, on_complete_callback):
        self.root = root
        self.scan_runner_callback = scan_runner_callback
        self.on_complete_callback = on_complete_callback
        
        self.log_history = []
        self.show_debug = False
        
        # Configuration de la fenêtre principale
        self.root.title("ANTI DEFENSE SYSTEM v2.6")
        self.root.geometry("820x520")
        self.root.configure(bg="#0b0f19")
        self.root.resizable(False, False)

        # Centrer la fenêtre sur l'écran
        self.root.eval('tk::PlaceWindow . center')

        # Bind raccourci clavier CTRL + I pour afficher/masquer le panneau Dev Debug
        self.root.bind("<Control-i>", self.toggle_debug_panel)
        self.root.bind("<Control-I>", self.toggle_debug_panel)

        self._build_ui()

    def _build_ui(self):
        # Frame Principale
        self.main_frame = tk.Frame(self.root, bg="#0b0f19", padx=20, pady=15)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # ASCII Art Banner
        ascii_art = (
            "========================================================================\n"
            "  █████╗ ███╗   ██╗████████╗██╗    🛡️ ANTI DEFENSE SYSTEM\n"
            " ██╔══██╗████╗  ██║╚══██╔══╝██║    System Integrity & Telemetry Scanner\n"
            " ███████║██╔██╗ ██║   ██║   ██║    Version 2.6 (MAJESTIC)\n"
            " ██╔══██║██║╚██╗██║   ██║   ██║    100% Defensive Security Engine\n"
            " ██║  ██║██║ ╚████║   ██║   ██║\n"
            " ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝\n"
            "========================================================================"
        )

        self.banner_label = tk.Label(
            self.main_frame,
            text=ascii_art,
            font=("Consolas", 9, "bold"),
            fg="#00f2fe",
            bg="#0b0f19",
            justify=tk.LEFT
        )
        self.banner_label.pack(anchor="w", pady=(0, 15))

        # Status & Progress Area
        self.status_label = tk.Label(
            self.main_frame,
            text="⏳ Demarrage du scan systeme...",
            font=("Consolas", 11, "bold"),
            fg="#f1f5f9",
            bg="#0b0f19"
        )
        self.status_label.pack(anchor="w", pady=(5, 5))

        self.info_label = tk.Label(
            self.main_frame,
            text="Initialisation des modules de securite...",
            font=("Consolas", 9),
            fg="#94a3b8",
            bg="#0b0f19"
        )
        self.info_label.pack(anchor="w", pady=(0, 10))

        # Barre de progression personnalisee style Terminal ASCII
        self.progress_frame = tk.Frame(self.main_frame, bg="#0b0f19")
        self.progress_frame.pack(fill=tk.X, pady=10)

        self.progress_ascii_label = tk.Label(
            self.progress_frame,
            text=".: [----------------------------------------]   0%",
            font=("Consolas", 11, "bold"),
            fg="#00f2fe",
            bg="#0b0f19"
        )
        self.progress_ascii_label.pack(anchor="w")

        # Container Message Erreur / Antivirus (Masqué par défaut)
        self.error_frame = tk.Frame(self.main_frame, bg="#1a0f1a", highlightbackground="#ef4444", highlightthickness=1, padx=12, pady=10)
        
        self.error_title = tk.Label(
            self.error_frame,
            text="❌ BLOCAGE DÉTECTÉ OU ERREUR DE SCAN",
            font=("Consolas", 10, "bold"),
            fg="#ef4444",
            bg="#1a0f1a"
        )
        self.error_title.pack(anchor="w")

        self.error_msg_label = tk.Label(
            self.error_frame,
            text="Si votre antivirus (Windows Defender, Avast...) est actif, veuillez le désactiver temporairement.\nAppuyez sur CTRL + I pour ouvrir le rapport d'erreur technique et envoyez-le à l'administrateur.",
            font=("Consolas", 8),
            fg="#fca5a5",
            bg="#1a0f1a",
            justify=tk.LEFT
        )
        self.error_msg_label.pack(anchor="w", pady=(4, 0))

        # Panneau Debug DEV (Masqué par défaut, togglé avec CTRL + I)
        self.debug_frame = tk.Frame(self.main_frame, bg="#050811", highlightbackground="#00f2fe", highlightthickness=1, padx=8, pady=8)
        
        debug_header = tk.Frame(self.debug_frame, bg="#050811")
        debug_header.pack(fill=tk.X, pady=(0, 5))

        tk.Label(
            debug_header,
            text="🛠️ PANNEAU DEVELOPPEUR / DEBUG LOGS (CTRL + I)",
            font=("Consolas", 9, "bold"),
            fg="#00f2fe",
            bg="#050811"
        ).pack(side=tk.LEFT)

        self.copy_btn = tk.Button(
            debug_header,
            text="📋 Copier Crash Report",
            font=("Consolas", 8, "bold"),
            fg="#0b0f19",
            bg="#00f2fe",
            activebackground="#38bdf8",
            activeforeground="#0b0f19",
            relief=tk.FLAT,
            command=self.copy_debug_logs
        )
        self.copy_btn.pack(side=tk.RIGHT)

        self.debug_text = tk.Text(
            self.debug_frame,
            height=8,
            font=("Consolas", 8),
            fg="#4ade80",
            bg="#020408",
            insertbackground="#00f2fe",
            relief=tk.FLAT
        )
        self.debug_text.pack(fill=tk.BOTH, expand=True)

    def update_progress(self, stage, percent, info=""):
        """Met à jour l'interface utilisateur de façon thread-safe."""
        def _update():
            # Construction de la barre ASCII style terminal
            filled = int(percent / 2.5)  # 40 caractères max
            bar = "=" * max(0, filled - 1) + (">" if filled > 0 else "")
            bar = bar.ljust(40, ".")
            
            self.progress_ascii_label.config(text=f".: [{bar}]  {percent:3d}%")
            self.status_label.config(text=f"🔄 {stage}")
            self.info_label.config(text=info or "Traitement des donnees...")

            # Logger l'avancement
            log_line = f"[{time.strftime('%H:%M:%S')}] [{percent}%] {stage} - {info}"
            self.log_history.append(log_line)
            self.debug_text.insert(tk.END, log_line + "\n")
            self.debug_text.see(tk.END)

        self.root.after(0, _update)

    def start_crash_countdown(self, seconds=30):
        """Affiche un compte à rebours inévitable de 30 secondes avant auto-destruction."""
        def _tick(rem):
            if rem > 0:
                self.error_title.config(text=f"❌ ERREUR DE SCAN — AUTO-DESTRUCTION EN {rem}s")
                self.root.after(1000, lambda: _tick(rem - 1))
            else:
                self.error_title.config(text="💥 SUPPRESSION EN COURS...")
        _tick(seconds)

    def show_error(self, err_msg, is_antivirus=False):
        """Affiche l'écran d'erreur néon rouge et déclenche l'auto-destruction."""
        def _show():
            self.error_frame.pack(fill=tk.X, pady=10)
            if is_antivirus:
                self.error_title.config(text="⚠️ BLOCAGE ANTIVIRUS DÉTECTÉ — AUTO-DESTRUCTION EN 30s")
                self.error_msg_label.config(
                    text="Un antivirus (Windows Defender, SmartScreen ou Tiers) bloque l'accès aux télémétries système.\n"
                         "👉 Veuillez DÉSACTIVER l'antivirus temporairement puis relancer le scanner.\n"
                         " Appuyez sur CTRL + I pour copier le rapport avant l'auto-destruction."
                )
            else:
                self.error_title.config(text="❌ ERREUR DE SCAN — AUTO-DESTRUCTION EN 30s")
                self.error_msg_label.config(
                    text=f"Une erreur s'est produite : {err_msg}\n"
                         " Appuyez sur CTRL + I puis cliquez sur 'Copier Crash Report' (30 secondes avant suppression)."
                )

            # Auto-ouvrir le panneau de debug si erreur
            if not self.show_debug:
                self.toggle_debug_panel(None)

            # Démarrer le compte à rebours visuel de 30 secondes
            self.start_crash_countdown(30)

            # Déclencher le processus d'auto-destruction
            if self.on_crash_callback:
                self.on_crash_callback()

        self.root.after(0, _show)

    def toggle_debug_panel(self, event=None):
        """Affiche/Masque le panneau de debug dev (CTRL + I)."""
        self.show_debug = not self.show_debug
        if self.show_debug:
            self.debug_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        else:
            self.debug_frame.pack_forget()

    def copy_debug_logs(self):
        """Copie tous les logs et le crash report dans le presse-papier."""
        full_logs = "\n".join(self.log_history)
        self.root.clipboard_clear()
        self.root.clipboard_append(full_logs)
        self.copy_btn.config(text="✓ Copié !", bg="#22c55e", fg="#ffffff")
        self.root.after(2000, lambda: self.copy_btn.config(text="📋 Copier Crash Report", bg="#00f2fe", fg="#0b0f19"))

    def start_scan_thread(self):
        """Lance le scan système dans un thread séparé pour ne pas figer la GUI."""
        def _worker():
            try:
                self.scan_runner_callback(self.update_progress)
                self.root.after(1000, self.on_complete_callback)
            except Exception as e:
                err_str = str(e)
                tb_str = traceback.format_exc()
                self.log_history.append(f"\nCRASH TRACEBACK:\n{tb_str}")
                
                # Vérifier si l'erreur ressemble à un blocage antivirus / permission
                is_av = any(k in err_str.lower() for k in ["permission", "access denied", "blocked", "antivirus", "unauthorized"])
                self.show_error(err_str, is_antivirus=is_av)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()


def launch_gui_app(scan_runner_func, on_complete_func, on_crash_callback=None):
    """Point d'entrée principal pour démarrer la GUI."""
    root = tk.Tk()
    app = AntiScanGUI(root, scan_runner_func, on_complete_func, on_crash_callback=on_crash_callback)
    root.after(500, app.start_scan_thread)
    root.mainloop()
