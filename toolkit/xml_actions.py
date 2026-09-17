"""
xml_actions.py
Screen Agent Toolkit for XML manipulation.
Uses: xml.etree.ElementTree, lxml, xmltodict, json, re.
All functions return a standardized Dict: {"success": bool, "data": Any, "error": str | None}
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

import xml.etree.ElementTree as ET
import xmltodict
from lxml import etree as lxml_etree
from pathlib import Path


def _response(success: bool, data: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Standardized response dictionary factory."""
    return {"success": success, "data": data, "error": error}


def parse_xml(xml_string: str) -> Dict[str, Any]:
    """Parse XML string into a dictionary using xmltodict."""
    try:
        parsed = xmltodict.parse(xml_string, force_list=False)
        return _response(True, parsed)
    except Exception as e:
        return _response(False, error=str(e))


def parse_xml_file(file_path: str) -> Dict[str, Any]:
    """Read and parse an XML file into a dictionary."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return parse_xml(content)
    except Exception as e:
        return _response(False, error=str(e))


def xml_to_dict(xml_string: str) -> Dict[str, Any]:
    """Convert XML string to dictionary (Alias/Explicit wrapper for clarity)."""
    try:
        data = xmltodict.parse(xml_string, force_list=False)
        return _response(True, data)
    except Exception as e:
        return _response(False, error=str(e))


def dict_to_xml(data: dict, root_tag: str = "root") -> Dict[str, Any]:
    """Convert a dictionary to an XML string."""
    try:
        # Wrap data to ensure a single root element if not already present
        wrapped = {root_tag: data}
        xml_str = xmltodict.unparse(wrapped, pretty=False, full_document=False)
        return _response(True, xml_str)
    except Exception as e:
        return _response(False, error=str(e))


def xml_to_json(xml_string: str) -> Dict[str, Any]:
    """Convert XML string to JSON string."""
    try:
        dict_data = xmltodict.parse(xml_string, force_list=False)
        json_str = json.dumps(dict_data, indent=2)
        return _response(True, json_str)
    except Exception as e:
        return _response(False, error=str(e))


def json_to_xml(json_string: str, root_tag: str = "root") -> Dict[str, Any]:
    """Convert JSON string to XML string."""
    try:
        dict_data = json.loads(json_string)
        if not isinstance(dict_data, dict):
            dict_data = {"item": dict_data}
        xml_str = xmltodict.unparse({root_tag: dict_data}, pretty=False, full_document=False)
        return _response(True, xml_str)
    except Exception as e:
        return _response(False, error=str(e))


def validate_xml(xml_string: str, xsd_string: str) -> Dict[str, Any]:
    """Validate XML against an XSD schema using lxml."""
    try:
        xml_doc = lxml_etree.fromstring(xml_string.encode('utf-8'))
        xsd_doc = lxml_etree.fromstring(xsd_string.encode('utf-8'))
        schema = lxml_etree.XMLSchema(xsd_doc)
        is_valid = schema.validate(xml_doc)
        error_log = str(schema.error_log) if not is_valid else None
        return _response(is_valid, data={"valid": is_valid}, error=error_log)
    except Exception as e:
        return _response(False, error=str(e))


def xpath_query(xml_string: str, xpath: str) -> Dict[str, Any]:
    """Execute an XPath query on an XML string."""
    try:
        doc = lxml_etree.fromstring(xml_string.encode('utf-8'))
        results = doc.xpath(xpath)
        processed = []
        for res in results:
            if isinstance(res, (str, int, float, bool)):
                processed.append(res)
            elif hasattr(res, 'tag'):
                processed.append({
                    "tag": res.tag,
                    "text": (res.text or "").strip(),
                    "attrib": dict(res.attrib)
                })
            else:
                processed.append(str(res))
        return _response(True, processed)
    except Exception as e:
        return _response(False, error=str(e))


def transform_xslt(xml_string: str, xslt_string: str) -> Dict[str, Any]:
    """Transform XML using an XSLT stylesheet."""
    try:
        xml_doc = lxml_etree.fromstring(xml_string.encode('utf-8'))
        xslt_doc = lxml_etree.fromstring(xslt_string.encode('utf-8'))
        transform = lxml_etree.XSLT(xslt_doc)
        result = transform(xml_doc)
        return _response(True, str(result))
    except Exception as e:
        return _response(False, error=str(e))


def pretty_print_xml(xml_string: str, indent: int = 2) -> Dict[str, Any]:
    """Format XML with consistent indentation."""
    try:
        # Use xml.etree for precise indent control
        tree = ET.fromstring(xml_string)
        ET.indent(tree, space=" " * indent)
        pretty = ET.tostring(tree, encoding='unicode')
        return _response(True, pretty)
    except Exception as e:
        return _response(False, error=str(e))


def minify_xml(xml_string: str) -> Dict[str, Any]:
    """Remove unnecessary whitespace between tags."""
    try:
        minified = re.sub(r'>\s+<', '><', xml_string.strip())
        return _response(True, minified)
    except Exception as e:
        return _response(False, error=str(e))


def get_element_text(xml_string: str, tag: str) -> Dict[str, Any]:
    """Retrieve text content from all elements matching the tag."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        elements = tree.findall(f".//{tag}")
        texts = [(elem.text or "").strip() for elem in elements]
        return _response(True, texts)
    except Exception as e:
        return _response(False, error=str(e))


