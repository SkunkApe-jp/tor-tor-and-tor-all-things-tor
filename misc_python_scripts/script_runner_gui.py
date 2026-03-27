#!/usr/bin/env python3
"""
Modern Windows 10 Style Tkinter GUI for running Python scripts in the current directory.
Optimized for Tor Scraper Ecosystem.
Now handles background visualization of all onions on startup.
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




class ModernScriptRunnerGUI:
    def __init__(self, root):
        # Define Windows 10 style colors (EXACTLY AS REQUESTED)
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
        self.root.title("Tor Scraper Ecosystem - Big Daddy Runner")
        self.root.geometry("1100x800")
        self.root.configure(bg=self.colors['bg'])

        # Get the current directory (now in misc_python_scripts/)
        self.script_dir = Path(__file__).parent

        # Find all Python scripts in the directory and subdirectories
        self.load_scripts()

        # Create GUI elements
        self.create_widgets()

        # Run minimal_visualize_onions.py all in the background
        self.start_background_visualization()
    
    def load_scripts(self):
        """Discover Python scripts in misc_python_scripts/, its subfolders, and the project root."""
        self.python_scripts = []
        
        # Current folder (misc_python_scripts)
        scripts = sorted(list(self.script_dir.glob("*.py")))
        
        # Filter out common utility or gui scripts
        exclude_names = ["script_runner_gui.py", "filter_targets.py", "__init__.py"]
        self.python_scripts = [f for f in scripts if f.name not in exclude_names]
        
        # Add scripts from specific relevant subfolders if they exist
        subfolders = ["diagramatic exploratory analysis", "main scripts", "onion finders"]
        for sub in subfolders:
            sub_path = self.script_dir / sub
            if sub_path.exists():
                sub_scripts = sorted(list(sub_path.glob("*.py")))
                self.python_scripts.extend(sub_scripts)
                
        # Add scripts from the project root (parent directory)
        root_dir = self.script_dir.parent
        root_scripts = sorted(list(root_dir.glob("*.py")))
        # Filter out scripts already handled or irrelevant
        root_exclude = ["mirror_discovery_engine.py", "scraped_onion_harvester.py", "visualize_now.py", "fast_onion_scrubber.py"]
        # Actually, let's keep the important ones
        self.python_scripts.extend([f for f in root_scripts if f.name in root_exclude])

    def start_background_visualization(self):
        """Run minimal_visualize_onions.py all in the background on startup."""
        viz_script = self.script_dir / "minimal_visualize_onions.py"
        if viz_script.exists():
            def run_viz():
                try:
                    self.status_var.set("Background Task: Running initial visualizations...")
                    # Using Popen for fire-and-forget background execution
                    subprocess.Popen(
                        [sys.executable, str(viz_script), "all"],
                        cwd=self.script_dir,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                    )
                except Exception as e:
                    print(f"Failed to start background visualization: {e}")

            viz_thread = threading.Thread(target=run_viz)
            viz_thread.daemon = True
            viz_thread.start()

    def create_widgets(self):
        # Header frame
        header_frame = tk.Frame(self.root, bg=self.colors['header_bg'], height=70)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Header label with subtle subtitle
        title_container = tk.Frame(header_frame, bg=self.colors['header_bg'])
        title_container.pack(side=tk.LEFT, padx=30, pady=10)
        
        header_label = tk.Label(
            title_container, 
            text="Tor Scraper Ecosystem", 
            font=("Segoe UI Variable Display", 18, "bold"),
            fg=self.colors['text_primary'],
            bg=self.colors['header_bg']
        )
        header_label.pack(anchor='w')
        
        subtitle_label = tk.Label(
            title_container, 
            text="Master Script Control Center", 
            font=("Segoe UI", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['header_bg']
        )
        subtitle_label.pack(anchor='w')
        
        # Main content split container
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Left sidebar for controls and scripts
        sidebar_frame = tk.Frame(main_container, bg=self.colors['bg'], width=320)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        sidebar_frame.pack_propagate(False)


        # Scripts Section
        scripts_label = tk.Label(
            sidebar_frame,
            text="SCRIPTS LIBRARY",
            font=("Segoe UI", 9, "bold"),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg']
        )
        scripts_label.pack(anchor='w', pady=(0, 10))
        
        # Search bar for scripts
        search_frame = tk.Frame(sidebar_frame, bg=self.colors['bg'])
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_scripts)
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 10),
            bg=self.colors['header_bg'],
            fg=self.colors['text_primary'],
            relief=tk.FLAT,
            borderwidth=1,
            highlightthickness=1,
            highlightcolor=self.colors['accent'],
            highlightbackground=self.colors['border']
        )
        search_entry.pack(fill=tk.X, ipady=5)
        search_entry.insert(0, "") # Placeholder behavior could be added
        
        # Scrollable frame for script buttons
        list_container = tk.Frame(sidebar_frame, bg=self.colors['bg'])
        list_container.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(list_container, highlightthickness=0, bg=self.colors['bg'])
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.colors['bg'])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Initial population of script list
        self.populate_script_list(self.python_scripts)
        
        # Right Output area
        content_frame = tk.Frame(main_container, bg=self.colors['bg'])
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Output title bar
        output_header = tk.Frame(content_frame, bg=self.colors['bg'])
        output_header.pack(fill=tk.X, pady=(0, 10))
        
        output_label = tk.Label(
            output_header,
            text="EXECUTION OUTPUT",
            font=("Segoe UI", 9, "bold"),
            fg=self.colors['text_secondary'],
            bg=self.colors['bg']
        )
        output_label.pack(side=tk.LEFT)
        
        # Clear button on the right
        self.clear_btn = ModernButton(
            output_header,
            text="Clear Log",
            command=self.clear_output,
            width=100,
            height=30,
            colors=self.colors
        )
        self.clear_btn.pack(side=tk.RIGHT)
        
        # Output text area with elevated look
        self.output_container = tk.Frame(
            content_frame, 
            bg=self.colors['header_bg'],
            relief=tk.FLAT,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self.colors['border']
        )
        self.output_container.pack(fill=tk.BOTH, expand=True)
        
        self.output_text = CustomScrolledText(
            self.output_container,
            height=20,
            width=70,
            bg=self.colors['output_bg'],
            fg=self.colors['output_text'],
            insertbackground=self.colors['text_primary'],
            selectbackground=self.colors['accent'],
            selectforeground='#FFFFFF',
            relief=tk.FLAT,
            borderwidth=0,
            font=("Consolas", 10),
            padx=15,
            pady=15
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar_frame = tk.Frame(self.root, bg=self.colors['header_bg'], height=30)
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        status_bar = tk.Label(
            status_bar_frame,
            textvariable=self.status_var,
            bd=0,
            anchor=tk.W,
            font=("Segoe UI", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['header_bg'],
            padx=20
        )
        status_bar.pack(side=tk.LEFT, fill=tk.BOTH)
        
        # Add clock/time to status bar
        self.update_time_label(status_bar_frame)

    def update_time_label(self, parent):
        import time
        self.time_label = tk.Label(
            parent,
            text=time.strftime("%H:%M:%S"),
            font=("Segoe UI", 9),
            fg=self.colors['text_secondary'],
            bg=self.colors['header_bg'],
            padx=20
        )
        self.time_label.pack(side=tk.RIGHT)
        
        def refresh():
            self.time_label.config(text=time.strftime("%H:%M:%S"))
            self.root.after(1000, refresh)
        
        refresh()

    def on_canvas_configure(self, event):
        """Update window width to match canvas."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def filter_scripts(self, *args):
        """Filter scripts based on search string."""
        search_query = self.search_var.get().lower()
        if not search_query:
            self.populate_script_list(self.python_scripts)
            return
            
        filtered = [s for s in self.python_scripts if search_query in s.name.lower()]
        self.populate_script_list(filtered)

    def populate_script_list(self, script_list):
        """Update the script button list."""
        # Clear existing buttons
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        if not script_list:
            lbl = tk.Label(
                self.scrollable_frame,
                text="No scripts found",
                font=("Segoe UI", 9, "italic"),
                fg=self.colors['text_secondary'],
                bg=self.colors['bg']
            )
            lbl.pack(pady=20)
            return

        for script in script_list:
            # Display name: strip directory if in subfolder
            display_name = script.name
            if script.parent != self.script_dir:
                display_name = f"[{script.parent.name}] {script.name}"
                
            btn = ModernButton(
                self.scrollable_frame,
                text=display_name,
                command=lambda s=script: self.run_script(s),
                width=280,
                height=38,
                colors=self.colors,
                is_script=True
            )
            btn.pack(pady=2, fill=tk.X)

    def run_script(self, script_path):
        """Run a script in a separate thread"""
        def run_in_thread():
            try:
                self.status_var.set(f"Executing {script_path.name}...")

                # Show which script is running
                header = f"\n{'='*60}\n"
                header += f" RUNNING: {script_path.name}\n"
                header += f" LOCATION: {script_path}\n"
                header += f"{'='*60}\n"
                self.append_output(header)

                # Prepare the command
                cmd = [sys.executable, str(script_path)]
                
                # Special handling for minimal_visualize_onions.py - add "all" argument
                if script_path.name == "minimal_visualize_onions.py":
                    cmd.append("all")

                # Run the script
                result = subprocess.run(
                    cmd,
                    cwd=script_path.parent, # Run in its own directory
                    capture_output=True,
                    text=True,
                    timeout=600 # 10 minute timeout for big scripts
                )
                
                # Display output
                if result.stdout:
                    self.append_output(result.stdout)
                if result.stderr:
                    self.append_output(f"\n[STDERR]\n{result.stderr}")
                
                footer = f"\n{'='*60}\n"
                footer += f" FINISHED: {script_path.name} (Return Code: {result.returncode})\n"
                footer += f"{'='*60}\n"
                self.append_output(footer)
                self.status_var.set(f"Finished: {script_path.name} ({result.returncode})")
                
            except subprocess.TimeoutExpired:
                self.append_output(f"\n[TIMEOUT] {script_path.name} exceeded 10 minute limit.\n")
                self.status_var.set(f"Timeout: {script_path.name}")
            except Exception as e:
                self.append_output(f"\n[SYSTEM ERROR] {str(e)}\n")
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
        self.status_var.set("Logs cleared")



