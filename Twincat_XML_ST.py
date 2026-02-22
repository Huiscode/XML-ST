"""PLCopen XML <-> TwinCAT 3 Structured Text Converter.

Bidirectional converter:
  - XML to ST: Opens PLCopen XML, extracts Structured Text, saves as .txt
  - ST to XML: Opens .txt with ST code, builds PLCopen XML, saves as .xml
"""

import io
import os
import re
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
from datetime import datetime

# =============================================================================
# Namespace constants (shared by both directions)
# =============================================================================
NS = {
    'plc': 'http://www.plcopen.org/xml/tc6_0200',
    'xhtml': 'http://www.w3.org/1999/xhtml',
}

NS_PLC = 'http://www.plcopen.org/xml/tc6_0200'
NS_XH = 'http://www.w3.org/1999/xhtml'
NS_INTERFACE = 'http://www.3s-software.com/plcopenxml/interfaceasplaintext'
NS_METHOD = 'http://www.3s-software.com/plcopenxml/method'
NS_OBJID = 'http://www.3s-software.com/plcopenxml/objectid'
NS_PROJ = 'http://www.3s-software.com/plcopenxml/projectstructure'
NS_PINFO = 'http://www.3s-software.com/plcopenxml/projectinformation'

# IEC 61131-3 primitive types that map to simple XML elements like <BOOL/>
PRIMITIVES = {
    'BOOL', 'BYTE', 'WORD', 'DWORD', 'LWORD',
    'SINT', 'INT', 'DINT', 'LINT',
    'USINT', 'UINT', 'UDINT', 'ULINT',
    'REAL', 'LREAL',
    'TIME', 'LTIME', 'DATE', 'TOD', 'DT',
    'STRING', 'WSTRING',
}

# POU keyword to XML pouType attribute mapping
POU_TYPES = {
    'FUNCTION_BLOCK': 'functionBlock',
    'PROGRAM': 'program',
    'FUNCTION': 'function',
}

# VAR section keyword to XML element tag mapping
VAR_TAGS = {
    'VAR_INPUT': 'inputVars',
    'VAR_OUTPUT': 'outputVars',
    'VAR_IN_OUT': 'inOutVars',
    'VAR': 'localVars',
}


# =============================================================================
# XML to ST (existing functionality)
# =============================================================================

def get_xhtml_text(element):
    """Extract text from an xhtml element, stripping leading/trailing whitespace."""
    if element is None:
        return ''
    node = element.find('xhtml:xhtml', NS)
    if node is None:
        return ''
    return (node.text or '').strip()


def get_body_st(element):
    """Extract body > ST > xhtml text from a POU or Method element."""
    body = element.find('plc:body/plc:ST/xhtml:xhtml', NS)
    if body is None:
        return ''
    return (body.text or '').strip()


def extract_single_method(method_element):
    """Extract one method: declaration text + body ST code."""
    name = method_element.get('name', 'Unknown')

    # Method declaration from InterfaceAsPlainText directly under Method
    decl_node = method_element.find('plc:InterfaceAsPlainText', NS)
    if decl_node is None:
        # Fallback: look inside interface > localVars > addData
        decl_node = method_element.find(
            f"plc:interface/plc:localVars/plc:addData/"
            f"plc:data[@name='{NS_INTERFACE}']/plc:InterfaceAsPlainText", NS
        )
    declaration = get_xhtml_text(decl_node) if decl_node is not None else f'METHOD {name}'

    body = get_body_st(method_element)

    parts = [f'// === Method: {name} ===']
    parts.append(declaration)
    if body:
        parts.append(body)

    return '\n'.join(parts)


def extract_methods(pou_element):
    """Find all Method elements in a POU and format them."""
    method_xpath = f"plc:addData/plc:data[@name='{NS_METHOD}']/plc:Method"
    methods = pou_element.findall(method_xpath, NS)

    parts = []
    for method in methods:
        parts.append(extract_single_method(method))
    return '\n\n'.join(parts)


