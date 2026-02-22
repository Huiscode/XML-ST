"""
xml_parser.py
-------------
Loads TwinCAT 3 PLCopen XML exports, extracts editable ST content,
and patches modified ST content back — preserving the exact original
XML bytes for round-trip fidelity.

Supports three XML types:
  - FB      (Function Block):  <pous><pou pouType="functionBlock">
  - PROGRAM (Program):         <pous><pou pouType="program">
  - DUT     (Data Type/Struct): <dataTypes><dataType>
"""

import re
import html
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MethodInfo:
    name: str
    access: str          # "PRIVATE", "PUBLIC", etc.
    return_type: str     # e.g. "STRING", "BOOL"
    var_declaration: str # VAR ... END_VAR block text
    body: str            # ST body code


@dataclass
class ParsedXML:
    xml_type: str            # "FB" or "DUT"
    raw_bytes: bytes         # original file bytes (UTF-8)

    # FB / PROGRAM fields
    fb_declaration: str = ""   # full FUNCTION_BLOCK/PROGRAM ... END_VAR text
    fb_body: str = ""          # main body ST code
    methods: list = field(default_factory=list)  # list[MethodInfo]

    # DUT fields
    dut_declaration: str = ""  # full TYPE ... END_TYPE text


# ---------------------------------------------------------------------------
# XML entity helpers
# ---------------------------------------------------------------------------

def _unescape(text: str) -> str:
    """Convert XML entities in xhtml content to plain text characters."""
    return (text
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&apos;", "'")
            .replace("&quot;", '"'))


