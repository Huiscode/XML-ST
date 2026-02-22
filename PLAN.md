# PLAN.md — Implementation Plan

> Actionable, step-by-step plan for the **TwinCAT XML ↔ ST Converter** tool.
> See [PRD.md](PRD.md) for full requirements and [CLAUDE.md](CLAUDE.md) for agent rules.

---

## Phase 1: Prework — Preparing the Repository ✅ Complete

> Establish project foundations, context files, and agent guardrails.

- [x] Run architectural research — codified existing PLC XML structure
- [x] Populate CLAUDE.md with project conventions and RAILGUARD rules
- [x] Write PRD.md with full product requirements
- [x] Verify all context files in place (PRD, PLAN, CLAUDE)

---

## Phase 2: Foundation — Core App Scaffolding ✅ Complete

> Build the XML parsing and ST conversion engine. Zero external dependencies.

- [x] Project structure created: `src/`, `src/ui/`, `src/tests/`
- [x] `xml_parser.py` — load XML, detect FB/DUT type, extract ST pieces, patch XML back
- [x] `st_formatter.py` — combine extracted pieces into single editable ST display text
- [x] `st_splitter.py` — parse edited ST back into XML-patchable pieces
- [x] Round-trip tests written and passing (22/22) — including byte-identical fidelity

---

## Phase 3: Core Features ✅ Complete

> Build the desktop UI and syntax highlighting.

### Feature 1: XML → ST Conversion
- [x] FB type: declaration + body + methods (methods last, divider-separated)
- [x] DUT type: TYPE...STRUCT...END_TYPE display
- [x] Methods displayed with `// ====` divider + `// Method: Name | ACCESS | ReturnType` header
- [x] No METHOD/END_METHOD keywords — divider is the sole boundary marker
- [x] Exact byte-for-byte round-trip verified for both template XMLs

### Feature 2: Desktop UI
- [x] Dark-themed split-panel window (ST editor | XML preview)
- [x] File open dialog with type auto-detection badge (FB / DUT)
- [x] ST → XML conversion button with live XML preview
- [x] Save XML and Copy XML actions
- [x] Copy ST button — copies editor text to clipboard; enabled on file load (`Ctrl+T`)
- [x] Clear All button — resets editor, XML view, path bar, badge, and all button states; enabled on file load
- [x] Keyboard shortcuts: `Ctrl+O`, `Ctrl+Enter`, `Ctrl+S`, `Ctrl+T`
- [x] Status bar with contextual messages (load, convert, save, copy, error states)

### Feature 3: ST Syntax Highlighting
- [x] IEC 61131-3 control keywords (purple): IF, FOR, WHILE, CASE, RETURN…
- [x] Declaration keywords (blue): FUNCTION_BLOCK, VAR_INPUT, VAR, END_VAR…
- [x] Type keywords (yellow): BOOL, INT, REAL, STRING, TIME, ARRAY…
- [x] Standard library (teal): R_TRIG, TON, ADR, CONCAT, LEFT…
- [x] Comments (grey/italic): `//` and `(* *)`
- [x] Strings (green): `'...'`
- [x] Divider lines (dark): `// ====`
- [x] Method header lines (cyan): `// Method: ...`
- [x] Line numbers sidebar

### Feature 4: Documentation
- [x] `ai/docs/2026-02-22-xml-st-converter-app.md` — implementation notes
- [x] PRD.md — full product requirements document

---

## Phase 4: Hardening — Next Steps

> Improve robustness, edge cases, and usability.

- [ ] **FUNCTION POU support** — handle `pouType="function"` exports (no interface vars)
- [ ] **PROGRAM POU support** — handle `pouType="program"` exports
- [ ] **GVL support** — Global Variable List XML format
- [ ] **Public/Protected methods** — `st_splitter` hardcodes `METHOD PRIVATE`; generalize for other access modifiers
- [ ] **Multi-file open** — tabs or a recent files list
- [ ] **Diff mode** — show what changed between original XML and patched XML
- [ ] **Drag-and-drop** — drag XML file onto the window to open
- [ ] **Auto-reload** — watch source file for changes (useful with TwinCAT side-by-side)
- [ ] Edge case: FB with no methods — verify round-trip
- [ ] Edge case: FB with `PUBLIC` or `PROTECTED` methods

---

## Phase 5: Polish & Ship

- [ ] Package as a standalone `.exe` (PyInstaller or Nuitka — no Python install required)
- [ ] Associate `.xml` file type with the app
- [ ] Add app icon
- [ ] Write `README.md` with screenshots and install/usage instructions
- [ ] Stakeholder review and sign-off

---

## Current Status

| Area | Status |
|---|---|
| XML → ST extraction | ✅ Complete |
| ST → XML patching | ✅ Complete |
| Round-trip fidelity | ✅ Byte-identical (both templates) |
| FB with methods | ✅ Complete |
| DUT structs | ✅ Complete |
| Desktop UI (incl. Copy ST, Clear All) | ✅ Complete |
| Syntax highlighting | ✅ Complete |
| FUNCTION / PROGRAM POUs | ⬜ Not started |
| GVL support | ⬜ Not started |
| Packaging / distribution | ⬜ Not started |

---

## Notes

- **Launch command**: `python src/main.py [optional: path/to/file.xml]`
- **Start fresh** when context gets noisy — begin a new session after a logical unit of work
- **Close the loop** — document completed features in [ai/docs/](ai/docs/)
- References: [PRD.md](PRD.md) · [CLAUDE.md](CLAUDE.md)
