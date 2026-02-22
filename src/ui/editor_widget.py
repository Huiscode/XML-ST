"""
editor_widget.py
----------------
ST syntax-highlighted text editor built on tk.Text.
Highlights IEC 61131-3 Structured Text keywords, comments, strings,
and the converter's divider/header lines.
"""

import re
import tkinter as tk
from tkinter import ttk


# IEC 61131-3 keyword groups
_KEYWORDS_CONTROL = [
    "IF", "THEN", "ELSE", "ELSIF", "END_IF",
    "FOR", "TO", "BY", "DO", "END_FOR",
    "WHILE", "END_WHILE",
    "REPEAT", "UNTIL", "END_REPEAT",
    "CASE", "OF", "END_CASE",
    "RETURN", "EXIT", "CONTINUE",
]

_KEYWORDS_DECLARATION = [
    "FUNCTION_BLOCK", "END_FUNCTION_BLOCK",
    "FUNCTION", "END_FUNCTION",
    "PROGRAM", "END_PROGRAM",
    "METHOD", "END_METHOD",
    "PROPERTY", "END_PROPERTY",
    "ACTION", "END_ACTION",
    "STRUCT", "END_STRUCT",
    "TYPE", "END_TYPE",
    "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT",
    "VAR_GLOBAL", "VAR_EXTERNAL",
    "VAR", "END_VAR",
    "PRIVATE", "PUBLIC", "PROTECTED", "INTERNAL", "FINAL", "ABSTRACT",
]

_KEYWORDS_TYPES = [
    "BOOL", "BYTE", "WORD", "DWORD", "LWORD",
    "SINT", "INT", "DINT", "LINT",
    "USINT", "UINT", "UDINT", "ULINT",
    "REAL", "LREAL",
    "TIME", "DATE", "TIME_OF_DAY", "DATE_AND_TIME",
    "STRING", "WSTRING",
    "ARRAY", "OF", "AT",
    "TRUE", "FALSE",
    "T_DCTIME64", "LREAL",
]

_KEYWORDS_STDLIB = [
    "R_TRIG", "F_TRIG", "TON", "TOF", "TP", "CTU", "CTD", "CTUD",
    "AND", "OR", "NOT", "XOR", "MOD",
    "ADR", "SIZEOF", "LEFT", "RIGHT", "MID", "CONCAT", "REPLACE",
    "LEN", "FIND", "UPPER", "LOWER",
    "ABS", "SQRT", "LN", "LOG", "EXP", "SIN", "COS", "TAN",
    "TRUNC", "ROUND",
]


def _kw_pattern(words: list[str]) -> str:
    """Whole-word regex for a list of keywords."""
    escaped = sorted(words, key=len, reverse=True)  # longest first
    return r'\b(?:' + '|'.join(re.escape(w) for w in escaped) + r')\b'