def _escape(text: str) -> str:
    """Escape plain text characters for embedding inside XML xhtml nodes."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# Low-level xhtml node extractor  (works on raw XML string)
# ---------------------------------------------------------------------------

def _extract_xhtml_blocks(raw: str) -> list[tuple[int, int, str]]:
    """
    Find all <xhtml ...>...</xhtml> blocks.
    Returns list of (start_idx, end_idx, content) where start/end span
    the full tag including <xhtml> and </xhtml>.
    """
    results = []
    # Match opening tag (may have namespace attr)
    pattern = re.compile(r'<xhtml(?:[^>]*)>(.*?)</xhtml>', re.DOTALL)
    for m in pattern.finditer(raw):
        results.append((m.start(), m.end(), m.group(1)))
    return results


# ---------------------------------------------------------------------------
# FB XML parser
# ---------------------------------------------------------------------------

def _parse_fb(raw: str) -> ParsedXML:
    """Parse a Function Block XML export."""

    # ------------------------------------------------------------------
    # 1. Extract the FB interface declaration (InterfaceAsPlainText)
    #    The first InterfaceAsPlainText in the file is the canonical one.
    # ------------------------------------------------------------------
    ipt_pattern = re.compile(
        r'<InterfaceAsPlainText>\s*<xhtml[^>]*>(.*?)</xhtml>\s*</InterfaceAsPlainText>',
        re.DOTALL
    )
    ipt_matches = list(ipt_pattern.finditer(raw))
    if not ipt_matches:
        raise ValueError("No InterfaceAsPlainText found in FB XML")

    fb_declaration = _unescape(ipt_matches[0].group(1))

    # ------------------------------------------------------------------
    # 2. Extract the FB body  (<body><ST><xhtml>...</xhtml></ST></body>)
    # ------------------------------------------------------------------
    body_pattern = re.compile(
        r'<body>\s*<ST>\s*<xhtml[^>]*>(.*?)</xhtml>\s*</ST>\s*</body>',
        re.DOTALL
    )
    body_match = body_pattern.search(raw)
    if not body_match:
        raise ValueError("No FB body found in XML")
    fb_body = _unescape(body_match.group(1))

    # ------------------------------------------------------------------
    # 3. Extract methods — match <Method name="...">...</Method> directly.
    #    This avoids the nested-</data> ambiguity problem.
    # ------------------------------------------------------------------
    method_block_pattern = re.compile(
        r'<Method\s+name="([^"]+)"[^>]*>(.*?)</Method>',
        re.DOTALL
    )

    methods = []
    for mb_match in method_block_pattern.finditer(raw):
        name = mb_match.group(1)
        method_block = mb_match.group(2)

        # Access modifier — look inside <interface><addData>
        access = "PUBLIC"
        priv_m = re.search(r'<AccessModifiers\s+Private="true"', method_block)
        if priv_m:
            access = "PRIVATE"

        # Return type — extracted from <returnType>
        rt_m = re.search(r'<returnType>\s*(.*?)\s*</returnType>', method_block, re.DOTALL)
        return_type = ""
        if rt_m:
            rt_inner = rt_m.group(1).strip()
            if re.search(r'<string\s*/>', rt_inner, re.IGNORECASE):
                return_type = "STRING"
            elif re.search(r'<BOOL\s*/>', rt_inner):
                return_type = "BOOL"
            else:
                der_m = re.search(r'<derived\s+name="([^"]+)"', rt_inner)
                if der_m:
                    return_type = der_m.group(1)
                else:
                    tag_m = re.search(r'<(\w+)\s*/>', rt_inner)
                    if tag_m:
                        return_type = tag_m.group(1)

        # Method InterfaceAsPlainText  (METHOD PRIVATE X : TYPE\nVAR...\nEND_VAR)
        # There are two: one inside <interface><addData> and one top-level.
        # Use the first occurrence.
        m_ipt = re.search(
            r'<InterfaceAsPlainText>\s*<xhtml[^>]*>(.*?)</xhtml>\s*</InterfaceAsPlainText>',
            method_block, re.DOTALL
        )
        var_declaration = _unescape(m_ipt.group(1)) if m_ipt else ""

        # Method body — <body><ST><xhtml>...</xhtml></ST></body>
        m_body = re.search(
            r'<body>\s*<ST>\s*<xhtml[^>]*>(.*?)</xhtml>\s*</ST>\s*</body>',
            method_block, re.DOTALL
        )
        body = _unescape(m_body.group(1)) if m_body else ""

        methods.append(MethodInfo(
            name=name,
            access=access,
            return_type=return_type,
            var_declaration=var_declaration,
            body=body,
        ))

    return ParsedXML(
        xml_type="FB",
        raw_bytes=raw.encode("utf-8"),
        fb_declaration=fb_declaration,
        fb_body=fb_body,
        methods=methods,
    )


# ---------------------------------------------------------------------------
# PROGRAM XML parser
# ---------------------------------------------------------------------------

def _parse_program(raw: str) -> ParsedXML:
    """Parse a Program POU XML export (no methods, just declaration + body)."""

    ipt_pattern = re.compile(
        r'<InterfaceAsPlainText>\s*<xhtml[^>]*>(.*?)</xhtml>\s*</InterfaceAsPlainText>',
        re.DOTALL
    )
    ipt_matches = list(ipt_pattern.finditer(raw))
    if not ipt_matches:
        raise ValueError("No InterfaceAsPlainText found in PROGRAM XML")

    fb_declaration = _unescape(ipt_matches[0].group(1))

    body_pattern = re.compile(
        r'<body>\s*<ST>\s*<xhtml[^>]*>(.*?)</xhtml>\s*</ST>\s*</body>',
        re.DOTALL
    )
    body_match = body_pattern.search(raw)
    if not body_match:
        raise ValueError("No body found in PROGRAM XML")
    fb_body = _unescape(body_match.group(1))

    return ParsedXML(
        xml_type="PROGRAM",
        raw_bytes=raw.encode("utf-8"),
        fb_declaration=fb_declaration,
        fb_body=fb_body,
        methods=[],
    )


# ---------------------------------------------------------------------------
# DUT XML parser
# ---------------------------------------------------------------------------

def _parse_dut(raw: str) -> ParsedXML:
    """Parse a DUT (Data Type / Struct) XML export."""

    ipt_pattern = re.compile(
        r'<InterfaceAsPlainText>\s*<xhtml[^>]*>(.*?)</xhtml>\s*</InterfaceAsPlainText>',
        re.DOTALL
    )
    ipt_match = ipt_pattern.search(raw)
    if not ipt_match:
        raise ValueError("No InterfaceAsPlainText found in DUT XML")

    return ParsedXML(
        xml_type="DUT",
        raw_bytes=raw.encode("utf-8"),
        dut_declaration=_unescape(ipt_match.group(1)),
    )


# ---------------------------------------------------------------------------
# Public load function
# ---------------------------------------------------------------------------

def load_xml(path: str) -> ParsedXML:
    """
    Load a TwinCAT PLCopen XML file and return a ParsedXML object.
    Detects FB vs DUT automatically.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Detect type
    if re.search(r'pouType\s*=\s*"functionBlock"', raw):
        parsed = _parse_fb(raw)
    elif re.search(r'pouType\s*=\s*"program"', raw):
        parsed = _parse_program(raw)
    elif re.search(r'<dataType\s+name=', raw):
        parsed = _parse_dut(raw)
    else:
        raise ValueError(
            "Unknown XML type: expected a functionBlock/program POU or a dataType DUT"
        )

    parsed.raw_bytes = raw.encode("utf-8")
    return parsed