def _ensure_var_indentation(declaration):
    """Ensure variable lines inside VAR blocks have 4-space indentation.

    Processes declaration text line-by-line: lines between VAR_xxx and END_VAR
    that are not already indented get 4 spaces prepended.
    """
    lines = declaration.split('\n')
    result = []
    in_var = False

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()

        if upper in VAR_TAGS or upper == 'VAR':
            in_var = True
            result.append(stripped)
        elif upper == 'END_VAR':
            in_var = False
            result.append(stripped)
        elif in_var and stripped:
            # Add 4-space indent if not already indented
            if not line.startswith('    ') and not line.startswith('\t'):
                result.append('    ' + stripped)
            else:
                result.append(line.rstrip())
        else:
            result.append(line.rstrip())

    return '\n'.join(result)


def extract_pou(pou_element):
    """Extract one POU: declaration + body + methods."""
    # Get POU-level InterfaceAsPlainText
    decl_xpath = (
        f"plc:addData/plc:data[@name='{NS_INTERFACE}']/"
        f"plc:InterfaceAsPlainText"
    )
    decl_node = pou_element.find(decl_xpath, NS)
    declaration = get_xhtml_text(decl_node)

    if not declaration:
        # Fallback: try inside inputVars addData
        decl_node = pou_element.find(
            f"plc:interface/plc:inputVars/plc:addData/"
            f"plc:data[@name='{NS_INTERFACE}']/plc:InterfaceAsPlainText", NS
        )
        declaration = get_xhtml_text(decl_node)

    # Ensure consistent 4-space indentation in VAR blocks
    if declaration:
        declaration = _ensure_var_indentation(declaration)

    body = get_body_st(pou_element)
    methods = extract_methods(pou_element)

    parts = []
    if declaration:
        parts.append(declaration)
    if body:
        parts.append('\n// === Body ===')
        parts.append(body)
    if methods:
        parts.append('')
        parts.append(methods)

    return '\n'.join(parts)


def parse_xml_file(filepath):
    """Parse a PLCopen XML file and return combined ST text for all POUs."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    pous = root.findall('.//plc:pous/plc:pou', NS)
    if not pous:
        raise ValueError('No POUs found in the XML file.')

    results = []
    for pou in pous:
        results.append(extract_pou(pou))

    return '\n\n'.join(results)


# =============================================================================
# ST to XML (new functionality)
# =============================================================================

def _tag(ns, name):
    """Build a namespace-qualified XML tag: {namespace}localname."""
    return f'{{{ns}}}{name}'


def _parse_pou_header(line):
    """Parse a POU header line like 'FUNCTION_BLOCK FB_Name'.

    Returns (xml_pou_type, pou_name) or (None, None) if not a POU header.
    """
    stripped = line.strip()
    for keyword, xml_type in POU_TYPES.items():
        if stripped.upper().startswith(keyword + ' ') or stripped.upper() == keyword:
            name = stripped[len(keyword):].strip()
            return xml_type, name
    return None, None


def _parse_type_str(type_str):
    """Parse a type string into a structured dict.

    Returns dict with 'kind' key:
      'primitive'    -> {'kind': 'primitive', 'name': 'BOOL'}
      'derived'      -> {'kind': 'derived', 'name': 'TON'}
      'string_sized' -> {'kind': 'string_sized', 'length': 255}
      'array'        -> {'kind': 'array', 'lower': 1, 'upper': 100, 'base_type': {...}}
    """
    type_str = type_str.strip()

    # ARRAY[lower..upper] OF BaseType
    m = re.match(
        r'ARRAY\s*\[\s*(\d+)\s*\.\.\s*(\d+)\s*\]\s+OF\s+(.+)',
        type_str, re.IGNORECASE,
    )
    if m:
        return {
            'kind': 'array',
            'lower': int(m.group(1)),
            'upper': int(m.group(2)),
            'base_type': _parse_type_str(m.group(3).strip()),
        }

    # STRING(length) or WSTRING(length)
    m = re.match(r'(W?STRING)\s*\(\s*(\d+)\s*\)', type_str, re.IGNORECASE)
    if m:
        return {'kind': 'string_sized', 'name': m.group(1).upper(), 'length': int(m.group(2))}

    # Primitive type (BOOL, INT, REAL, TIME, STRING, etc.)
    if type_str.upper() in PRIMITIVES:
        return {'kind': 'primitive', 'name': type_str.upper()}

    # Derived / user-defined type (TON, R_TRIG, ST_BatchMetadata, FB_Xxx, etc.)
    return {'kind': 'derived', 'name': type_str}


def _parse_variable_line(line):
    """Parse a single variable declaration line.

    Handles formats like:
      bEnable           : BOOL;
      aData AT %I*      : ARRAY[1..100] OF REAL; // comment
      nState            : INT := 0;
      sDir              : STRING := 'C:\\Path\\';
      sDoc              : STRING(2000000);

    Returns a dict with keys: name, at_mapping, type_str, type_info,
    initial_value, comment.  Returns None if the line is not a variable declaration.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith('//'):
        return None
    if ';' not in stripped:
        return None

    # --- Separate trailing inline comment ---
    # Find '//' that is not inside a single-quoted string literal
    comment = None
    in_quote = False
    comment_pos = -1
    for idx in range(len(stripped) - 1):
        if stripped[idx] == "'":
            in_quote = not in_quote
        elif not in_quote and stripped[idx] == '/' and stripped[idx + 1] == '/':
            comment_pos = idx
            break
    if comment_pos >= 0:
        comment = stripped[comment_pos + 2:].strip()
        stripped = stripped[:comment_pos].strip()

    # --- Remove trailing semicolon ---
    if stripped.endswith(';'):
        stripped = stripped[:-1].strip()
    else:
        return None

    # --- Find the type-separator colon (first ':' not followed by '=') ---
    colon_pos = -1
    for idx in range(len(stripped)):
        if stripped[idx] == ':' and (idx + 1 >= len(stripped) or stripped[idx + 1] != '='):
            colon_pos = idx
            break
    if colon_pos < 0:
        return None

    left = stripped[:colon_pos].strip()
    right = stripped[colon_pos + 1:].strip()

    # --- Parse left side: name [AT %I*] ---
    at_mapping = None
    parts = left.split()
    name = parts[0]
    if len(parts) >= 3 and parts[1].upper() == 'AT':
        at_mapping = parts[2]

    # --- Parse right side: type [:= initial_value] ---
    initial_value = None
    assign_pos = right.find(':=')
    if assign_pos >= 0:
        type_str = right[:assign_pos].strip()
        initial_value = right[assign_pos + 2:].strip()
    else:
        type_str = right.strip()

    return {
        'name': name,
        'at_mapping': at_mapping,
        'type_str': type_str,
        'type_info': _parse_type_str(type_str),
        'initial_value': initial_value,
        'comment': comment,
    }


