"""
st_splitter.py
--------------
Parses the combined ST display text (produced by st_formatter) back into
discrete pieces that can be patched into the original XML structure.

Round-trip whitespace contract with st_formatter:
  - format_st uses "\n".join(parts), which adds ONE \n between each piece.
  - var_decl ends with "END_VAR"; body starts with "\n" (its own leading newline).
    → After END_VAR in the content there is ONE extra \n before the body.
  - For non-last methods: between body and next method section there are TWO
    extra \n (join(body, "") + join("", DIVIDER)).
  - For the last method: body is the last item, so no trailing extra \n.
  The splitter must strip exactly these join-induced newlines to recover
  the original body text.
"""

import re
from xml_parser import MethodInfo

DIVIDER_PATTERN = re.compile(r'^// ={50,}\s*$', re.MULTILINE)
HEADER_PATTERN = re.compile(
    r'^// Method:\s*(?P<name>\S+)\s*\|\s*(?P<access>\S+)\s*\|\s*(?P<ret>.+?)\s*$',
    re.MULTILINE
)
FB_BODY_MARKER = "// === FB Body ==="


class SplitResult:
    def __init__(self):
        self.declaration: str = ""
        self.body: str = ""
        self.methods: list[MethodInfo] = []
        self.is_dut: bool = False


def split_st(text: str, xml_type: str) -> SplitResult:
    """
    Split combined ST text back into declaration, body, and method pieces.
    """
    result = SplitResult()

    if xml_type == "DUT":
        result.is_dut = True
        result.declaration = text
        return result

    dividers = list(DIVIDER_PATTERN.finditer(text))

    if not dividers:
        _split_decl_body(text, result)
        return result

    pre_divider = text[:dividers[0].start()]
    _split_decl_body(pre_divider, result)

    # Collect method ranges: (opening_div_idx, name, access, return_type, is_last)
    method_ranges = []
    i = 0
    while i < len(dividers):
        open_div_end = dividers[i].end()
        next_div_start = dividers[i + 1].start() if i + 1 < len(dividers) else len(text)
        between_text = text[open_div_end:next_div_start]
        header_m = HEADER_PATTERN.search(between_text)

        if header_m:
            closing_div = dividers[i + 1] if i + 1 < len(dividers) else None
            has_next = (i + 2 < len(dividers))
            method_ranges.append((
                closing_div.end() if closing_div else open_div_end,   # content_start
                dividers[i + 2].start() if has_next else len(text),   # content_end
                header_m.group("name"),
                header_m.group("access"),
                header_m.group("ret").strip(),
                not has_next,  # is_last
            ))
            i += 2
        else:
            i += 1

    for (content_start, content_end, name, access, return_type, is_last) in method_ranges:
        method_content = text[content_start:content_end]
        var_decl, body = _split_method_content(
            method_content, name, return_type, is_last
        )
        result.methods.append(MethodInfo(
            name=name,
            access=access,
            return_type=return_type,
            var_declaration=var_decl,
            body=body,
        ))

    return result


def _split_decl_body(text: str, result: SplitResult) -> None:
    """Split pre-divider text into FB declaration and FB body."""
    marker_idx = text.find(FB_BODY_MARKER)
    if marker_idx == -1:
        result.declaration = text.strip()
        result.body = ""
        return

    decl_part = text[:marker_idx].rstrip()
    body_part = text[marker_idx + len(FB_BODY_MARKER):].lstrip("\n")

    result.declaration = decl_part
    result.body = body_part.rstrip()


def _split_method_content(content: str, method_name: str,
                           return_type: str, is_last: bool) -> tuple[str, str]:
    """
    Split method content (from after closing divider to next opening divider)
    into:
      - var_declaration: "METHOD PRIVATE Name : Type\nVAR\n...\nEND_VAR"
      - body: the raw ST body code as it appeared in the original XML xhtml

    Whitespace accounting (see module docstring):
      - content starts with "\n" (join added between closing_div and var_decl)
        → strip ONE leading \n after END_VAR
      - content ends with "\n\n" (non-last) or nothing extra (last)
        → for non-last: strip trailing TWO \n from body
    """
    var_start = re.search(r'^\s*VAR\s*$', content, re.MULTILINE | re.IGNORECASE)
    end_var   = re.search(r'^\s*END_VAR\s*$', content, re.MULTILINE | re.IGNORECASE)

    if var_start and end_var:
        var_block = content[var_start.start():end_var.end()].rstrip()
        # end_var regex (^\s*END_VAR\s*$) consumes the trailing \n via \s*$.
        # So body_code starts at the character AFTER "END_VAR\n".
        # The join(var_decl, body) in format_st adds one \n between them,
        # but that \n is already consumed by the end_var match.
        # Therefore body_code starts directly with the body's own leading \n.
        body_code = content[end_var.end():]

        # Strip trailing join-induced newlines for non-last methods.
        # format_st: join(body, "") → +\n; join("", DIVIDER) → +\n → two \n total.
        if not is_last:
            if body_code.endswith('\n\n'):
                body_code = body_code[:-2]
            elif body_code.endswith('\n'):
                body_code = body_code[:-1]

        decl = f"METHOD PRIVATE {method_name} : {return_type}\n{var_block}"
    else:
        decl = f"METHOD PRIVATE {method_name} : {return_type}\nVAR\nEND_VAR"
        body_code = content.strip()

    return decl, body_code