# ---------------------------------------------------------------------------
# Patch functions — return new XML string with updated ST content
# ---------------------------------------------------------------------------

def _replace_xhtml_content(raw: str, pattern: re.Pattern, new_content: str,
                            count: int = 1) -> str:
    """
    Replace the inner content of xhtml nodes matched by pattern.
    Replaces exactly `count` occurrences (use count=0 for all).
    """
    replaced = 0

    def replacer(m):
        nonlocal replaced
        if count == 0 or replaced < count:
            replaced += 1
            # Reconstruct: opening tag + new content + closing tag
            full = m.group(0)
            # Find where content starts (after >) and ends (before </xhtml>)
            open_end = full.index('>') + 1
            close_start = full.rindex('</xhtml>')
            return full[:open_end] + _escape(new_content) + full[close_start:]
        return m.group(0)

    return pattern.sub(replacer, raw)


def patch_xml(parsed: ParsedXML,
              new_declaration: str,
              new_body: str,
              new_methods: list) -> str:
    """
    Given updated ST content, patch it back into the original XML string.

    Strategy (for exact round-trip):
      - Split raw XML at the first <Method name= tag.
      - Patch the FB InterfaceAsPlainText blocks (all identical) in the PRE section.
      - Patch the FB body in the PRE section.
      - Patch each <Method>...</Method> block individually.
      - Recombine.

    For DUT: only the single InterfaceAsPlainText is patched.
    """
    raw = parsed.raw_bytes.decode("utf-8")

    # ------------------------------------------------------------------ DUT
    if parsed.xml_type in ("DUT",):
        ipt_xhtml = re.compile(
            r'(<InterfaceAsPlainText>\s*<xhtml[^>]*>)(.*?)'
            r'(</xhtml>\s*</InterfaceAsPlainText>)',
            re.DOTALL
        )
        escaped_decl = _escape(new_declaration)
        patched, n = ipt_xhtml.subn(
            lambda m: m.group(1) + escaped_decl + m.group(3),
            raw, count=1
        )
        return patched

    # ------------------------------------------------------------------ FB
    # Split raw XML into:
    #   pre_section  — everything before the first <Method name=
    #   method_tags  — list of (full_method_string) in order
    #   post_section — everything after the last </Method>

    method_spans = [(m.start(), m.end())
                    for m in re.finditer(r'<Method\s+name="[^"]+"[^>]*>.*?</Method>',
                                         raw, re.DOTALL)]

    if not method_spans:
        # No methods — patch FB declaration + body in the whole document
        pre_section = raw
        post_section = ""
        method_raws = []
    else:
        pre_section  = raw[:method_spans[0][0]]
        post_section = raw[method_spans[-1][1]:]
        method_raws  = [raw[s:e] for s, e in method_spans]

    # --- Patch FB InterfaceAsPlainText (ALL occurrences in pre_section) ---
    ipt_xhtml = re.compile(
        r'(<InterfaceAsPlainText>\s*<xhtml[^>]*>)(.*?)'
        r'(</xhtml>\s*</InterfaceAsPlainText>)',
        re.DOTALL
    )
    escaped_decl = _escape(new_declaration)
    pre_section = ipt_xhtml.sub(
        lambda m: m.group(1) + escaped_decl + m.group(3),
        pre_section
    )

    # --- Patch FB body (first <body><ST><xhtml> in pre_section) ---
    body_xhtml = re.compile(
        r'(<body>\s*<ST>\s*<xhtml[^>]*>)(.*?)(</xhtml>\s*</ST>\s*</body>)',
        re.DOTALL
    )
    escaped_body = _escape(new_body)
    pre_section, _ = body_xhtml.subn(
        lambda m: m.group(1) + escaped_body + m.group(3),
        pre_section, count=1
    )

    # --- Patch each Method block ---
    patched_methods = []
    for idx, method_raw in enumerate(method_raws):
        if idx < len(new_methods):
            minfo = new_methods[idx]
            escaped_var  = _escape(minfo.var_declaration)
            escaped_mbody = _escape(minfo.body)

            # Replace all InterfaceAsPlainText inside this method
            method_raw = ipt_xhtml.sub(
                lambda m: m.group(1) + escaped_var + m.group(3),
                method_raw
            )

            # Replace the method body (<body><ST><xhtml>)
            method_raw, _ = body_xhtml.subn(
                lambda m: m.group(1) + escaped_mbody + m.group(3),
                method_raw, count=1
            )

            # Replace the top-level <InterfaceAsPlainText> that appears AFTER </body>
            # inside the Method block (some TwinCAT versions add a second one)
            top_ipt = re.compile(
                r'(</body>\s*<InterfaceAsPlainText>\s*<xhtml[^>]*>)(.*?)'
                r'(</xhtml>\s*</InterfaceAsPlainText>)',
                re.DOTALL
            )
            method_raw = top_ipt.sub(
                lambda m: m.group(1) + escaped_var + m.group(3),
                method_raw
            )

        patched_methods.append(method_raw)

    # Reconstruct: pre + methods (interleaved with their surrounding XML) + post
    # We need to also preserve the XML between/around the method blocks
    if method_spans:
        # Collect the gaps between method blocks
        between = []
        prev_end = method_spans[0][0]  # pre_section ends here
        for i, (s, e) in enumerate(method_spans):
            if i > 0:
                between.append(raw[method_spans[i-1][1]:s])

        # Rebuild: pre + (gap + method) * n + post
        result = pre_section
        for i, pm in enumerate(patched_methods):
            if i > 0:
                result += between[i - 1]
            result += pm
        result += post_section
    else:
        result = pre_section

    return result


