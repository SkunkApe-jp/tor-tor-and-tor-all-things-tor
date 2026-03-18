#!/usr/bin/env python3
"""
Modern Windows 10 Style Tkinter GUI for running Python scripts in the current directory
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import os
import sys
import re
from pathlib import Path
from urllib.parse import urlparse


# =========================================================
# TARGETS.YAML FILTERING LOGIC (Run before any script)
# =========================================================

TARGETS_FILE = Path(__file__).parent.parent / "config" / "targets.yaml"


def is_root_onion_url(url: str) -> bool:
    """Check if URL is a root onion URL (no sub-path)."""
    try:
        parsed = urlparse(url)
        return parsed.path in ['', '/']
    except:
        return False


def filter_targets_yaml() -> tuple[int, int, list[str], list[str]]:
    """
    Filter targets.yaml to keep only root URLs.
    Returns: (total, kept_count, kept_urls, removed_urls)
    """
    if not TARGETS_FILE.exists():
        return 0, 0, [], []
    
    # Read targets
    urls = []
    with open(TARGETS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('urls:'):
                url = stripped.lstrip('- ').strip()
                if url:
                    urls.append(url)
    
    # Categorize
    root_urls = [u for u in urls if is_root_onion_url(u)]
    subpath_urls = [u for u in urls if u not in root_urls]
    
    # Write back if there were sub-paths
    if subpath_urls:
        content = "urls:\n"
        for url in root_urls:
            content += f"  - {url}\n"
        TARGETS_FILE.write_text(content, encoding='utf-8')
    
    return len(urls), len(root_urls), root_urls, subpath_urls


def check_and_filter_targets() -> bool:
    """Check targets.yaml and filter if needed. Returns True if OK to proceed."""
    if not TARGETS_FILE.exists():
        messagebox.showwarning("Targets Not Found", f"{TARGETS_FILE}\n\nPlease create targets.yaml first!")
        return False
    
    total, kept, kept_urls, removed = filter_targets_yaml()
    
    if total == 0:
        messagebox.showwarning("Empty Targets", "No URLs found in targets.yaml!")
        return False
    
    if removed:
        msg = f"Filtered {len(removed)} sub-path URL(s):\n\n"
        for url in removed:
            msg += f"  ❌ {url}\n"
        msg += f"\n✅ Kept {kept} root URL(s)\n\nTargets updated automatically!"
        messagebox.showinfo("Targets Filtered", msg)
    
    return True


class ModernScriptRunnerGUI:
    def __init__(self, root):
        # Define Windows 10 style colors
        self.colors = {
            'bg': '#F3F3F3',           # Light gray background
            'header_bg': '#FFFFFF',    # White header
            'accent': '#0078D7',       # Windows blue
            'button_normal': '#FFFFFF',
            'button_hover': '#E5F3FF',
            'button_pressed': '#CCE8FF',
            'text_primary': '#323130',
            'text_secondary': '#605E5C',
            'border': '#E1DFDD',
            'output_bg': '#FFFFFF',
            'output_text': '#323130'
        }

        self.root = root
        self.root.title("Tor Scraper - Script Runner")
        self.root.geometry("900x700")
        self.root.configure(bg=self.colors['bg'])

        # Get the current directory
        self.script_dir = Path(__file__).parent

        # Find all Python scripts in the directory
        self.python_scripts = [f for f in self.script_dir.glob("*.py") if f.name not in ["script_runner_gui.py", "filter_targets.py"]]

        # Create GUI elements
        self.create_widgets()
    
    def create_widgets(self):
        # Header frame
        header_frame = tk.Frame(self.root, bg=self.colors['header_bg'], height=60)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Header label
        header_label = tk.Label(
            header_frame, 
            text="Tor Scraper Scripts", 
            font=("Segoe UI", 16, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['header_bg']
        )
        header_label.pack(side=tk.LEFT, padx=20, pady=15)
        
        # Main content frame
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Left panel for script buttons
        left_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        left_frame.grid(row=0, column=0, rowspan=2, sticky='ns', padx=(0, 15))

        # Filter Targets button (top action button)
        filter_btn = ModernButton(
            left_frame,
            text="🔍 Filter Targets",
            command=self.filter_targets_manual,
            width=250,
            height=45,
            colors=self.colors
        )
        filter_btn.pack(pady=(0, 15), fill=tk.X)

        # Scripts label
        scripts_label = tk.Label(
            left_frame,
            text="Scripts",
            font=("Segoe UI", 12, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg']
        )
        scripts_label.pack(anchor='w', pady=(0, 10))
        
        # Scrollable frame for script buttons
        canvas = tk.Canvas(left_frame, highlightthickness=0, bg=self.colors['bg'])
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind("<MouseWheel>", _on_mousewheel)
        
        # Create buttons for each script with Windows 10 style (without arrow heads)
        for i, script in enumerate(sorted(self.python_scripts)):
            btn = ModernButton(
                scrollable_frame,
                text=script.name,
                command=lambda s=script: self.run_script(s),
                width=250,
                height=40,
                colors=self.colors
            )
            btn.pack(pady=3, fill=tk.X)
        
        # Add a frame to hold the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Output section
        output_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        output_frame.grid(row=0, column=1, sticky='nsew', padx=(15, 0))
        
        # Output label
        output_label = tk.Label(
            output_frame,
            text="Output",
            font=("Segoe UI", 12, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['bg']
        )
        output_label.pack(anchor='w', pady=(0, 10))
        
        # Output text area with custom styling
        self.output_text = CustomScrolledText(
            output_frame,
            height=20,
            width=70,
            bg=self.colors['output_bg'],
            fg=self.colors['output_text'],
            insertbackground=self.colors['text_primary'],
            selectbackground=self.colors['accent'],
            selectforeground='#FFFFFF',
            relief=tk.FLAT,
            borderwidth=1,
            font=("Consolas", 10)
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons frame
        controls_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        controls_frame.grid(row=1, column=1, sticky='ew', padx=(15, 0), pady=(15, 0))
        
        # Clear button
        self.clear_btn = ModernButton(
            controls_frame,
            text="Clear Output",
            command=self.clear_output,
            width=120,
            height=35,
            colors=self.colors
        )
        self.clear_btn.pack(side=tk.RIGHT)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            bd=1,
            relief=tk.FLAT,
            anchor=tk.W,
            font=("Segoe UI", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['header_bg']
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def run_script(self, script_path):
        """Run a script in a separate thread"""
        def run_in_thread():
            try:
                self.status_var.set(f"Running {script_path.name}...")

                # Show which script is running
                self.append_output(f"\n>>> Running {script_path.name} <<<\n")

                # Prepare the command to run the script with the current Python interpreter
                cmd = [sys.executable, str(script_path)]
                
                # Special handling for minimal_visualize_onions.py - add "all" argument
                if script_path.name == "minimal_visualize_onions.py":
                    cmd.append("all")

                # Run the script with the current environment
                result = subprocess.run(
                    cmd,
                    cwd=self.script_dir,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                # Display output
                if result.stdout:
                    self.append_output(result.stdout)
                if result.stderr:
                    self.append_output(f"[ERROR]\n{result.stderr}")
                
                self.append_output(f"\n>>> Finished {script_path.name} (Code: {result.returncode}) <<<\n")
                self.status_var.set(f"Completed: {script_path.name} (Code: {result.returncode})")
                
            except subprocess.TimeoutExpired:
                error_msg = f"\n>>> TIMEOUT: {script_path.name} took too long <<<\n"
                self.append_output(error_msg)
                self.status_var.set(f"Timeout: {script_path.name}")
            except Exception as e:
                error_msg = f"\n>>> ERROR running {script_path.name}: {str(e)} <<<\n"
                self.append_output(error_msg)
                self.status_var.set(f"Error: {script_path.name}")

        # Run in a separate thread to prevent GUI from freezing
        thread = threading.Thread(target=run_in_thread)
        thread.daemon = True
        thread.start()

    def append_output(self, text):
        """Append text to the output area in the main thread"""
        def update():
            self.output_text.configure(state='normal')
            self.output_text.insert(tk.END, text)
            self.output_text.see(tk.END)
            self.output_text.configure(state='disabled')
            self.root.update_idletasks()

        # Schedule the update in the main thread
        self.root.after(0, update)

    def clear_output(self):
        """Clear the output text area"""
        self.output_text.configure(state='normal')
        self.output_text.delete(1.0, tk.END)
        self.output_text.configure(state='disabled')
        self.status_var.set("Output cleared")

    def filter_targets_manual(self):
        """Manually filter targets.yaml and show results"""
        def do_filter():
            total, kept, kept_urls, removed = filter_targets_yaml()
            
            if total == 0:
                self.append_output("\n>>> No targets found in targets.yaml <<<\n")
                self.status_var.set("No targets found")
                return
            
            msg = f"\n>>> TARGETS FILTER RESULTS <<<\n"
            msg += f"Total URLs:     {total}\n"
            msg += f"Root URLs:      {kept} (KEPT)\n"
            msg += f"Sub-path URLs:  {len(removed)} (REMOVED)\n"
            
            if removed:
                msg += f"\nRemoved:\n"
                for url in removed:
                    msg += f"  ❌ {url}\n"
            
            if kept_urls:
                msg += f"\nKept:\n"
                for url in kept_urls:
                    msg += f"  ✅ {url}\n"
            
            msg += f"\n>>> Filter complete! <<<\n"
            self.append_output(msg)
            self.status_var.set(f"Filtered: {kept}/{total} URLs kept")
        
        thread = threading.Thread(target=do_filter)
        thread.daemon = True
        thread.start()


class ModernButton(tk.Label):
    def __init__(self, parent, text, command, width, height, colors, **kwargs):
        self.command = command
        self.colors = colors
        self.width = width
        self.height = height
        
        super().__init__(
            parent,
            text=text,
            font=("Segoe UI", 10),
            fg=colors['text_primary'],
            bg=colors['button_normal'],
            relief=tk.FLAT,
            borderwidth=1,
            highlightthickness=0,
            cursor="hand2"
        )
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        
        # Calculate padding to achieve desired dimensions
        self.configure(width=width//8)  # Approximate character width
        
    def on_enter(self, event):
        self.configure(bg=self.colors['button_hover'])
        
    def on_leave(self, event):
        self.configure(bg=self.colors['button_normal'])
        
    def on_press(self, event):
        self.configure(bg=self.colors['button_pressed'])
        
    def on_release(self, event):
        self.configure(bg=self.colors['button_hover'])
        if self.command:
            self.command()


class CustomScrolledText(scrolledtext.ScrolledText):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # Configure the text widget to be read-only by default
        self.configure(state='disabled')


def main():
    root = tk.Tk()
    root.tk_setPalette(background='#F3F3F3', foreground='#323130')
    app = ModernScriptRunnerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()