def _parse_var_sections(lines):
    """Parse VAR_INPUT / VAR_OUTPUT / VAR / END_VAR blocks from declaration lines.

    Returns a list of (xml_section_tag, [variable_dicts]).
    """
    sections = []
    current_tag = None
    current_vars = []

    for line in lines:
        stripped = line.strip().upper()

        # Check for VAR section start keyword
        matched_kw = False
        for kw, tag in VAR_TAGS.items():
            if stripped == kw:
                current_tag = tag
                current_vars = []
                matched_kw = True
                break
        if matched_kw:
            continue

        # Check for END_VAR
        if stripped == 'END_VAR' and current_tag:
            sections.append((current_tag, current_vars))
            current_tag = None
            current_vars = []
            continue

        # Inside a VAR section: try to parse variable declarations
        if current_tag:
            var = _parse_variable_line(line)
            if var:
                current_vars.append(var)

    return sections


def _parse_method_section(lines):
    """Parse a method section starting from a marker comment or METHOD keyword.

    Returns dict with: name, access, return_type, declaration_text,
    var_sections, body_text.
    """
    method_name = 'Unknown'
    access = None
    return_type = None
    method_line_idx = -1

    # Search all lines for the METHOD keyword (it may be the first line
    # or appear after comment lines)
    for i, line in enumerate(lines):
        m = re.match(
            r'METHOD\s+(?:(PRIVATE|PUBLIC|PROTECTED|INTERNAL)\s+)?(\w+)(?:\s*:\s*(.+))?',
            line.strip(), re.IGNORECASE,
        )
        if m:
            access = m.group(1)
            method_name = m.group(2)
            return_type = m.group(3).strip() if m.group(3) else None
            method_line_idx = i
            break

    if method_line_idx < 0:
        return {
            'name': method_name,
            'access': None,
            'return_type': None,
            'declaration_text': f'METHOD {method_name}',
            'var_sections': [],
            'body_text': '\n'.join(lines[1:]).strip(),
        }

    # Find the last END_VAR after the METHOD line (end of method declaration)
    last_end_var = method_line_idx
    for i, line in enumerate(lines[method_line_idx:], method_line_idx):
        if line.strip().upper() == 'END_VAR':
            last_end_var = i

    # Declaration = from METHOD line through last END_VAR
    decl_end = last_end_var + 1 if last_end_var > method_line_idx else method_line_idx + 1
    decl_lines = lines[method_line_idx:decl_end]
    declaration_text = '\n'.join(l for l in decl_lines if l.strip())

    # Parse VAR sections within the method declaration
    var_sections = _parse_var_sections(decl_lines)

    # Body = everything after the declaration
    body_text = '\n'.join(lines[decl_end:]).strip()

    return {
        'name': method_name,
        'access': access,
        'return_type': return_type,
        'declaration_text': declaration_text,
        'var_sections': var_sections,
        'body_text': body_text,
    }


