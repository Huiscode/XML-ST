"""
main.py
-------
Entry point for the TwinCAT XML ↔ ST Converter desktop app.

Usage:
    python src/main.py [optional: path/to/file.xml]
"""

import sys
import os
import tkinter as tk

# Ensure src/ is on the import path when launched from the project root
sys.path.insert(0, os.path.dirname(__file__))

from ui.main_window import MainWindow


def main():
    root = tk.Tk()

    # App icon (suppress error if not available)
    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    # DPI awareness on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = MainWindow(root)

    # If a file path is passed as CLI argument, open it immediately
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.isfile(path):
            root.after(200, lambda: app._load(path))

    root.mainloop()


if __name__ == "__main__":
    main()