def set_element_text(xml_string: str, tag: str, text: str) -> Dict[str, Any]:
    """Set text content for all elements matching the tag."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        elements = tree.findall(f".//{tag}")
        if not elements:
            return _response(False, error=f"Tag '{tag}' not found.")
        for elem in elements:
            elem.text = text
        result = lxml_etree.tostring(tree, encoding='unicode')
        return _response(True, result)
    except Exception as e:
        return _response(False, error=str(e))


def add_element(xml_string: str, parent_tag: str, new_tag: str, text: str = "") -> Dict[str, Any]:
    """Add a new element as a child of the first matching parent tag."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        parent = tree.find(f".//{parent_tag}")
        if parent is None:
            return _response(False, error=f"Parent tag '{parent_tag}' not found.")
        new_elem = lxml_etree.SubElement(parent, new_tag)
        new_elem.text = text
        result = lxml_etree.tostring(tree, encoding='unicode')
        return _response(True, result)
    except Exception as e:
        return _response(False, error=str(e))


def remove_element(xml_string: str, tag: str) -> Dict[str, Any]:
    """Remove the first element matching the tag."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        elem = tree.find(f".//{tag}")
        if elem is None:
            return _response(False, error=f"Tag '{tag}' not found.")
        parent = elem.getparent()
        if parent is not None:
            parent.remove(elem)
        result = lxml_etree.tostring(tree, encoding='unicode')
        return _response(True, result)
    except Exception as e:
        return _response(False, error=str(e))


def get_attributes(xml_string: str, tag: str) -> Dict[str, Any]:
    """Extract attributes from all elements matching the tag."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        elements = tree.findall(f".//{tag}")
        attrs = [dict(elem.attrib) for elem in elements]
        return _response(True, attrs)
    except Exception as e:
        return _response(False, error=str(e))


def set_attribute(xml_string: str, tag: str, attr: str, value: str) -> Dict[str, Any]:
    """Set an attribute on the first element matching the tag."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        elem = tree.find(f".//{tag}")
        if elem is None:
            return _response(False, error=f"Tag '{tag}' not found.")
        elem.set(attr, value)
        result = lxml_etree.tostring(tree, encoding='unicode')
        return _response(True, result)
    except Exception as e:
        return _response(False, error=str(e))


def count_elements(xml_string: str, tag: str) -> Dict[str, Any]:
    """Count occurrences of a specific tag."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        count = len(tree.findall(f".//{tag}"))
        return _response(True, {"count": count})
    except Exception as e:
        return _response(False, error=str(e))