def _build_declaration_text(decl_lines):
    """Build clean declaration text for InterfaceAsPlainText.

    Keeps: POU header, VAR section markers, variable lines (with inline comments),
    END_VAR markers.  Preserves original indentation on variable lines.
    Strips: standalone comment lines, blank lines.
    """
    result = []
    in_var = False

    for line in decl_lines:
        stripped = line.strip()
        if not stripped:
            continue

        # POU header line
        pt, _ = _parse_pou_header(stripped)
        if pt:
            result.append(stripped)
            continue

        upper = stripped.upper()

        # VAR section start
        if upper in VAR_TAGS:
            result.append(stripped)
            in_var = True
            continue

        # END_VAR
        if upper == 'END_VAR':
            result.append(stripped)
            in_var = False
            continue

        # Inside VAR: keep variable lines with 4-space indentation
        # (TwinCAT standard), skip standalone comments
        if in_var and not stripped.startswith('//'):
            # Ensure consistent 4-space indent regardless of source formatting
            if not line.startswith('    ') and not line.startswith('\t'):
                result.append('    ' + stripped)
            else:
                result.append(line.rstrip())

    return '\n'.join(result) + '\n'


def parse_st_text(st_text):
    """Parse ST text into structured POU data for XML generation.

    Returns a dict with keys:
      pou_type         : 'functionBlock' | 'program' | 'function'
      pou_name         : str
      declaration_text : str (clean declaration for InterfaceAsPlainText)
      var_sections     : list of (xml_tag, [variable_dicts])
      body_text        : str
      methods          : list of method dicts
    """
    lines = st_text.split('\n')

    # --- Find POU header ---
    pou_type = None
    pou_name = None
    header_idx = -1

    for i, line in enumerate(lines):
        pt, pn = _parse_pou_header(line)
        if pt:
            pou_type = pt
            pou_name = pn
            header_idx = i
            break

    if not pou_type:
        raise ValueError(
            'No POU header found.\n'
            'The text must contain FUNCTION_BLOCK, PROGRAM, or FUNCTION.'
        )

    # --- Locate body marker and method markers ---
    body_idx = None
    method_indices = []
    last_decl_end_var = -1

    # First pass: find body marker and last END_VAR in the declaration area
    for i, line in enumerate(lines[header_idx:], header_idx):
        stripped = line.strip()
        # Detect body marker in various formats:
        #   // === Body ===          (original XML->ST format)
        #   // BODY                  (commented format)
        #   // =============...      before BODY heading
        if '// === Body ===' in stripped or stripped.upper() == '// BODY':
            body_idx = i
            break
        if stripped.upper() == 'END_VAR':
            last_decl_end_var = i

    # Second pass: find method boundaries
    # First collect // === Method: markers (these take priority)
    marker_indices = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'//\s*===\s*Method:', stripped):
            method_indices.append(i)
            marker_indices.add(i)

    # Then detect bare METHOD keyword lines, but only if no marker exists
    # within 30 lines before this METHOD line (avoids duplicates)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'METHOD\s+(?:(?:PRIVATE|PUBLIC|PROTECTED|INTERNAL)\s+)?\w+', stripped, re.IGNORECASE):
            boundary = body_idx if body_idx is not None else last_decl_end_var
            if boundary >= 0 and i > boundary:
                # Check no existing marker is nearby (within 30 lines before)
                has_nearby_marker = any(
                    mi in marker_indices and (i - mi) < 30 and (i - mi) >= 0
                    for mi in method_indices
                )
                if not has_nearby_marker:
                    method_indices.append(i)

    method_indices.sort()

    # --- Extract declaration lines (header to body/method/end) ---
    decl_end = body_idx or (method_indices[0] if method_indices else len(lines))
    decl_lines = lines[header_idx:decl_end]

    declaration_text = _build_declaration_text(decl_lines)
    var_sections = _parse_var_sections(decl_lines)

    # --- Extract body text ---
    body_text = ''
    if body_idx is not None:
        body_end = method_indices[0] if method_indices else len(lines)
        body_text = '\n'.join(lines[body_idx + 1 : body_end]).strip()

    # --- Extract methods ---
    methods = []
    for idx, mi in enumerate(method_indices):
        end = method_indices[idx + 1] if idx + 1 < len(method_indices) else len(lines)
        methods.append(_parse_method_section(lines[mi:end]))

    return {
        'pou_type': pou_type,
        'pou_name': pou_name,
        'declaration_text': declaration_text,
        'var_sections': var_sections,
        'body_text': body_text,
        'methods': methods,
    }


