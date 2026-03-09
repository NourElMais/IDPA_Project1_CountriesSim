"""
tree_loader.py — XML → TreeNode

Core design decision
--------------------
The Wikipedia XML format splits every value into individual <token> nodes:

    <president>
        <token>Abdelmadjid</token>
        <token>Tebboune</token>
    </president>

If we keep these as separate content nodes, the TED pays heavy insert/delete
costs purely because two presidents have names of different lengths
(e.g. "Ali Hassan" vs "Bashar Al-Assad" = 2 tokens vs 3 tokens).
That swamps the real semantic signal.

Fix: any element whose children are ALL <token> leaves gets collapsed into
a SINGLE content node whose value is the joined token text.

    Before:                         After:
    president [structure]           president [content, value="Abdelmadjid Tebboune"]
      token [content] "Abdelmadjid"
      token [content] "Tebboune"

This means:
  - cost_upd("president":"Abdelmadjid Tebboune",
             "president":"Bashar Al-Assad")   → CONTENT_W  (same field, diff value)
  - cost_upd("president":"...", "capital":"") → STRUCT_W   (different field entirely)

Elements with mixed children (some token, some structural sub-elements like
<formation><independence><token>…) are NOT collapsed — only pure-token parents.
"""

import xml.etree.ElementTree as ET


class TreeNode:
    def __init__(self, label, value=None, children=None, node_type="structure"):
        self.label     = label
        self.value     = value
        self.children  = children if children is not None else []
        self.node_type = node_type

    def add_child(self, child):
        self.children.append(child)

    def __repr__(self):
        v = f" : {self.value!r}" if self.value else ""
        return f"TreeNode({self.label!r} [{self.node_type}]{v}, children={len(self.children)})"


def _all_token_leaves(elem: ET.Element) -> bool:
    """True iff every direct child of elem is a <token> with no sub-children."""
    if len(elem) == 0:
        return False                        # elem itself is a leaf — nothing to collapse
    return all(
        child.tag == "token" and len(child) == 0
        for child in elem
    )


def xml_elem_to_tree(elem: ET.Element) -> TreeNode | None:
    """
    Recursively convert an XML element to a TreeNode.

    Three cases:
    1. Pure-token parent  → single content node  (label = elem.tag, value = joined text)
    2. Bare text leaf     → single content node  (label = elem.tag, value = text)
    3. Structural element → structure node with recursively built children
    """

    # ── Case 1: collapse pure-token parents ───────────────────────────────────
    if _all_token_leaves(elem):
        tokens = [c.text.strip() for c in elem if (c.text or "").strip()]
        if tokens:
            return TreeNode(
                label     = elem.tag,
                value     = " ".join(tokens),
                node_type = "content",
            )
        # all tokens were whitespace — fall through to structural

    # ── Case 2: bare text leaf (no children, has text) ────────────────────────
    if len(elem) == 0:
        text = (elem.text or "").strip()
        if text:
            return TreeNode(label=elem.tag, value=text, node_type="content")
        return None                         # empty leaf — discard

    # ── Case 3: structural node ───────────────────────────────────────────────
    node = TreeNode(label=elem.tag, node_type="structure")
    for child in elem:
        child_node = xml_elem_to_tree(child)
        if child_node is not None:
            node.add_child(child_node)

    return node


def load_tree_from_xml(file_path: str) -> TreeNode:
    root = ET.parse(file_path).getroot()
    return xml_elem_to_tree(root)


def print_tree(node: TreeNode, level: int = 0):
    indent = "  " * level
    v      = f" → {node.value!r}" if node.value else ""
    print(f"{indent}- {node.label} [{node.node_type}]{v}")
    for child in node.children:
        print_tree(child, level + 1)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "xml_output/Lebanon.xml"
    print_tree(load_tree_from_xml(path))