def merge_xml(xml1: str, xml2: str) -> Dict[str, Any]:
    """Merge children of xml2 into xml1."""
    try:
        tree1 = lxml_etree.fromstring(xml1.encode('utf-8'))
        tree2 = lxml_etree.fromstring(xml2.encode('utf-8'))
        for child in tree2:
            tree1.append(child)
        result = lxml_etree.tostring(tree1, encoding='unicode')
        return _response(True, result)
    except Exception as e:
        return _response(False, error=str(e))


def split_xml(xml_string: str, tag: str) -> Dict[str, Any]:
    """Extract all elements matching the tag as individual XML fragments."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        elements = tree.findall(f".//{tag}")
        fragments = [lxml_etree.tostring(elem, encoding='unicode') for elem in elements]
        return _response(True, fragments)
    except Exception as e:
        return _response(False, error=str(e))


def find_elements_by_attr(xml_string: str, attr: str, value: str) -> Dict[str, Any]:
    """Find elements by a specific attribute value."""
    try:
        tree = lxml_etree.fromstring(xml_string.encode('utf-8'))
        xpath_expr = f".//*[@{attr}='{value}']"
        elems = tree.xpath(xpath_expr)
        results = [{"tag": e.tag, "text": (e.text or "").strip(), "attrib": dict(e.attrib)} for e in elems]
        return _response(True, results)
    except Exception as e:
        return _response(False, error=str(e))


def xml_diff(xml1: str, xml2: str) -> Dict[str, Any]:
    """Compare two XML strings and return structural differences."""
    try:
        t1 = lxml_etree.fromstring(xml1.encode('utf-8'))
        t2 = lxml_etree.fromstring(xml2.encode('utf-8'))
        
        # Canonicalize for consistent comparison
        s1 = lxml_etree.tostring(t1, encoding='unicode', method='xml')
        s2 = lxml_etree.tostring(t2, encoding='unicode', method='xml')
        
        lines1 = s1.splitlines()
        lines2 = s2.splitlines()
        max_lines = max(len(lines1), len(lines2))
        diffs = []
        
        for i in range(max_lines):
            l1 = lines1[i] if i < len(lines1) else None
            l2 = lines2[i] if i < len(lines2) else None
            if l1 != l2:
                diffs.append({
                    "line": i + 1,
                    "xml1_line": l1,
                    "xml2_line": l2
                })
                
        return _response(True, {
            "identical": len(diffs) == 0,
            "difference_count": len(diffs),
            "details": diffs
        })
    except Exception as e:
        return _response(False, error=str(e))


def escape_xml(text: str) -> Dict[str, Any]:
    """Escape XML special characters using regex."""
    try:
        entity_map = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'}
        escaped = re.sub(r'[&<>"\x27]', lambda m: entity_map[m.group()], text)
        return _response(True, escaped)
    except Exception as e:
        return _response(False, error=str(e))


def unescape_xml(text: str) -> Dict[str, Any]:
    """Unescape XML entities using regex."""
    try:
        entity_map = {'amp': '&', 'lt': '<', 'gt': '>', 'quot': '"', 'apos': "'", '#39': "'", '#x27': "'"}
        unescaped = re.sub(r'&([a-z0-9#]+);', lambda m: entity_map.get(m.group(1), m.group(0)), text)
        return _response(True, unescaped)
    except Exception as e:
        return _response(False, error=str(e))


def batch_process_xml(file_paths: list, xpath: str) -> Dict[str, Any]:
    """Process multiple XML files with an XPath query and collect results."""
    try:
        results = {}
        for fp in file_paths:
            file_path = Path(fp)
            if not file_path.exists():
                results[str(fp)] = {"success": False, "error": "File not found."}
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = lxml_etree.fromstring(content.encode('utf-8'))
            query_res = tree.xpath(xpath)
            processed = []
            for res in query_res:
                if isinstance(res, (str, int, float, bool)):
                    processed.append(res)
                elif hasattr(res, 'tag'):
                    processed.append({
                        "tag": res.tag,
                        "text": (res.text or "").strip(),
                        "attrib": dict(res.attrib)
                    })
                else:
                    processed.append(str(res))
            
            results[str(fp)] = {"success": True, "matches": processed}
            
        return _response(True, results)
    except Exception as e:
        return _response(False, error=str(e))