# --- XML element builders ---

def _add_iface_adddata(parent, decl_text):
    """Add the addData > data > InterfaceAsPlainText > xhtml subtree."""
    add = ET.SubElement(parent, _tag(NS_PLC, 'addData'))
    data = ET.SubElement(add, _tag(NS_PLC, 'data'))
    data.set('name', NS_INTERFACE)
    data.set('handleUnknown', 'implementation')
    ipt = ET.SubElement(data, _tag(NS_PLC, 'InterfaceAsPlainText'))
    xh = ET.SubElement(ipt, _tag(NS_XH, 'xhtml'))
    xh.text = decl_text


def _build_type_xml(parent, type_info):
    """Build the XML type structure inside a <type> element."""
    kind = type_info['kind']

    if kind == 'primitive':
        # TwinCAT uses lowercase <string/> and <wstring/> but uppercase for all others
        tag_name = type_info['name']
        if tag_name in ('STRING', 'WSTRING'):
            tag_name = tag_name.lower()
        ET.SubElement(parent, _tag(NS_PLC, tag_name))

    elif kind == 'derived':
        d = ET.SubElement(parent, _tag(NS_PLC, 'derived'))
        d.set('name', type_info['name'])

    elif kind == 'string_sized':
        s = ET.SubElement(parent, _tag(NS_PLC, 'string'))
        s.set('length', str(type_info['length']))

    elif kind == 'array':
        arr = ET.SubElement(parent, _tag(NS_PLC, 'array'))
        dim = ET.SubElement(arr, _tag(NS_PLC, 'dimension'))
        dim.set('lower', str(type_info['lower']))
        dim.set('upper', str(type_info['upper']))
        bt = ET.SubElement(arr, _tag(NS_PLC, 'baseType'))
        _build_type_xml(bt, type_info['base_type'])


def _build_variable_element(parent, var):
    """Build a <variable> XML element from a parsed variable dict."""
    vel = ET.SubElement(parent, _tag(NS_PLC, 'variable'))
    vel.set('name', var['name'])

    if var.get('at_mapping'):
        vel.set('address', var['at_mapping'])

    # <type>
    type_el = ET.SubElement(vel, _tag(NS_PLC, 'type'))
    _build_type_xml(type_el, var['type_info'])

    # <initialValue> (optional)
    if var.get('initial_value'):
        iv = ET.SubElement(vel, _tag(NS_PLC, 'initialValue'))
        sv = ET.SubElement(iv, _tag(NS_PLC, 'simpleValue'))
        sv.set('value', var['initial_value'])

    # <documentation> with inline comment (optional)
    if var.get('comment'):
        doc = ET.SubElement(vel, _tag(NS_PLC, 'documentation'))
        xh = ET.SubElement(doc, _tag(NS_XH, 'xhtml'))
        xh.text = ' ' + var['comment']