class ModernButton(tk.Label):
    def __init__(self, parent, text, command, width, height, colors, is_primary=False, is_script=False, **kwargs):
        self.command = command
        self.colors = colors
        self.is_primary = is_primary
        self.is_script = is_script
        
        # Style based on priority
        fg_color = colors['text_primary']
        bg_color = colors['button_normal']
        
        if is_primary:
            fg_color = '#FFFFFF'
            bg_color = colors['accent']
        
        super().__init__(
            parent,
            text=text,
            font=("Segoe UI", 10 if not is_primary else 11, "bold" if is_primary else "normal"),
            fg=fg_color,
            bg=bg_color,
            relief=tk.FLAT,
            borderwidth=0,
            padx=15,
            pady=10,
            cursor="hand2",
            anchor="w" if is_script else "center"
        )
        
        # Add visual border for secondary buttons
        if not is_primary:
            self.configure(
                highlightthickness=1,
                highlightbackground=colors['border']
            )
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_press)
        self.bind("<ButtonRelease-1>", self.on_release)
        
    def on_enter(self, event):
        if self.is_primary:
            # Darker blue for hover on accent
            self.configure(bg='#0067B8')
        else:
            self.configure(bg=self.colors['button_hover'])
        
    def on_leave(self, event):
        if self.is_primary:
            self.configure(bg=self.colors['accent'])
        else:
            self.configure(bg=self.colors['button_normal'])
        
    def on_press(self, event):
        if self.is_primary:
            self.configure(bg='#005A9E')
        else:
            self.configure(bg=self.colors['button_pressed'])
        
    def on_release(self, event):
        self.on_enter(None) # Reset to hover state
        if self.command:
            self.command()


class CustomScrolledText(scrolledtext.ScrolledText):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(state='disabled')


def main():
    root = tk.Tk()
    # High DPI support for Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    root.tk_setPalette(background='#F3F3F3', foreground='#323130')
    app = ModernScriptRunnerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()