class STEditor(tk.Frame):
    """
    A scrollable, syntax-highlighted Structured Text editor.
    """

    def __init__(self, parent, palette: dict, **kwargs):
        super().__init__(parent, bg=palette["panel"], **kwargs)
        self._palette = palette
        self._highlight_job = None
        self._build()
        self._configure_tags()

    def _build(self):
        p = self._palette

        # Line-number canvas
        self._ln_canvas = tk.Canvas(
            self, width=46, bg="#161625",
            highlightthickness=0, bd=0
        )
        self._ln_canvas.pack(side=tk.LEFT, fill=tk.Y)

        # Main editor + scrollbars
        vsb = ttk.Scrollbar(self, orient="vertical")
        hsb = ttk.Scrollbar(self, orient="horizontal")

        self._text = tk.Text(
            self,
            font=("Consolas", 10),
            bg="#1a1a2e",
            fg=p["text_primary"],
            insertbackground=p["accent"],
            selectbackground=p["border"],
            selectforeground=p["text_primary"],
            wrap=tk.NONE,
            relief="flat",
            padx=10, pady=8,
            undo=True,
            maxundo=200,
            yscrollcommand=self._on_yscroll,
            xscrollcommand=hsb.set,
            tabs=("28p",),   # 4-space-wide tab stops
        )

        vsb.config(command=self._text.yview)
        hsb.config(command=self._text.xview)

        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._vsb = vsb

        self._text.bind("<KeyRelease>", self._on_key_release)
        self._text.bind("<<Paste>>",    self._on_paste)
        self._text.bind("<MouseWheel>", lambda e: self._redraw_line_numbers())
        self._text.bind("<Configure>",  lambda e: self._redraw_line_numbers())
        self._ln_canvas.bind("<Button-1>", lambda e: self._text.focus_set())
        self._change_callback = None

    def _configure_tags(self):
        t = self._text
        p = self._palette

        t.tag_configure("kw_control",     foreground="#c678dd")  # purple
        t.tag_configure("kw_declare",     foreground="#61afef")  # blue
        t.tag_configure("kw_type",        foreground="#e5c07b")  # yellow
        t.tag_configure("kw_stdlib",      foreground="#56b6c2")  # teal
        t.tag_configure("comment_line",   foreground="#5c6370", font=("Consolas", 10, "italic"))
        t.tag_configure("comment_block",  foreground="#5c6370", font=("Consolas", 10, "italic"))
        t.tag_configure("string",         foreground="#98c379")  # green
        t.tag_configure("number",         foreground="#d19a66")  # orange
        t.tag_configure("divider",        foreground="#3a3a5c",  font=("Consolas", 10, "bold"))
        t.tag_configure("method_header",  foreground=p["accent"], font=("Consolas", 10, "bold"))
        t.tag_configure("fb_body_marker", foreground=p["accent2"], font=("Consolas", 10, "bold"))
        t.tag_configure("operator",       foreground="#abb2bf")

        # Tag priority (higher = applied last = wins)
        for tag in ("comment_line", "comment_block", "string", "divider",
                    "method_header", "fb_body_marker"):
            t.tag_raise(tag)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_change_callback(self, fn):
        """Register a function to call whenever the editor content changes."""
        self._change_callback = fn

    def _fire_change(self):
        if self._change_callback:
            self._change_callback(self.get_text())

    def _on_key_release(self, event=None):
        self._schedule_highlight()
        self._fire_change()

    def _on_paste(self, event=None):
        # Paste happens after this event, so schedule the callback slightly later
        self.after(10, self._fire_change)

    def set_text(self, text: str):
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._text.edit_reset()
        self._highlight_all()
        self._redraw_line_numbers()

    def get_text(self) -> str:
        return self._text.get("1.0", tk.END).rstrip("\n")

    # ------------------------------------------------------------------
    # Scrollbar sync with line numbers
    # ------------------------------------------------------------------

    def _on_yscroll(self, *args):
        self._vsb.set(*args)
        self._redraw_line_numbers()

    def _redraw_line_numbers(self):
        canvas = self._ln_canvas
        txt = self._text
        canvas.delete("all")

        i = txt.index("@0,0")
        while True:
            dline = txt.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            canvas.create_text(
                40, y + 8,
                anchor="ne",
                text=linenum,
                font=("Consolas", 9),
                fill="#4a4a6a",
            )
            i = txt.index(f"{i}+1line")
            if i == txt.index(f"end"):
                break

    # ------------------------------------------------------------------
    # Syntax highlighting
    # ------------------------------------------------------------------

    def _schedule_highlight(self, event=None):
        if self._highlight_job:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(300, self._highlight_all)

    def _highlight_all(self):
        t = self._text
        text = t.get("1.0", tk.END)

        # Remove all existing tags
        for tag in t.tag_names():
            if tag not in ("sel",):
                t.tag_remove(tag, "1.0", tk.END)

        self._apply_regex(text, _kw_pattern(_KEYWORDS_CONTROL),  "kw_control",  re.IGNORECASE)
        self._apply_regex(text, _kw_pattern(_KEYWORDS_DECLARATION), "kw_declare", re.IGNORECASE)
        self._apply_regex(text, _kw_pattern(_KEYWORDS_TYPES),    "kw_type",     re.IGNORECASE)
        self._apply_regex(text, _kw_pattern(_KEYWORDS_STDLIB),   "kw_stdlib",   re.IGNORECASE)

        # Numbers  (e.g.  100, 1.0E38, T#60M, TIME#30m0s)
        self._apply_regex(text, r'\b\d+(?:\.\d+)?(?:E[+-]?\d+)?\b', "number")
        self._apply_regex(text, r'\bT#\S+|\bTIME#\S+|\bDT#\S+', "number", re.IGNORECASE)

        # Strings  '...'
        self._apply_regex(text, r"'[^']*'", "string")

        # Block comments  (* ... *)
        self._apply_regex(text, r'\(\*.*?\*\)', "comment_block", re.DOTALL)

        # Line comments  // ...
        self._apply_regex(text, r'//.*$', "comment_line", re.MULTILINE)

        # Divider lines  (override comment colour — blue-grey)
        self._apply_regex(text, r'^// ={50,}\s*$', "divider", re.MULTILINE)

        # Method header lines
        self._apply_regex(text, r'^// Method:.*$', "method_header", re.MULTILINE)

        # Body markers (FB and PROGRAM)
        self._apply_regex(text, r'^// === (?:FB|PROGRAM) Body ===$', "fb_body_marker", re.MULTILINE)

        self._redraw_line_numbers()

    def _apply_regex(self, text: str, pattern: str, tag: str, flags: int = 0):
        t = self._text
        for m in re.finditer(pattern, text, flags):
            start = f"1.0+{m.start()}c"
            end   = f"1.0+{m.end()}c"
            t.tag_add(tag, start, end)