def _build_method_element(add_data, method):
    """Build a Method data element inside the POU's <addData>.

    TwinCAT XML structure for methods:
      <data name="...method"><Method name="..." ObjectId="...">
        <interface>
          <returnType><STRING/></returnType>   (if method returns a value)
          <localVars>...</localVars>
        </interface>
        <body><ST><xhtml>...</xhtml></ST></body>
        <InterfaceAsPlainText><xhtml>...</xhtml></InterfaceAsPlainText>
      </Method></data>
    """
    data = ET.SubElement(add_data, _tag(NS_PLC, 'data'))
    data.set('name', NS_METHOD)
    data.set('handleUnknown', 'implementation')

    m_el = ET.SubElement(data, _tag(NS_PLC, 'Method'))
    m_el.set('name', method['name'])
    m_el.set('ObjectId', str(uuid.uuid4()))

    # <interface> — returnType + variable sections
    interface = ET.SubElement(m_el, _tag(NS_PLC, 'interface'))

    # <returnType> (if the method has a return type like : STRING or : BOOL)
    if method.get('return_type'):
        rt_el = ET.SubElement(interface, _tag(NS_PLC, 'returnType'))
        rt_info = _parse_type_str(method['return_type'])
        _build_type_xml(rt_el, rt_info)

    # Local variable sections
    for section_tag, variables in method['var_sections']:
        section = ET.SubElement(interface, _tag(NS_PLC, section_tag))
        for var in variables:
            _build_variable_element(section, var)
        # Add InterfaceAsPlainText inside localVars addData (TwinCAT convention)
        _add_iface_adddata(section, method['declaration_text'])

    # Access modifiers
    if method.get('access'):
        acc_add = ET.SubElement(interface, _tag(NS_PLC, 'addData'))
        acc_data = ET.SubElement(acc_add, _tag(NS_PLC, 'data'))
        acc_data.set('name', 'http://www.3s-software.com/plcopenxml/accessmodifiers')
        acc_data.set('handleUnknown', 'implementation')
        acc_el = ET.SubElement(acc_data, _tag(NS_PLC, 'AccessModifiers'))
        acc_el.set(method['access'].capitalize(), 'true')

    # <body> with ST code
    if method['body_text']:
        body = ET.SubElement(m_el, _tag(NS_PLC, 'body'))
        st = ET.SubElement(body, _tag(NS_PLC, 'ST'))
        xhtml = ET.SubElement(st, _tag(NS_XH, 'xhtml'))
        xhtml.text = '\n' + method['body_text']

    # InterfaceAsPlainText directly under Method element (TwinCAT convention)
    ipt = ET.SubElement(m_el, _tag(NS_PLC, 'InterfaceAsPlainText'))
    xh = ET.SubElement(ipt, _tag(NS_XH, 'xhtml'))
    xh.text = method['declaration_text']

    # Empty addData at the end (TwinCAT convention)
    ET.SubElement(m_el, _tag(NS_PLC, 'addData'))


def _build_pou_element(parent, pou_data, obj_id):
    """Build a complete <pou> element from parsed POU data."""
    pou = ET.SubElement(parent, _tag(NS_PLC, 'pou'))
    pou.set('name', pou_data['pou_name'])
    pou.set('pouType', pou_data['pou_type'])

    decl_text = pou_data['declaration_text']

    # --- <interface> ---
    interface = ET.SubElement(pou, _tag(NS_PLC, 'interface'))

    for section_tag, variables in pou_data['var_sections']:
        section = ET.SubElement(interface, _tag(NS_PLC, section_tag))

        # Individual <variable> elements (primary structured representation)
        for var in variables:
            _build_variable_element(section, var)

        # InterfaceAsPlainText inside each VAR section (TwinCAT convention:
        # each section carries the FULL declaration, not just its own variables)
        _add_iface_adddata(section, decl_text)

    # --- <body> ---
    if pou_data['body_text']:
        body = ET.SubElement(pou, _tag(NS_PLC, 'body'))
        st = ET.SubElement(body, _tag(NS_PLC, 'ST'))
        xhtml = ET.SubElement(st, _tag(NS_XH, 'xhtml'))
        xhtml.text = '\n' + pou_data['body_text']

    # --- <addData> at POU level ---
    add_data = ET.SubElement(pou, _tag(NS_PLC, 'addData'))

    # InterfaceAsPlainText (POU-level copy)
    iface_data = ET.SubElement(add_data, _tag(NS_PLC, 'data'))
    iface_data.set('name', NS_INTERFACE)
    iface_data.set('handleUnknown', 'implementation')
    ipt = ET.SubElement(iface_data, _tag(NS_PLC, 'InterfaceAsPlainText'))
    xh = ET.SubElement(ipt, _tag(NS_XH, 'xhtml'))
    xh.text = decl_text

    # ObjectId
    oid_data = ET.SubElement(add_data, _tag(NS_PLC, 'data'))
    oid_data.set('name', NS_OBJID)
    oid_data.set('handleUnknown', 'discard')
    oid_el = ET.SubElement(oid_data, _tag(NS_PLC, 'ObjectId'))
    oid_el.text = obj_id

    # Methods
    for method in pou_data['methods']:
        _build_method_element(add_data, method)


