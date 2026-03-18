#!/usr/bin/env python3
"""
Master High-Performance Visualization Generator
Runs all WebGL/Canvas visualization scripts to generate faster alternatives to D3/SVG.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_script(script_path, scraped_data_dir):
    script_name = os.path.basename(script_path)
    print(f"--- Running {script_name} ---")
    try:
        # Use the same python interpreter
        result = subprocess.run([sys.executable, script_path, scraped_data_dir], 
                                capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully generated visualization.")
            # Print last line of output which usually contains the file path
            lines = result.stdout.strip().split('\n')
            if lines: print(f"Output: {lines[-1]}")
        else:
            print(f"Error running {script_name}:")
            print(result.stderr)
    except Exception as e:
        print(f"Failed to execute {script_name}: {str(e)}")
    print()

def main():
    # Detect directories
    base_dir = Path(__file__).parent
    scraped_data_dir = base_dir.parent / "scraped_data"
    
    if not scraped_data_dir.exists():
        scraped_data_dir = base_dir / "scraped_data"
        if not scraped_data_dir.exists():
            print("Error: scraped_data directory not found.")
            return

    viz_scripts_dir = base_dir / "diagramatic exploratory analysis"
    
    # List of scripts to run
    high_perf_scripts = [
        "advanced_sigma_analysis.py",
        "forcegraph_global_visualization.py",
        "cosmograph_global_visualization.py",
        "echarts_global_visualization.py",
        "grand_webgl_visualization.py"
    ]

    print("====================================================")
    print("   DEEP WEB HIGH-PERFORMANCE VIZ GENERATOR          ")
    print("====================================================")
    print(f"Scraped data source: {scraped_data_dir}")
    print()

    for script_name in high_perf_scripts:
        script_full_path = viz_scripts_dir / script_name
        if script_full_path.exists():
            run_script(str(script_full_path), str(scraped_data_dir))
        else:
            # Check in the same directory as this master script
            script_full_path = base_dir / script_name
            if script_full_path.exists():
                run_script(str(script_full_path), str(scraped_data_dir))
            else:
                # Try relative from current work dir
                if os.path.exists(script_name):
                    run_script(script_name, str(scraped_data_dir))
                else:
                    print(f"Warning: Script {script_name} not found.")

    print("====================================================")
    print("All visualizations processed.")
    print("Check the 'scraped_data' directory for .html files.")
    print("Recommended starting point: forcegraph_network_visualization.html")
    print("====================================================")

if __name__ == "__main__":
    main()
