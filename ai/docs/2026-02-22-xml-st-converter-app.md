# Feature: TwinCAT XML ↔ ST Converter App

**Date**: 2026-02-22
**Status**: Complete (Phase 1 implementation)

---

## What Was Built

A Python desktop application that converts TwinCAT 3 PLCopen XML exports to Structured Text (ST) for viewing/editing, and converts them back to XML — with exact byte-for-byte round-trip fidelity.

---

## Files Created

```
src/
├── main.py              — App entry point (Tkinter + DPI awareness)
├── xml_parser.py        — XML loading, ST extraction, XML patching
├── st_formatter.py      — Combines extracted pieces into display ST text
├── st_splitter.py       — Splits edited ST back into XML-patchable pieces
├── ui/
│   ├── __init__.py
│   ├── main_window.py   — Main window (header, ST editor, XML preview, status)
│   └── editor_widget.py — ST syntax-highlighted editor with line numbers
└── tests/
    ├── __init__.py
    └── test_roundtrip.py — Round-trip exactness tests (pytest)
```

**Launch command**: `python src/main.py [optional: path/to/file.xml]`

---

## Architecture: Template-Patch Approach

**Key decision**: Never regenerate XML from scratch. Instead:

1. Load XML → store raw bytes + parse structure
2. Extract editable ST content (from `<xhtml>` nodes)
3. Display as single text block in the editor
4. On "ST → XML": patch only the changed `<xhtml>` nodes back into the stored raw XML string

This is the only approach that achieves exact byte-for-byte round-trip, because it preserves all XML structure, attributes, GUIDs, whitespace, and entity encoding.

---

## Supported XML Types

### FB (Function Block)  — `FB_RingData.xml` pattern
- `<pous><pou pouType="functionBlock">`
- Has interface (inputVars, outputVars, localVars) with 4 identical `InterfaceAsPlainText` blocks
- Has `<body><ST><xhtml>` for the main body code
- Has methods in `<addData>` as `<Method name=...>` elements

### DUT (Data Type) — `ST_BatchMetadata.xml` pattern
- `<dataTypes><dataType>`
- Has a single `InterfaceAsPlainText` with the TYPE...STRUCT...END_TYPE text

---

## ST Display Format

### FB with Methods
```
FUNCTION_BLOCK FB_RingData
VAR_INPUT
    ...
END_VAR
VAR_OUTPUT
    ...
END_VAR
VAR
    ...
END_VAR

// === FB Body ===
rTrig(CLK := bTrigger);
...
bBusy := bIsRecording OR bIsSaving;

// ============================================================
// Method: M_Filename | PRIVATE | STRING
// ============================================================
METHOD PRIVATE M_Filename : STRING
VAR
    sTimeStr : STRING;
    sTemp    : STRING;
END_VAR
<body code>

// ============================================================
// Method: M_JsonGenerate | PRIVATE | BOOL
// ============================================================
...
```

### DUT
```
(*
    DUT: ST_BatchMetadata
    ...
*)
TYPE ST_BatchMetadata :
STRUCT
    sOrderNumberSAP : STRING := '14963766';
    ...
END_STRUCT
END_TYPE
```

---

## Round-Trip Whitespace Contract

The formatter and splitter share an exact whitespace contract:

- `format_st` uses `"\n".join(parts)` — adds one `\n` between each piece
- `var_decl.strip()` in formatter → the join adds `\n` before body
- Body's `\n` from method's xhtml node is preserved as-is (no normalization)
- The `^\s*END_VAR\s*$` pattern in splitter matches INCLUDING the trailing `\n`
  → so `content[end_var.end():]` starts directly with the body's own leading `\n`
- For non-last methods: strip exactly two trailing `\n` (from join-induced separators)
- For last method: no trailing strip needed

This contract ensures: `original_body == split_body` for exact round-trip.

---

## UI Features

- **Dark theme** (industrial colour palette, Beckhoff-inspired)
- **Left panel**: ST editor with syntax highlighting + line numbers
- **Right panel**: XML preview (read-only, shown after conversion)
- **Buttons**: Open XML, ST→XML, Save XML, Copy XML
- **Type badge**: Shows `FB` or `DUT` for the loaded file
- **Keyboard shortcuts**: `Ctrl+O` open, `Ctrl+Enter` convert, `Ctrl+S` save
- **ST Syntax highlighting**: keywords (purple/blue/yellow/teal), comments (grey/italic), strings (green), divider lines (dark blue), method headers (cyan)

---

## Test Results

22/22 tests passing (run manually with `python -m pytest src/tests/` if pytest installed):

- FB type detection ✓
- FB interface/body/method extraction ✓
- FB ST format (dividers, markers, method order) ✓
- FB split reconstruction (decl, body, methods match exactly) ✓
- **FB ROUND-TRIP EXACT** ✓
- DUT type detection ✓
- DUT declaration extraction ✓
- **DUT ROUND-TRIP EXACT** ✓

---

## Zero External Dependencies

Uses only Python 3.12 built-ins:
- `tkinter` + `ttk` for UI
- `re` for XML and ST parsing
- No `lxml`, no `PyQt`, no `xml.etree` (avoids serialization reformatting)