def build_xml_from_st(st_text):
    """Convert ST text to a PLCopen XML string.

    Parses the ST text, builds the full PLCopen XML tree including
    file/content headers, POU with interface/body/methods, and
    project structure metadata.
    """
    ET.register_namespace('', NS_PLC)

    pou_data = parse_st_text(st_text)

    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.0000000')
    obj_id = str(uuid.uuid4())

    # --- Root: <project> ---
    project = ET.Element(_tag(NS_PLC, 'project'))

    # --- <fileHeader> ---
    fh = ET.SubElement(project, _tag(NS_PLC, 'fileHeader'))
    fh.set('companyName', 'Beckhoff Automation GmbH')
    fh.set('productName', 'TwinCAT PLC Control')
    fh.set('productVersion', '3.5.21.20')
    fh.set('creationDateTime', now)

    # --- <contentHeader> ---
    ch = ET.SubElement(project, _tag(NS_PLC, 'contentHeader'))
    ch.set('name', 'PLC1')
    ch.set('modificationDateTime', now)

    coord = ET.SubElement(ch, _tag(NS_PLC, 'coordinateInfo'))
    for lang in ('fbd', 'ld', 'sfc'):
        lang_el = ET.SubElement(coord, _tag(NS_PLC, lang))
        sc = ET.SubElement(lang_el, _tag(NS_PLC, 'scaling'))
        sc.set('x', '1')
        sc.set('y', '1')

    ch_add = ET.SubElement(ch, _tag(NS_PLC, 'addData'))
    ch_data = ET.SubElement(ch_add, _tag(NS_PLC, 'data'))
    ch_data.set('name', NS_PINFO)
    ch_data.set('handleUnknown', 'implementation')
    ET.SubElement(ch_data, _tag(NS_PLC, 'ProjectInformation'))

    # --- <types> ---
    types_el = ET.SubElement(project, _tag(NS_PLC, 'types'))
    ET.SubElement(types_el, _tag(NS_PLC, 'dataTypes'))

    pous = ET.SubElement(types_el, _tag(NS_PLC, 'pous'))
    _build_pou_element(pous, pou_data, obj_id)

    # --- <instances> ---
    instances = ET.SubElement(project, _tag(NS_PLC, 'instances'))
    ET.SubElement(instances, _tag(NS_PLC, 'configurations'))

    # --- <addData> project structure ---
    proj_add = ET.SubElement(project, _tag(NS_PLC, 'addData'))
    proj_data = ET.SubElement(proj_add, _tag(NS_PLC, 'data'))
    proj_data.set('name', NS_PROJ)
    proj_data.set('handleUnknown', 'discard')
    ps = ET.SubElement(proj_data, _tag(NS_PLC, 'ProjectStructure'))
    obj = ET.SubElement(ps, _tag(NS_PLC, 'Object'))
    obj.set('Name', pou_data['pou_name'])
    obj.set('ObjectId', obj_id)

    # --- Serialize to XML string ---
    try:
        ET.indent(project, space='  ')
    except AttributeError:
        pass  # Python < 3.9: skip pretty-printing

    buffer = io.BytesIO()
    tree = ET.ElementTree(project)
    tree.write(buffer, encoding='utf-8', xml_declaration=True)
    xml_str = buffer.getvalue().decode('utf-8')

    # Match TwinCAT's double-quote style in the XML declaration
    xml_str = xml_str.replace(
        "<?xml version='1.0' encoding='utf-8'?>",
        '<?xml version="1.0" encoding="utf-8"?>',
    )

    return xml_str


