# PRD.md — Product Requirements Document

> **TwinCAT XML ↔ ST Converter**
> A desktop tool for engineers to view, edit, and round-trip TwinCAT 3 PLC code between PLCopen XML and Structured Text.

---

## Project Overview

| Field | Value |
|---|---|
| **Project Name** | TwinCAT XML ↔ ST Converter |
| **Owner** | Grundfos / PLC Engineering |
| **Date** | 2026-02-22 |
| **Status** | Phase 1 Complete |
| **App Type** | Offline desktop application (Python / Tkinter) |

---

## Problem Statement

TwinCAT 3 exports PLC code as PLCopen XML — a verbose, deeply nested format that is difficult to read, diff, or edit in a text editor. Engineers who need to review or copy logic across projects must work inside the TwinCAT IDE, which requires a full TwinCAT installation and a valid project context.

**This tool solves that** by extracting the actual Structured Text (ST) code from the XML, presenting it in a clean editable view, and converting edits back into XML that TwinCAT can re-import — without touching the TwinCAT IDE.

---

## Users

| User | Context |
|---|---|
| PLC Developer | Reviews and edits FB/Method logic outside of TwinCAT |
| Code Reviewer | Reads ST without needing TwinCAT installed |
| Automation Engineer | Transfers logic between projects by editing ST then re-importing |

---

## User Journey

1. **Export XML from TwinCAT** — Right-click a POU or DUT → "Export PLCopen XML"
2. **Open the exported file** — Launch the app, click Open XML, select the file
3. **Read and edit ST** — The full ST text (declaration + body + methods) is shown in the editor
4. **Convert back to XML** — Click "ST → XML" to regenerate the PLCopen XML
5. **Save and re-import** — Click "Save XML", then import into TwinCAT via "Import PLCopen XML"

---

## Supported XML Types

### FB — Function Block (`pouType="functionBlock"`)

Exported from TwinCAT as a single XML file containing:
- Interface declaration (VAR_INPUT, VAR_OUTPUT, VAR)
- Main body (ST code)
- Private/Public methods (each with their own VAR block and body)

Example: `FB_RingData.xml`

### DUT — Data Type / Struct (`<dataType name="...">`)

Exported from TwinCAT as a single XML file containing:
- A TYPE...STRUCT...END_STRUCT...END_TYPE declaration

Example: `ST_BatchMetadata.xml`

---

## Functional Requirements

### F1 — Load XML
- App detects FB vs DUT from XML structure automatically
- Displays a type badge (`FB` or `DUT`) in the header
- Shows the file path in the path bar

### F2 — ST Display (XML → ST)
- For **FB**: shows a single editable text block:
  ```
  FUNCTION_BLOCK Name
  VAR_INPUT / VAR_OUTPUT / VAR

  // === FB Body ===
  <body code>

  // ============================================================
  // Method: M_Name | PRIVATE | ReturnType
  // ============================================================
  METHOD PRIVATE M_Name : ReturnType
  VAR
      ...
  END_VAR
  <method body>
  ```
  - Methods always appear **after** the FB body, in declaration order
  - Each method is separated by a `// ===...===` divider with a parseable header line
  - No `METHOD` / `END_METHOD` wrapper keywords (method boundary = divider only)

- For **DUT**: shows the raw TYPE...END_TYPE declaration as-is

### F3 — ST Editing
- Full text editing in the left panel
- Undo/redo (`Ctrl+Z` / `Ctrl+Y`)
- Syntax highlighting: keywords, types, comments, strings, method dividers
- Line numbers

### F4 — Convert ST → XML
- Parses the edited ST text and patches the result back into the original XML structure
- Preserves all non-editable XML content (GUIDs, timestamps, attributes, `addData` metadata)
- Shows the resulting XML in the read-only right panel

### F5 — Round-Trip Fidelity
- If no edits are made, the regenerated XML must be **byte-for-byte identical** to the original
- XML entity encoding (`&amp;`, `&lt;`, `&gt;`) is preserved
- All `InterfaceAsPlainText` blocks (TwinCAT writes them 2–4× per POU) are kept in sync

### F6 — Save XML
- Saves the patched XML to disk via a file save dialog
- Default filename and directory are pre-filled from the original file path

### F7 — Copy XML
- Copies the full patched XML string to the system clipboard
- Button enabled only after "ST → XML" conversion has been run

### F8 — Copy ST
- Copies the current ST editor text to the system clipboard
- Button enabled immediately after a file is loaded (no conversion required)
- Shortcut: `Ctrl+T`
- Allows quick paste of ST into external editors, documentation, or code review tools

### F9 — Clear All
- Resets the application to its initial empty state
- Clears the ST editor, XML preview, path bar, and type badge
- Disables all action buttons (except Open XML)
- Button enabled after a file is loaded

---

## Non-Functional Requirements

| Requirement | Specification |
|---|---|
| **Runtime** | Python 3.12+, no external packages required |
| **Dependencies** | Zero — uses only Python stdlib (`tkinter`, `re`) |
| **Platform** | Windows 10/11 (primary), macOS/Linux (secondary) |
| **Startup time** | < 2 seconds |
| **File size handled** | XML files up to ~5 MB (typical TwinCAT exports are < 100 KB) |
| **Round-trip correctness** | 100% byte-identical when no ST edits are made |

---

## Success Conditions

- [x] Load `FB_RingData.xml` — displays correct ST with body + 2 methods
- [x] Load `ST_BatchMetadata.xml` — displays correct TYPE...STRUCT declaration
- [x] FB round-trip: XML → ST → XML produces byte-identical output
- [x] DUT round-trip: XML → ST → XML produces byte-identical output
- [x] Methods appear at the **end** of the ST text (after FB body)
- [x] Syntax highlighting covers IEC 61131-3 keywords, comments, strings
- [x] App launches with optional CLI file argument: `python src/main.py file.xml`
- [x] No external dependencies — ships as a folder of `.py` files
- [x] Copy ST button copies editor text to clipboard immediately after file load (`Ctrl+T`)
- [x] Clear All button resets app to initial state (enabled after file load)

---

## Out of Scope (Phase 1)

- TwinCAT-direct integration (no COM/ADS API)
- FUNCTION or PROGRAM POU types (only FUNCTION_BLOCK and DUT)
- Multi-file batch conversion
- Diff view between original and edited XML
- GVL (Global Variable List) export format
- Syntax validation or compile checking of edited ST
- Version control / git integration

---

## Architecture Summary

```
src/
├── main.py              Entry point, window startup
├── xml_parser.py        Load XML, extract ST pieces, patch XML (string-level)
├── st_formatter.py      Combine pieces → single display text
├── st_splitter.py       Parse display text → pieces for XML patching
└── ui/
    ├── main_window.py   Split-panel UI (editor | XML preview)
    └── editor_widget.py Syntax-highlighted editor + line numbers
```

**Core design decision**: XML is patched at the raw string level (not re-serialized through a parser). This is the only way to guarantee byte-for-byte round-trip fidelity with TwinCAT's non-standard XML structure (repeated `InterfaceAsPlainText` blocks, mixed tabs/spaces, specific entity encoding).

---

## References

- `FB_RingData.xml` — Primary FB template (source of truth for XML structure)
- `ST_BatchMetadata.xml` — Primary DUT template (source of truth for DUT structure)
- [ai/docs/2026-02-22-xml-st-converter-app.md](ai/docs/2026-02-22-xml-st-converter-app.md) — Implementation notes
- [CLAUDE.md](CLAUDE.md) — Agent rules and RAILGUARD security policy
- [PLAN.md](PLAN.md) — Development phase tracker
