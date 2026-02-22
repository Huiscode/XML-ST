"""
test_roundtrip.py
-----------------
Critical round-trip tests:
    XML → ST → XML must produce the exact original XML string.

Run from project root:
    python -m pytest src/tests/ -v
"""

import os
import sys
import pytest

# Add src/ to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from xml_parser import load_xml, patch_xml
from st_formatter import format_st
from st_splitter import split_st

# Paths to the template XML files
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FB_XML  = os.path.join(REPO_ROOT, "FB_RingData.xml")
DUT_XML = os.path.join(REPO_ROOT, "ST_BatchMetadata.xml")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roundtrip(path: str) -> tuple[str, str]:
    """Return (original_xml, roundtripped_xml)."""
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    parsed = load_xml(path)
    st_text = format_st(parsed)
    split = split_st(st_text, parsed.xml_type)

    if parsed.xml_type == "DUT":
        patched = patch_xml(parsed, new_declaration=split.declaration,
                            new_body="", new_methods=[])
    else:
        patched = patch_xml(parsed, new_declaration=split.declaration,
                            new_body=split.body, new_methods=split.methods)

    return original, patched


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFBRoundTrip:
    @pytest.fixture(autouse=True)
    def skip_if_missing(self):
        if not os.path.isfile(FB_XML):
            pytest.skip(f"Template file not found: {FB_XML}")

    def test_fb_xml_roundtrip_exact(self):
        """XML → ST → XML must be byte-for-byte identical for FB_RingData.xml"""
        original, patched = _roundtrip(FB_XML)
        assert original == patched, _diff_report(original, patched)

    def test_fb_xml_type_detected(self):
        parsed = load_xml(FB_XML)
        assert parsed.xml_type == "FB"

    def test_fb_declaration_extracted(self):
        parsed = load_xml(FB_XML)
        assert "FUNCTION_BLOCK FB_RingData" in parsed.fb_declaration
        assert "VAR_INPUT" in parsed.fb_declaration
        assert "VAR_OUTPUT" in parsed.fb_declaration
        assert "VAR" in parsed.fb_declaration

    def test_fb_body_extracted(self):
        parsed = load_xml(FB_XML)
        assert "rTrig(CLK := bTrigger)" in parsed.fb_body
        assert "bBusy := bIsRecording OR bIsSaving" in parsed.fb_body

    def test_fb_methods_extracted(self):
        parsed = load_xml(FB_XML)
        assert len(parsed.methods) == 2

        names = [m.name for m in parsed.methods]
        assert "M_Filename" in names
        assert "M_JsonGenerate" in names

    def test_fb_method_access_modifiers(self):
        parsed = load_xml(FB_XML)
        for m in parsed.methods:
            assert m.access == "PRIVATE"

    def test_fb_method_return_types(self):
        parsed = load_xml(FB_XML)
        by_name = {m.name: m for m in parsed.methods}
        assert by_name["M_Filename"].return_type == "STRING"
        assert by_name["M_JsonGenerate"].return_type == "BOOL"

    def test_fb_method_bodies_extracted(self):
        parsed = load_xml(FB_XML)
        by_name = {m.name: m for m in parsed.methods}
        assert "M_Filename := sTemp" in by_name["M_Filename"].body
        assert "fbJsonWriter.ResetDocument()" in by_name["M_JsonGenerate"].body

    def test_fb_st_format_has_dividers(self):
        parsed = load_xml(FB_XML)
        st = format_st(parsed)
        assert "// " + "=" * 60 in st
        assert "// Method: M_Filename | PRIVATE | STRING" in st
        assert "// Method: M_JsonGenerate | PRIVATE | BOOL" in st
        assert "// === FB Body ===" in st

    def test_fb_methods_at_end(self):
        """Methods must appear AFTER the FB body in the ST text."""
        parsed = load_xml(FB_XML)
        st = format_st(parsed)
        body_pos = st.find("// === FB Body ===")
        method_pos = st.find("// Method:")
        assert body_pos < method_pos, "Methods must appear after FB body"

    def test_fb_split_reconstruction(self):
        parsed = load_xml(FB_XML)
        st = format_st(parsed)
        split = split_st(st, "FB")

        assert "FUNCTION_BLOCK FB_RingData" in split.declaration
        assert "bBusy := bIsRecording OR bIsSaving" in split.body
        assert len(split.methods) == 2


class TestDUTRoundTrip:
    @pytest.fixture(autouse=True)
    def skip_if_missing(self):
        if not os.path.isfile(DUT_XML):
            pytest.skip(f"Template file not found: {DUT_XML}")

    def test_dut_xml_roundtrip_exact(self):
        """XML → ST → XML must be byte-for-byte identical for ST_BatchMetadata.xml"""
        original, patched = _roundtrip(DUT_XML)
        assert original == patched, _diff_report(original, patched)

    def test_dut_xml_type_detected(self):
        parsed = load_xml(DUT_XML)
        assert parsed.xml_type == "DUT"

    def test_dut_declaration_extracted(self):
        parsed = load_xml(DUT_XML)
        assert "ST_BatchMetadata" in parsed.dut_declaration
        assert "STRUCT" in parsed.dut_declaration
        assert "END_STRUCT" in parsed.dut_declaration

    def test_dut_st_format(self):
        parsed = load_xml(DUT_XML)
        st = format_st(parsed)
        assert "TYPE ST_BatchMetadata" in st
        assert "sOrderNumberSAP" in st


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _diff_report(a: str, b: str, context: int = 5) -> str:
    """Show the first differing region between two strings."""
    min_len = min(len(a), len(b))
    for i in range(min_len):
        if a[i] != b[i]:
            start = max(0, i - context * 40)
            end = min(min_len, i + context * 40)
            return (
                f"\nFirst difference at char {i}:\n"
                f"  ORIGINAL:  {repr(a[start:end])}\n"
                f"  ROUNDTRIP: {repr(b[start:end])}"
            )
    if len(a) != len(b):
        return f"\nLength mismatch: original={len(a)}, roundtrip={len(b)}"
    return "\nStrings are identical (no diff found)"