# ---------------------------------------------------------------------------
# Build XML from scratch (no template needed)
# ---------------------------------------------------------------------------

_IEC_PRIMITIVES = {
    'BOOL', 'BYTE', 'WORD', 'DWORD', 'LWORD',
    'SINT', 'INT', 'DINT', 'LINT',
    'USINT', 'UINT', 'UDINT', 'ULINT',
    'REAL', 'LREAL',
    'TIME', 'DATE', 'TIME_OF_DAY', 'DATE_AND_TIME',
}


def _return_type_tag(rt: str) -> str:
    """Generate the XML tag for a method return type."""
    if not rt:
        return '<BOOL />'
    up = rt.upper()
    if up == 'STRING':
        return '<string />'
    if up == 'WSTRING':
        return '<wstring />'
    if up in _IEC_PRIMITIVES:
        return f'<{up} />'
    return f'<derived name="{rt}" />'


def detect_st_type(st_text: str) -> tuple:
    """
    Detect POU type and name from ST text.
    Returns (xml_type, pou_name).
    """
    m = re.search(r'^\s*FUNCTION_BLOCK\s+(\w+)', st_text, re.MULTILINE | re.IGNORECASE)
    if m:
        return ('FB', m.group(1))
    m = re.search(r'^\s*PROGRAM\s+(\w+)', st_text, re.MULTILINE | re.IGNORECASE)
    if m:
        return ('PROGRAM', m.group(1))
    m = re.search(r'^\s*TYPE\s+(\w+)\s*:', st_text, re.MULTILINE | re.IGNORECASE)
    if m:
        return ('DUT', m.group(1))
    raise ValueError(
        "Cannot detect POU type from ST text.\n"
        "Expected FUNCTION_BLOCK, PROGRAM, or TYPE declaration."
    )