# =============================================================================
# GUI
# =============================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PLCopen XML \u2194 ST Converter')
        self.geometry('950x700')

        self.current_filepath = None
        self.app_dir = os.path.dirname(os.path.abspath(__file__))

        # Toolbar
        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        # --- Import buttons ---
        tk.Button(toolbar, text='Open XML', command=self.open_xml).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Open .txt', command=self.open_txt).pack(side=tk.LEFT, padx=2)

        # Separator
        ttk_sep = tk.Frame(toolbar, width=2, bd=1, relief=tk.SUNKEN)
        ttk_sep.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        # --- Export buttons ---
        tk.Button(toolbar, text='Save .txt', command=self.save_txt).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text='Save XML', command=self.save_xml).pack(side=tk.LEFT, padx=2)

        # Separator
        ttk_sep2 = tk.Frame(toolbar, width=2, bd=1, relief=tk.SUNKEN)
        ttk_sep2.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        tk.Button(toolbar, text='Copy', command=self.copy_all).pack(side=tk.LEFT, padx=2)

        self.status_var = tk.StringVar(value='Ready')
        tk.Label(toolbar, textvariable=self.status_var).pack(side=tk.RIGHT, padx=5)

        # Text editor with scrollbars (use grid for proper layout)
        text_frame = tk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self.text_editor = tk.Text(
            text_frame,
            wrap=tk.NONE,
            undo=True,
            font=('Consolas', 10),
        )
        self.text_editor.grid(row=0, column=0, sticky='nsew')

        v_scroll = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_editor.yview)
        v_scroll.grid(row=0, column=1, sticky='ns')

        h_scroll = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=self.text_editor.xview)
        h_scroll.grid(row=1, column=0, sticky='ew')

        self.text_editor.config(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    # --- Import: XML -> ST ---
    def open_xml(self):
        filepath = filedialog.askopenfilename(
            title='Select PLCopen XML file',
            initialdir=self.app_dir,
            filetypes=[('XML files', '*.xml'), ('All files', '*.*')],
        )
        if not filepath:
            return

        try:
            result = parse_xml_file(filepath)
            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', result)
            self.current_filepath = filepath
            self.status_var.set(f'Loaded XML: {os.path.basename(filepath)}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to parse XML:\n{e}')

    # --- Import: .txt -> editor ---
    def open_txt(self):
        filepath = filedialog.askopenfilename(
            title='Select ST text file',
            initialdir=self.app_dir,
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', content)
            self.current_filepath = filepath
            self.status_var.set(f'Loaded: {os.path.basename(filepath)}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to read file:\n{e}')

    # --- Export: editor -> .txt ---
    def save_txt(self):
        default_name = ''
        if self.current_filepath:
            default_name = os.path.splitext(
                os.path.basename(self.current_filepath)
            )[0] + '.txt'

        filepath = filedialog.asksaveasfilename(
            title='Save ST code as text file',
            initialdir=self.app_dir,
            defaultextension='.txt',
            initialfile=default_name,
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
        )
        if not filepath:
            return

        content = self.text_editor.get('1.0', tk.END).rstrip('\n')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        self.status_var.set(f'Saved: {os.path.basename(filepath)}')

    # --- Export: editor ST -> PLCopen XML ---
    def save_xml(self):
        default_name = ''
        if self.current_filepath:
            default_name = os.path.splitext(
                os.path.basename(self.current_filepath)
            )[0] + '.xml'

        filepath = filedialog.asksaveasfilename(
            title='Save as PLCopen XML',
            initialdir=self.app_dir,
            defaultextension='.xml',
            initialfile=default_name,
            filetypes=[('XML files', '*.xml'), ('All files', '*.*')],
        )
        if not filepath:
            return

        try:
            st_text = self.text_editor.get('1.0', tk.END).rstrip('\n')
            xml_str = build_xml_from_st(st_text)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(xml_str)

            self.status_var.set(f'Saved XML: {os.path.basename(filepath)}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to generate XML:\n{e}')

    def copy_all(self):
        content = self.text_editor.get('1.0', tk.END).rstrip('\n')
        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_var.set('Copied to clipboard')


if __name__ == '__main__':
    app = App()
    app.mainloop()
