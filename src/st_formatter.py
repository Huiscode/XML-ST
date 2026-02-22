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

from xml_parser import ParsedXML, MethodInfo

DIVIDER = "// " + "=" * 60

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

    # FB declaration (VAR_INPUT / VAR_OUTPUT / VAR blocks)
    parts.append(parsed.fb_declaration.rstrip())

    # FB body
    parts.append("")
    parts.append("// === FB Body ===")
    parts.append(parsed.fb_body.rstrip())

    # Methods — body is NOT stripped so whitespace round-trips exactly.
    # The body's own leading newline provides visual separation from END_VAR.
    for minfo in parsed.methods:
        parts.append("")
        parts.append(DIVIDER)
        parts.append(_method_header(minfo))
        parts.append(DIVIDER)
        var_decl = minfo.var_declaration.strip()
        if var_decl:
            parts.append(var_decl)
        # Append body preserving original whitespace (leading \n gives blank line)
        if minfo.body:
            parts.append(minfo.body)

    return "\n".join(parts)
