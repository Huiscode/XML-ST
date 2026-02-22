"""
st_formatter.py
---------------
Combines extracted ST pieces from xml_parser into a single display string,
and defines the divider/header format used to separate FB body from methods.

Divider format (machine-parseable for the splitter):
    // ============================================================
    // Method: M_Filename | PRIVATE | STRING
    // ============================================================

The pipe-delimited header line carries metadata for round-trip reconstruction.
"""

import re

from xml_parser import ParsedXML, MethodInfo

DIVIDER = "// " + "=" * 60

_VAR_OPEN  = re.compile(r'^\s*(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_GLOBAL|VAR_EXTERNAL|VAR)\s*$', re.IGNORECASE)
_VAR_CLOSE = re.compile(r'^\s*END_VAR\s*$', re.IGNORECASE)


def _indent_var_blocks(text: str) -> str:
    """Ensure every variable line inside a VAR block is indented with 4 spaces."""
    lines = text.split('\n')
    result = []
    in_var = False
    for line in lines:
        if _VAR_OPEN.match(line):
            in_var = True
            result.append(line)
        elif _VAR_CLOSE.match(line):
            in_var = False
            result.append(line)
        elif in_var and line.strip() and not line.startswith('    '):
            result.append('    ' + line.lstrip())
        else:
            result.append(line)
    return '\n'.join(result)


def _method_header(minfo: MethodInfo) -> str:
    """Single comment line encoding method metadata."""
    return f"// Method: {minfo.name} | {minfo.access} | {minfo.return_type}"


def format_st(parsed: ParsedXML) -> str:
    """
    Convert a ParsedXML into a single editable ST text string.

    FB layout:
        <declaration block>

        // === FB Body ===
        <body code>

        // ============================================================
        // Method: M_Filename | PRIVATE | STRING
        // ============================================================
        <method VAR declaration>
        <blank line>
        <method body>

        (repeated for each method)

    DUT layout:
        <declaration text>
    """
    if parsed.xml_type == "DUT":
        return parsed.dut_declaration

    parts = []

    # Declaration block (normalise VAR indentation if source has none)
    parts.append(_indent_var_blocks(parsed.fb_declaration.rstrip()))

    # Body marker — differs by POU type so the editor label is meaningful
    body_marker = "// === PROGRAM Body ===" if parsed.xml_type == "PROGRAM" else "// === FB Body ==="
    parts.append("")
    parts.append(body_marker)
    parts.append(parsed.fb_body.rstrip())

    # Methods — body is NOT stripped so whitespace round-trips exactly.
    # The body's own leading newline provides visual separation from END_VAR.
    for minfo in parsed.methods:
        parts.append("")
        parts.append(DIVIDER)
        parts.append(_method_header(minfo))
        parts.append(DIVIDER)
        var_decl = _indent_var_blocks(minfo.var_declaration.strip())
        if var_decl:
            parts.append(var_decl)
        # Append body preserving original whitespace (leading \n gives blank line)
        if minfo.body:
            parts.append(minfo.body)

    return "\n".join(parts)
