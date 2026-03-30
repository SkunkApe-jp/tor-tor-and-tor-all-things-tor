#!/usr/bin/env python3
"""
loop_controller.py
==================
Infinite loop controller for the unified scraper ecosystem.

Cycle:
    1. Run unified_scraper.exe  (scraping phase)
    2. Run extract_unique_links.py --append-to-targets  (discovery phase)
    3. Repeat from 1 — forever, until you click Stop.

Usage:
    python loop_controller.py
"""

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import font as tkfont
from tkinter import scrolledtext, ttk

# ---------------------------------------------------------------------------
# Default paths — edit here or change inside the GUI
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.resolve()
SCRAPER_EXE = str(ROOT / "bin" / "unified_scraper.exe")
EXTRACTOR_PY = str(ROOT / "extract_unique_links.py")
TARGETS_YAML = str(ROOT / "targets.yaml")
SCRAPED_DATA = str(ROOT / "scraped_data")
OUTPUT_FILE = str(ROOT / "new_links.txt")
SCRAPER_FLAGS = "--fast"  # default flags for the scraper

# ---------------------------------------------------------------------------
# Colour palette (dark theme)
# ---------------------------------------------------------------------------
C = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "border": "#30363d",
    "accent": "#58a6ff",
    "accent2": "#3fb950",  # green – scraping phase
    "accent3": "#f78166",  # red   – stopped / error
    "accent4": "#d29922",  # amber – extracting phase
    "text": "#e6edf3",
    "text_dim": "#8b949e",
    "log_bg": "#0d1117",
    "log_sel": "#1f2937",
    "scraping": "#3fb950",
    "extracting": "#d29922",
    "idle": "#58a6ff",
    "stopped": "#f78166",
    "success": "#3fb950",
    "warn": "#d29922",
    "error": "#f78166",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------