def _xml_header(now: str) -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<project xmlns="http://www.plcopen.org/xml/tc6_0200">
  <fileHeader companyName="" productName="TwinCAT PLC Control" productVersion="3.5.21.20" creationDateTime="{now}" />
  <contentHeader name="PLC1" modificationDateTime="{now}">
    <coordinateInfo>
      <fbd>
        <scaling x="1" y="1" />
      </fbd>
      <ld>
        <scaling x="1" y="1" />
      </ld>
      <sfc>
        <scaling x="1" y="1" />
      </sfc>
    </coordinateInfo>
    <addData>
      <data name="http://www.3s-software.com/plcopenxml/projectinformation" handleUnknown="implementation">
        <ProjectInformation />
      </data>
    </addData>
  </contentHeader>'''


def _build_method_block(minfo: MethodInfo, obj_id: str) -> str:
    """Build a single <Method> XML block."""
    rt_tag = _return_type_tag(minfo.return_type)
    escaped_var = _escape(minfo.var_declaration)
    escaped_body = _escape(minfo.body)

    access_xml = ''
    if minfo.access.upper() == 'PRIVATE':
        access_xml = (
            '\n                <addData>'
            '\n                  <data name="http://www.3s-software.com/plcopenxml/accessmodifiers" handleUnknown="implementation">'
            '\n                    <AccessModifiers Private="true" />'
            '\n                  </data>'
            '\n                </addData>'
        )

    return (
        f'          <data name="http://www.3s-software.com/plcopenxml/method" handleUnknown="implementation">\n'
        f'            <Method name="{minfo.name}" ObjectId="{obj_id}">\n'
        f'              <interface>\n'
        f'                <returnType>\n'
        f'                  {rt_tag}\n'
        f'                </returnType>\n'
        f'                <localVars>\n'
        f'                  <addData>\n'
        f'                    <data name="http://www.3s-software.com/plcopenxml/interfaceasplaintext" handleUnknown="implementation">\n'
        f'                      <InterfaceAsPlainText>\n'
        f'                        <xhtml xmlns="http://www.w3.org/1999/xhtml">{escaped_var}</xhtml>\n'
        f'                      </InterfaceAsPlainText>\n'
        f'                    </data>\n'
        f'                  </addData>\n'
        f'                </localVars>{access_xml}\n'
        f'              </interface>\n'
        f'              <body>\n'
        f'                <ST>\n'
        f'                  <xhtml xmlns="http://www.w3.org/1999/xhtml">{escaped_body}</xhtml>\n'
        f'                </ST>\n'
        f'              </body>\n'
        f'              <InterfaceAsPlainText>\n'
        f'                <xhtml xmlns="http://www.w3.org/1999/xhtml">{escaped_var}</xhtml>\n'
        f'              </InterfaceAsPlainText>\n'
        f'              <addData />\n'
        f'            </Method>\n'
        f'          </data>\n'
    )


def build_xml_from_st(xml_type: str, pou_name: str,
                       declaration: str, body: str,
                       methods: list) -> str:
    """
    Build a complete PLCopen XML string from ST parts — no template needed.
    The generated XML is compatible with TwinCAT 3 import.
    """
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.0000000')
    header = _xml_header(now)
    escaped_decl = _escape(declaration)

    # ---- DUT ----
    if xml_type == 'DUT':
        obj_id = str(uuid.uuid4())
        return (
            f'{header}\n'
            f'  <types>\n'
            f'    <dataTypes>\n'
            f'      <dataType name="{pou_name}">\n'
            f'        <baseType>\n'
            f'          <struct />\n'
            f'        </baseType>\n'
            f'        <addData>\n'
            f'          <data name="http://www.3s-software.com/plcopenxml/interfaceasplaintext" handleUnknown="implementation">\n'
            f'            <InterfaceAsPlainText>\n'
            f'              <xhtml xmlns="http://www.w3.org/1999/xhtml">{escaped_decl}</xhtml>\n'
            f'            </InterfaceAsPlainText>\n'
            f'          </data>\n'
            f'          <data name="http://www.3s-software.com/plcopenxml/objectid" handleUnknown="discard">\n'
            f'            <ObjectId>{obj_id}</ObjectId>\n'
            f'          </data>\n'
            f'        </addData>\n'
            f'      </dataType>\n'
            f'    </dataTypes>\n'
            f'    <pous />\n'
            f'  </types>\n'
            f'  <instances>\n'
            f'    <configurations />\n'
            f'  </instances>\n'
            f'  <addData>\n'
            f'    <data name="http://www.3s-software.com/plcopenxml/projectstructure" handleUnknown="discard">\n'
            f'      <ProjectStructure>\n'
            f'        <Object Name="{pou_name}" ObjectId="{obj_id}" />\n'
            f'      </ProjectStructure>\n'
            f'    </data>\n'
            f'  </addData>\n'
            f'</project>'
        )

    # ---- FB / PROGRAM ----
    pou_type = 'functionBlock' if xml_type == 'FB' else 'program'
    escaped_body = _escape(body)
    pou_obj_id = str(uuid.uuid4())

    # Build method blocks and track IDs for ProjectStructure
    methods_xml = ''
    method_ids = []
    for minfo in methods:
        m_id = str(uuid.uuid4())
        method_ids.append((minfo.name, m_id))
        methods_xml += _build_method_block(minfo, m_id)

    # ProjectStructure object (self-closing if no children)
    if method_ids:
        children = ''.join(
            f'\n          <Object Name="{n}" ObjectId="{i}" />'
            for n, i in method_ids
        )
        project_obj = (
            f'        <Object Name="{pou_name}" ObjectId="{pou_obj_id}">'
            f'{children}\n'
            f'        </Object>'
        )
    else:
        project_obj = f'        <Object Name="{pou_name}" ObjectId="{pou_obj_id}" />'

    return (
        f'{header}\n'
        f'  <types>\n'
        f'    <dataTypes />\n'
        f'    <pous>\n'
        f'      <pou name="{pou_name}" pouType="{pou_type}">\n'
        f'        <interface>\n'
        f'          <localVars>\n'
        f'            <addData>\n'
        f'              <data name="http://www.3s-software.com/plcopenxml/interfaceasplaintext" handleUnknown="implementation">\n'
        f'                <InterfaceAsPlainText>\n'
        f'                  <xhtml xmlns="http://www.w3.org/1999/xhtml">{escaped_decl}</xhtml>\n'
        f'                </InterfaceAsPlainText>\n'
        f'              </data>\n'
        f'            </addData>\n'
        f'          </localVars>\n'
        f'        </interface>\n'
        f'        <body>\n'
        f'          <ST>\n'
        f'            <xhtml xmlns="http://www.w3.org/1999/xhtml">{escaped_body}</xhtml>\n'
        f'          </ST>\n'
        f'        </body>\n'
        f'        <addData>\n'
        f'{methods_xml}'
        f'          <data name="http://www.3s-software.com/plcopenxml/interfaceasplaintext" handleUnknown="implementation">\n'
        f'            <InterfaceAsPlainText>\n'
        f'              <xhtml xmlns="http://www.w3.org/1999/xhtml">{escaped_decl}</xhtml>\n'
        f'            </InterfaceAsPlainText>\n'
        f'          </data>\n'
        f'          <data name="http://www.3s-software.com/plcopenxml/objectid" handleUnknown="discard">\n'
        f'            <ObjectId>{pou_obj_id}</ObjectId>\n'
        f'          </data>\n'
        f'        </addData>\n'
        f'      </pou>\n'
        f'    </pous>\n'
        f'  </types>\n'
        f'  <instances>\n'
        f'    <configurations />\n'
        f'  </instances>\n'
        f'  <addData>\n'
        f'    <data name="http://www.3s-software.com/plcopenxml/projectstructure" handleUnknown="discard">\n'
        f'      <ProjectStructure>\n'
        f'{project_obj}\n'
        f'      </ProjectStructure>\n'
        f'    </data>\n'
        f'  </addData>\n'
        f'</project>'
    )
