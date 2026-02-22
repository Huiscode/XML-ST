"""
main_window.py
--------------
Main application window.
Layout: header bar | horizontal split (ST editor | XML preview) | status bar
"""

import json
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Ensure src/ is on the path when run from ui/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from xml_parser import load_xml, patch_xml, ParsedXML, detect_st_type, build_xml_from_st
from st_formatter import format_st
from st_splitter import split_st
from ui.editor_widget import STEditor


# ---------------------------------------------------------------------------
# Colour palette  (dark industrial theme — Beckhoff-ish)
# ---------------------------------------------------------------------------
PALETTE = {
    "bg":           "#1e1e2e",   # deep blue-black
    "panel":        "#252536",   # slightly lighter panel
    "border":       "#3a3a5c",   # separator colour
    "accent":       "#00b4d8",   # cyan accent (Beckhoff blue)
    "accent2":      "#90e0ef",   # lighter accent
    "btn":          "#00b4d8",
    "btn_hover":    "#0096c7",
    "btn_text":     "#ffffff",
    "text_primary": "#cdd6f4",
    "text_muted":   "#888aac",
    "success":      "#a6e3a1",
    "warning":      "#f9e2af",
    "error":        "#f38ba8",
    "xml_bg":       "#1a1a2e",
}


class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TwinCAT XML ↔ ST Converter")
        self.root.configure(bg=PALETTE["bg"])
        self.root.geometry("1400x860")
        self.root.minsize(900, 600)

        self._parsed: ParsedXML | None = None
        self._current_path: str = ""
        self._config_path = os.path.join(os.path.expanduser("~"), ".xml_st_converter.json")
        self._last_dir: str = self._load_last_dir()

        self._build_ui()
        self._bind_shortcuts()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ---- Top header bar ----
        header = tk.Frame(self.root, bg=PALETTE["bg"], pady=8)
        header.pack(side=tk.TOP, fill=tk.X, padx=12)

        # Logo / title label
        tk.Label(
            header, text="TwinCAT  XML ↔ ST  Converter",
            font=("Segoe UI", 14, "bold"),
            fg=PALETTE["accent"], bg=PALETTE["bg"]
        ).pack(side=tk.LEFT)

        # Type badge (FB / DUT)
        self._type_badge = tk.Label(
            header, text="", width=10,
            font=("Segoe UI", 10, "bold"),
            fg=PALETTE["btn_text"], bg=PALETTE["border"],
            relief="flat", padx=10, pady=2
        )
        self._type_badge.pack(side=tk.LEFT, padx=(14, 0))

        # Buttons on the right
        btn_frame = tk.Frame(header, bg=PALETTE["bg"])
        btn_frame.pack(side=tk.RIGHT)

        self._btn_open    = self._make_btn(btn_frame, "Open XML",  self._open_file,      icon="📂")
        self._btn_open_st = self._make_btn(btn_frame, "Open ST",   self._open_st,        icon="📂")
        self._btn_to_xml  = self._make_btn(btn_frame, "ST → XML",  self._convert_to_xml, icon="⚙",  state=tk.DISABLED)
        self._btn_save    = self._make_btn(btn_frame, "Save XML",  self._save_xml,       icon="💾", state=tk.DISABLED)
        self._btn_copy    = self._make_btn(btn_frame, "Copy XML",  self._copy_xml,       icon="📋", state=tk.DISABLED)
        self._btn_copy_st = self._make_btn(btn_frame, "Save ST",    self._save_st,        icon="📄", state=tk.DISABLED)
        self._btn_clip_st = self._make_btn(btn_frame, "Copy ST",   self._copy_st,        icon="📋", state=tk.DISABLED)
        self._btn_clear   = self._make_btn(btn_frame, "Clear All", self._clear_all,      icon="🗑",  state=tk.DISABLED,
                                           bg=PALETTE["border"], hover=PALETTE["error"])

        for b in (self._btn_open, self._btn_open_st, self._btn_to_xml, self._btn_save,
                  self._btn_copy, self._btn_copy_st, self._btn_clip_st, self._btn_clear):
            b.pack(side=tk.LEFT, padx=4)

        # ---- File path bar ----
        path_bar = tk.Frame(self.root, bg=PALETTE["panel"], pady=4)
        path_bar.pack(side=tk.TOP, fill=tk.X, padx=12)

        tk.Label(path_bar, text="File:", fg=PALETTE["text_muted"],
                 bg=PALETTE["panel"], font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=6)
        self._path_var = tk.StringVar(value="No file loaded")
        tk.Label(path_bar, textvariable=self._path_var,
                 fg=PALETTE["text_primary"], bg=PALETTE["panel"],
                 font=("Consolas", 9), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ---- Separator ----
        ttk.Separator(self.root, orient="horizontal").pack(fill=tk.X, padx=0, pady=0)

        # ---- Column headers ----
        col_header = tk.Frame(self.root, bg=PALETTE["bg"])
        col_header.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(6, 0))

        self._st_col_label = tk.Label(
            col_header, text="Structured Text  (editable)",
            font=("Segoe UI", 10, "bold"), fg=PALETTE["accent2"], bg=PALETTE["bg"]
        )
        self._st_col_label.pack(side=tk.LEFT)

        self._xml_col_label = tk.Label(
            col_header, text="XML Preview  (read-only)",
            font=("Segoe UI", 10, "bold"), fg=PALETTE["text_muted"], bg=PALETTE["bg"]
        )
        self._xml_col_label.pack(side=tk.RIGHT)

        # ---- Main horizontal split pane ----
        pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                              bg=PALETTE["border"], sashwidth=5,
                              sashrelief="flat", sashpad=0)
        pane.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=6)

        # Left: ST editor
        left_frame = tk.Frame(pane, bg=PALETTE["panel"])
        self._st_editor = STEditor(left_frame, PALETTE)
        self._st_editor.set_change_callback(self._on_editor_change)
        self._st_editor.pack(fill=tk.BOTH, expand=True)
        pane.add(left_frame, minsize=400, stretch="always")

        # Right: XML viewer
        right_frame = tk.Frame(pane, bg=PALETTE["panel"])
        self._xml_view = self._build_xml_viewer(right_frame)
        right_frame.pack_propagate(False)
        pane.add(right_frame, minsize=300, stretch="always")

        # Set initial sash position after window is drawn
        self.root.after(100, lambda: pane.sash_place(0, 720, 0))

        # ---- Status bar ----
        status_bar = tk.Frame(self.root, bg=PALETTE["panel"], pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._status_var = tk.StringVar(value="Ready — open an XML file to begin.")
        self._status_lbl = tk.Label(
            status_bar, textvariable=self._status_var,
            fg=PALETTE["text_primary"], bg=PALETTE["panel"],
            font=("Segoe UI", 9), anchor="w", padx=10
        )
        self._status_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Shortcut hint on the right of status bar
        tk.Label(
            status_bar, text="Ctrl+O  Open   |   Ctrl+Return  Convert   |   Ctrl+S  Save   |   Ctrl+T  Save ST.txt",
            fg=PALETTE["text_muted"], bg=PALETTE["panel"],
            font=("Segoe UI", 8), padx=10
        ).pack(side=tk.RIGHT)

        # Buffer for the current patched XML output
        self._output_xml: str = ""

    def _build_xml_viewer(self, parent: tk.Frame) -> tk.Text:
        """Read-only XML preview pane with horizontal + vertical scrollbars."""
        frame = tk.Frame(parent, bg=PALETTE["xml_bg"])
        frame.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(frame, orient="vertical")
        hsb = ttk.Scrollbar(frame, orient="horizontal")
        txt = tk.Text(
            frame,
            font=("Consolas", 9),
            bg=PALETTE["xml_bg"],
            fg="#9ece6a",        # XML green tint
            insertbackground=PALETTE["accent"],
            selectbackground=PALETTE["border"],
            wrap=tk.NONE,
            state=tk.DISABLED,
            relief="flat",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            padx=8, pady=8,
        )
        vsb.config(command=txt.yview)
        hsb.config(command=txt.xview)

        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return txt

    def _make_btn(self, parent, text, command, icon="", state=tk.NORMAL,
                  bg=None, hover=None):
        label = f"{icon}  {text}" if icon else text
        bg_color    = bg    or PALETTE["btn"]
        hover_color = hover or PALETTE["btn_hover"]
        btn = tk.Button(
            parent,
            text=label,
            command=command,
            state=state,
            font=("Segoe UI", 9, "bold"),
            fg=PALETTE["btn_text"],
            bg=bg_color,
            activeforeground=PALETTE["btn_text"],
            activebackground=hover_color,
            relief="flat",
            width=11,
            padx=6, pady=2,
            cursor="hand2",
        )
        btn.bind("<Enter>", lambda e, h=hover_color: btn.config(bg=h))
        btn.bind("<Leave>", lambda e, b=bg_color: btn.config(bg=b))
        return btn

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self._open_file())
        self.root.bind("<Control-O>", lambda e: self._open_file())
        self.root.bind("<Control-Return>", lambda e: self._convert_to_xml())
        self.root.bind("<Control-s>", lambda e: self._save_xml())
        self.root.bind("<Control-S>", lambda e: self._save_xml())
        self.root.bind("<Control-t>", lambda e: self._save_st())
        self.root.bind("<Control-T>", lambda e: self._save_st())

    # ------------------------------------------------------------------
    # Editor content change callback
    # ------------------------------------------------------------------

    def _on_editor_change(self, text: str):
        """Called whenever the ST editor content changes (key, paste, etc.)."""
        has_text = bool(text.strip())
        state = tk.NORMAL if has_text else tk.DISABLED
        self._btn_to_xml.config(state=state)
        self._btn_copy_st.config(state=state)
        self._btn_clip_st.config(state=state)
        self._btn_clear.config(state=state)

        # Update type badge from text content when no file is loaded
        if not self._parsed and has_text:
            import re
            if re.search(r'^\s*FUNCTION_BLOCK\b', text, re.MULTILINE | re.IGNORECASE):
                label, color = "FB", "#4a90d9"
            elif re.search(r'^\s*PROGRAM\b', text, re.MULTILINE | re.IGNORECASE):
                label, color = "PROG", "#2e7d32"
            elif re.search(r'^\s*TYPE\b', text, re.MULTILINE | re.IGNORECASE):
                label, color = "DUT", "#7e57c2"
            else:
                label, color = "", PALETTE["border"]
            self._type_badge.config(text=f"  {label}  " if label else "", bg=color)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _load_last_dir(self) -> str:
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                return json.load(f).get("last_dir", ".")
        except Exception:
            return "."

    def _save_last_dir(self, path: str):
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump({"last_dir": os.path.dirname(path)}, f)
        except Exception:
            pass

    def _open_file(self):
        initial = os.path.dirname(self._current_path) if self._current_path else self._last_dir
        path = filedialog.askopenfilename(
            title="Open TwinCAT XML Export",
            filetypes=[("PLCopen XML", "*.xml"), ("All files", "*.*")],
            initialdir=initial,
        )
        if not path:
            return
        self._load(path)

    def _open_st(self):
        initial = os.path.dirname(self._current_path) if self._current_path else self._last_dir
        path = filedialog.askopenfilename(
            title="Open ST Text File",
            filetypes=[("Text / ST files", "*.txt *.st *.TXT *.ST"),
                       ("All files", "*.*")],
            initialdir=initial,
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as exc:
            self._set_status(f"Error opening ST file: {exc}", error=True)
            messagebox.showerror("Open Error", str(exc))
            return

        # Keep self._parsed if one is already loaded — the user may want to
        # patch new ST text back into the existing XML structure via ST → XML.
        self._output_xml = ""
        self._save_last_dir(path)
        self._path_var.set(path)
        self._set_xml_view("")
        self._st_editor.set_text(text)
        self._on_editor_change(text)  # update badge + button states immediately

        self._btn_save.config(state=tk.DISABLED)
        self._btn_copy.config(state=tk.DISABLED)
        self._btn_clear.config(state=tk.NORMAL)

        fname = os.path.basename(path)
        self._set_status(f"Opened  {fname}  — ST text loaded into editor.")

    def _load(self, path: str):
        try:
            self._parsed = load_xml(path)
        except Exception as exc:
            self._set_status(f"Error loading file: {exc}", error=True)
            messagebox.showerror("Load Error", str(exc))
            return

        self._current_path = path
        self._save_last_dir(path)
        self._path_var.set(path)

        # Update type badge
        badge_colors = {"FB": "#4a90d9", "PROGRAM": "#2e7d32", "DUT": "#7e57c2"}
        badge_color = badge_colors.get(self._parsed.xml_type, PALETTE["border"])
        self._type_badge.config(
            text=f"  {self._parsed.xml_type}  ",
            bg=badge_color
        )

        # Populate ST editor
        st_text = format_st(self._parsed)
        self._st_editor.set_text(st_text)

        # Clear XML view (not yet converted)
        self._set_xml_view("")
        self._output_xml = ""

        # Enable buttons
        self._btn_to_xml.config(state=tk.NORMAL)
        self._btn_copy_st.config(state=tk.NORMAL)
        self._btn_clip_st.config(state=tk.NORMAL)
        self._btn_clear.config(state=tk.NORMAL)
        self._btn_save.config(state=tk.DISABLED)
        self._btn_copy.config(state=tk.DISABLED)

        fname = os.path.basename(path)
        self._set_status(
            f"Loaded  {fname}  [{self._parsed.xml_type}] — "
            f"Edit ST then click ⚙ ST → XML to convert."
        )

    def _convert_to_xml(self):
        st_text = self._st_editor.get_text()

        if self._parsed is None:
            # No XML template — build XML from scratch using the ST text.
            try:
                xml_type, pou_name = detect_st_type(st_text)
            except ValueError as exc:
                self._set_status(str(exc), error=True)
                messagebox.showerror("Detection Error", str(exc))
                return

            try:
                split = split_st(st_text, xml_type)
            except Exception as exc:
                self._set_status(f"Parse error: {exc}", error=True)
                messagebox.showerror("ST Parse Error", str(exc))
                return

            try:
                if xml_type == "DUT":
                    patched = build_xml_from_st(xml_type, pou_name,
                                               split.declaration, "", [])
                else:
                    patched = build_xml_from_st(xml_type, pou_name,
                                               split.declaration, split.body,
                                               split.methods)
            except Exception as exc:
                self._set_status(f"XML build error: {exc}", error=True)
                messagebox.showerror("XML Build Error", str(exc))
                return

            # Update type badge
            badge_colors = {"FB": "#4a90d9", "PROGRAM": "#2e7d32", "DUT": "#7e57c2"}
            self._type_badge.config(
                text=f"  {xml_type}  ",
                bg=badge_colors.get(xml_type, PALETTE["border"])
            )

            self._output_xml = patched
            self._set_xml_view(patched)
            self._btn_save.config(state=tk.NORMAL)
            self._btn_copy.config(state=tk.NORMAL)
            self._set_status(
                f"Built XML for {pou_name} [{xml_type}] — review, then Save.",
                success=True
            )
            return

        # Template loaded — patch ST into the existing XML structure.
        try:
            split = split_st(st_text, self._parsed.xml_type)
        except Exception as exc:
            self._set_status(f"Parse error: {exc}", error=True)
            messagebox.showerror("ST Parse Error", str(exc))
            return

        try:
            if self._parsed.xml_type == "DUT":
                patched = patch_xml(
                    self._parsed,
                    new_declaration=split.declaration,
                    new_body="",
                    new_methods=[],
                )
            else:
                patched = patch_xml(
                    self._parsed,
                    new_declaration=split.declaration,
                    new_body=split.body,
                    new_methods=split.methods,
                )
        except Exception as exc:
            self._set_status(f"XML patch error: {exc}", error=True)
            messagebox.showerror("XML Patch Error", str(exc))
            return

        self._output_xml = patched
        self._set_xml_view(patched)
        self._btn_save.config(state=tk.NORMAL)
        self._btn_copy.config(state=tk.NORMAL)
        self._set_status("Conversion complete — review XML, then Save.", success=True)

    def _save_xml(self):
        if not self._output_xml:
            self._set_status("Nothing to save — run ST → XML first.", warning=True)
            return

        initial = self._current_path or "output.xml"
        path = filedialog.asksaveasfilename(
            title="Save XML",
            defaultextension=".xml",
            filetypes=[("PLCopen XML", "*.xml"), ("All files", "*.*")],
            initialfile=os.path.basename(initial),
            initialdir=os.path.dirname(initial),
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._output_xml)
            self._set_status(f"Saved → {path}", success=True)
        except Exception as exc:
            self._set_status(f"Save error: {exc}", error=True)
            messagebox.showerror("Save Error", str(exc))

    def _copy_xml(self):
        if not self._output_xml:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._output_xml)
        self._set_status("XML copied to clipboard.", success=True)

    def _save_st(self):
        text = self._st_editor.get_text()
        if not text:
            return
        base = os.path.splitext(os.path.basename(self._current_path))[0] if self._current_path else "output"
        path = filedialog.asksaveasfilename(
            title="Save ST as text file",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile=f"{base}.txt",
            initialdir=os.path.dirname(self._current_path) if self._current_path else ".",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self._set_status(f"ST saved → {path}", success=True)
        except Exception as exc:
            self._set_status(f"Save error: {exc}", error=True)
            messagebox.showerror("Save Error", str(exc))

    def _copy_st(self):
        text = self._st_editor.get_text()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_status("ST text copied to clipboard.", success=True)

    def _clear_all(self):
        self._parsed = None
        self._current_path = ""
        self._output_xml = ""

        self._st_editor.set_text("")
        self._set_xml_view("")
        self._path_var.set("No file loaded")
        self._type_badge.config(text="", bg=PALETTE["border"])

        for btn in (self._btn_to_xml, self._btn_save,
                    self._btn_copy, self._btn_copy_st, self._btn_clip_st, self._btn_clear):
            btn.config(state=tk.DISABLED)

        self._set_status("Cleared — open an XML file to begin.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_xml_view(self, text: str):
        self._xml_view.config(state=tk.NORMAL)
        self._xml_view.delete("1.0", tk.END)
        if text:
            self._xml_view.insert("1.0", text)
            self._highlight_xml_view()
        self._xml_view.config(state=tk.DISABLED)

    def _highlight_xml_view(self):
        """Colour ST code inside <xhtml> nodes white; everything else stays green."""
        import re
        txt = self._xml_view
        txt.tag_configure("st_content", foreground="#ffffff")

        content = txt.get("1.0", tk.END)
        for m in re.finditer(r"<xhtml(?:[^>]*)>(.*?)</xhtml>", content, re.DOTALL):
            start_char = m.start(1)
            end_char   = m.end(1)
            start_idx  = f"1.0 + {start_char} chars"
            end_idx    = f"1.0 + {end_char} chars"
            txt.tag_add("st_content", start_idx, end_idx)

    def _set_status(self, msg: str, error=False, success=False, warning=False):
        color = PALETTE["text_primary"]
        if error:
            color = PALETTE["error"]
        elif success:
            color = PALETTE["success"]
        elif warning:
            color = PALETTE["warning"]
        self._status_var.set(msg)
        self._status_lbl.config(fg=color)