class LoopController(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Scraper Loop Controller")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self.minsize(820, 560)

        # State
        self._running = False
        self._stopped = False  # user-requested stop
        self._proc = None  # current subprocess
        self._thread = None
        self._log_q = queue.Queue()
        self._cycle = 0
        self._phase = "idle"  # idle | scraping | extracting | stopped

        self._build_ui()
        self._poll_log()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.geometry("980x680")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Title bar row ──────────────────────────────────────────────
        hdr = tk.Frame(self, bg=C["surface"], pady=10)
        hdr.pack(fill="x", padx=0, pady=0)

        tk.Label(
            hdr,
            text="⟳  Scraper Loop Controller",
            bg=C["surface"],
            fg=C["accent"],
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left", padx=18)

        self._cycle_lbl = tk.Label(
            hdr,
            text="Cycle: 0",
            bg=C["surface"],
            fg=C["text_dim"],
            font=("Segoe UI", 11),
        )
        self._cycle_lbl.pack(side="right", padx=18)

        self._phase_lbl = tk.Label(
            hdr,
            text="● IDLE",
            bg=C["surface"],
            fg=C["idle"],
            font=("Segoe UI", 11, "bold"),
        )
        self._phase_lbl.pack(side="right", padx=6)

        # ── Config panel ───────────────────────────────────────────────
        cfg_outer = tk.Frame(self, bg=C["border"], pady=1)
        cfg_outer.pack(fill="x", padx=0)
        cfg = tk.Frame(cfg_outer, bg=C["surface"], pady=10, padx=12)
        cfg.pack(fill="x")

        def row(label, default, col=0):
            tk.Label(
                cfg,
                text=label,
                bg=C["surface"],
                fg=C["text_dim"],
                font=("Segoe UI", 9),
                anchor="w",
            ).grid(row=col, column=0, sticky="w", padx=(0, 8), pady=2)
            var = tk.StringVar(value=default)
            e = tk.Entry(
                cfg,
                textvariable=var,
                bg=C["bg"],
                fg=C["text"],
                insertbackground=C["text"],
                relief="flat",
                font=("Consolas", 9),
                width=72,
            )
            e.grid(row=col, column=1, sticky="ew", pady=2)
            return var

        cfg.columnconfigure(1, weight=1)

        self._v_scraper = row("Scraper exe", SCRAPER_EXE, 0)
        self._v_flags = row("Scraper flags", SCRAPER_FLAGS, 1)
        self._v_extractor = row("Extractor script", EXTRACTOR_PY, 2)
        self._v_targets = row("targets.yaml", TARGETS_YAML, 3)
        self._v_links_dir = row("Links dir (scan)", SCRAPED_DATA, 4)
        self._v_output = row("New links output", OUTPUT_FILE, 5)

        # ── Button row ─────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=C["bg"], pady=8)
        btn_row.pack(fill="x", padx=14)

        btn_style = dict(
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            padx=22,
            pady=6,
            cursor="hand2",
        )

        self._btn_start = tk.Button(
            btn_row,
            text="▶  Start Loop",
            bg=C["accent2"],
            fg="#0d1117",
            activebackground="#4ec861",
            activeforeground="#0d1117",
            command=self._start_loop,
            **btn_style,
        )
        self._btn_start.pack(side="left", padx=(0, 8))

        self._btn_stop = tk.Button(
            btn_row,
            text="■  Stop after cycle",
            bg=C["surface"],
            fg=C["text_dim"],
            activebackground=C["border"],
            activeforeground=C["text"],
            command=self._request_stop,
            state="disabled",
            **btn_style,
        )
        self._btn_stop.pack(side="left", padx=(0, 8))

        self._btn_kill = tk.Button(
            btn_row,
            text="✕  Kill Now",
            bg=C["accent3"],
            fg="#0d1117",
            activebackground="#ff7070",
            activeforeground="#0d1117",
            command=self._kill_now,
            state="disabled",
            **btn_style,
        )
        self._btn_kill.pack(side="left", padx=(0, 8))

        self._btn_clear = tk.Button(
            btn_row,
            text="⌫  Clear Log",
            bg=C["surface"],
            fg=C["text_dim"],
            activebackground=C["border"],
            activeforeground=C["text"],
            command=self._clear_log,
            **btn_style,
        )
        self._btn_clear.pack(side="right")

        # ── Progress bar ───────────────────────────────────────────────
        pb_frame = tk.Frame(self, bg=C["bg"])
        pb_frame.pack(fill="x", padx=14, pady=(0, 4))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Loop.Horizontal.TProgressbar",
            troughcolor=C["surface"],
            background=C["accent2"],
            bordercolor=C["border"],
            lightcolor=C["accent2"],
            darkcolor=C["accent2"],
        )
        self._progress = ttk.Progressbar(
            pb_frame,
            style="Loop.Horizontal.TProgressbar",
            mode="indeterminate",
            length=200,
        )
        self._progress.pack(fill="x")

        # ── Log area ───────────────────────────────────────────────────
        log_frame = tk.Frame(self, bg=C["border"], pady=1)
        log_frame.pack(fill="both", expand=True, padx=0, pady=0)

        log_inner = tk.Frame(log_frame, bg=C["log_bg"])
        log_inner.pack(fill="both", expand=True)

        mono = tkfont.Font(family="Consolas", size=9)

        self._log = scrolledtext.ScrolledText(
            log_inner,
            bg=C["log_bg"],
            fg=C["text"],
            font=mono,
            relief="flat",
            bd=0,
            selectbackground=C["log_sel"],
            wrap="none",
            state="disabled",
        )
        self._log.pack(fill="both", expand=True, padx=6, pady=4)

        # Colour tags
        self._log.tag_config("ts", foreground=C["text_dim"])
        self._log.tag_config("phase", foreground=C["accent"], font=(mono, 9, "bold"))
        self._log.tag_config("scraping", foreground=C["scraping"])
        self._log.tag_config("extracting", foreground=C["extracting"])
        self._log.tag_config("success", foreground=C["success"])
        self._log.tag_config("warn", foreground=C["warn"])
        self._log.tag_config("error", foreground=C["error"])
        self._log.tag_config("dim", foreground=C["text_dim"])
        self._log.tag_config("normal", foreground=C["text"])

        # ── Status bar at bottom ───────────────────────────────────────
        sb = tk.Frame(self, bg=C["surface"], pady=3)
        sb.pack(fill="x", side="bottom")
        self._status_lbl = tk.Label(
            sb,
            text="Ready. Click ▶ Start Loop to begin.",
            bg=C["surface"],
            fg=C["text_dim"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        self._status_lbl.pack(side="left", padx=10)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_write(self, text: str, tag: str = "normal"):
        """Queue a log message (thread-safe)."""
        self._log_q.put((text, tag))

    def _poll_log(self):
        """Drain the log queue into the Text widget — runs on main thread."""
        try:
            while True:
                text, tag = self._log_q.get_nowait()
                self._log.configure(state="normal")
                self._log.insert("end", text, tag)
                self._log.see("end")
                self._log.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(60, self._poll_log)

    def _log_line(self, msg: str, tag: str = "normal"):
        self._log_write(f"[{ts()}] ", "ts")
        self._log_write(msg + "\n", tag)

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    # ------------------------------------------------------------------
    # Phase / UI state helpers
    # ------------------------------------------------------------------

    def _set_phase(self, phase: str, label: str, colour: str):
        self._phase = phase
        self._phase_lbl.configure(text=f"● {label}", fg=colour)
        self._status_lbl.configure(text=label)

    def _set_buttons(self, running: bool):
        if running:
            self._btn_start.configure(
                state="disabled", bg=C["border"], fg=C["text_dim"]
            )
            self._btn_stop.configure(state="normal", bg=C["accent3"], fg="#0d1117")
            self._btn_kill.configure(state="normal")
            self._progress.start(12)
        else:
            self._btn_start.configure(state="normal", bg=C["accent2"], fg="#0d1117")
            self._btn_stop.configure(
                state="disabled", bg=C["surface"], fg=C["text_dim"]
            )
            self._btn_kill.configure(state="disabled")
            self._progress.stop()

    # ------------------------------------------------------------------
    # Loop control
    # ------------------------------------------------------------------

    def _start_loop(self):
        if self._running:
            return
        self._running = True
        self._stopped = False
        self._set_buttons(True)
        self._set_phase("scraping", "STARTING…", C["idle"])
        self._log_line("━━━ Loop started ━━━", "phase")
        self._thread = threading.Thread(target=self._loop_worker, daemon=True)
        self._thread.start()

    def _request_stop(self):
        """Graceful stop: finish current cycle, then halt."""
        self._stopped = True
        self._btn_stop.configure(state="disabled", text="⏳ Stopping after cycle…")
        self._log_line(
            "Stop requested — will halt after current cycle finishes.", "warn"
        )

    def _kill_now(self):
        """Immediately kill the running subprocess and stop the loop."""
        self._stopped = True
        self._running = False
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
                self._log_line("Process killed by user.", "error")
            except Exception:
                pass
        self._on_loop_ended(killed=True)

    def _on_loop_ended(self, killed: bool = False):
        """Called from main thread when the loop exits."""
        self._running = False
        self._set_buttons(False)
        if killed:
            self._set_phase("stopped", "STOPPED (killed)", C["stopped"])
            self._log_line("━━━ Loop killed. ━━━", "error")
        else:
            self._set_phase("idle", "IDLE", C["idle"])
            self._log_line("━━━ Loop ended gracefully. ━━━", "success")
        self._btn_stop.configure(text="■  Stop after cycle")
        self._cycle_lbl.configure(text=f"Cycle: {self._cycle}")

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _loop_worker(self):
        """Runs in a background thread. Executes scraper → extractor forever."""
        while True:
            if self._stopped:
                break

            self._cycle += 1
            self.after(
                0, lambda c=self._cycle: self._cycle_lbl.configure(text=f"Cycle: {c}")
            )

            # ── Phase 1: Scraper ──────────────────────────────────────
            self.after(
                0,
                lambda: self._set_phase(
                    "scraping", f"SCRAPING  (cycle {self._cycle})", C["scraping"]
                ),
            )
            self._log_line(f"╔═ Cycle {self._cycle} — SCRAPING phase ═╗", "scraping")

            scraper_cmd = [
                self._v_scraper.get(),
                "--targets",
                str(ROOT / "targets.yaml"),
            ] + self._v_flags.get().split()
            rc = self._run_subprocess(scraper_cmd, phase_tag="scraping")
            if rc != 0:
                self._log_line(
                    f"Scraper exited with code {rc}. Continuing loop anyway.", "warn"
                )
            else:
                self._log_line("Scraper finished successfully.", "success")

            if self._stopped:
                break

            # ── Phase 2: Extractor ────────────────────────────────────
            self.after(
                0,
                lambda: self._set_phase(
                    "extracting", f"EXTRACTING  (cycle {self._cycle})", C["extracting"]
                ),
            )
            self._log_line(
                f"╠═ Cycle {self._cycle} — EXTRACTING phase ═╣", "extracting"
            )

            extractor_cmd = [
                sys.executable,
                self._v_extractor.get(),
                "--links-dir",
                self._v_links_dir.get(),
                "--targets",
                self._v_targets.get(),
                "--output",
                self._v_output.get(),
                "--resume-log",
                str(ROOT / "config" / "resume_log.txt"),
                "--append-to-targets",
                "--verbose",
            ]
            rc = self._run_subprocess(extractor_cmd, phase_tag="extracting")
            if rc != 0:
                self._log_line(f"Extractor exited with code {rc}.", "warn")
            else:
                self._log_line(
                    "Extraction complete — new links appended to targets.yaml.",
                    "success",
                )

            self._log_line(
                f"╚═ Cycle {self._cycle} complete. {'Stopping.' if self._stopped else 'Restarting scraper…'} ═╝",
                "success",
            )

            if self._stopped:
                break

            # Brief pause between cycles so the OS can breathe
            time.sleep(2)

        self.after(0, self._on_loop_ended)

    def _run_subprocess(self, cmd: list, phase_tag: str) -> int:
        """
        Run *cmd* as a subprocess, streaming stdout+stderr into the log.
        Returns the exit code (or -1 if killed).
        """
        self._log_write(f"  $ {' '.join(cmd)}\n", "dim")
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=str(ROOT),
            )
        except FileNotFoundError as exc:
            self._log_line(f"[ERROR] Could not launch: {exc}", "error")
            return -1
        except Exception as exc:
            self._log_line(f"[ERROR] Subprocess error: {exc}", "error")
            return -1

        # Stream output line by line
        for line in self._proc.stdout:
            line = line.rstrip("\n\r")
            if not line:
                continue
            # Colour-code common prefixes
            tag = phase_tag
            lower = line.lower()
            if any(k in lower for k in ("[error]", "[warn]", "error", "fail")):
                tag = "error"
            elif any(k in lower for k in ("[ok]", "[done]", "success", "complete")):
                tag = "success"
            elif any(k in lower for k in ("[info]", "[config]", "[stealth]")):
                tag = "dim"
            self._log_write(f"    {line}\n", tag)

        self._proc.wait()
        rc = self._proc.returncode if self._proc else -1
        self._proc = None
        return rc

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def _on_close(self):
        if self._running:
            self._kill_now()
            self.after(400, self.destroy)
        else:
            self.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = LoopController()
    app.mainloop()
