"""
Nierman & Jagadish (2002) — Tree Edit Distance
Faithful implementation of the published pseudocode:

    Input:  A, B          (XML document trees)
    Output: TED(A, B)

    M = Degree(A)                           -- # of direct children of A
    N = Degree(B)                           -- # of direct children of B

    Dist[0..M][0..N]
    Dist[0][0] = CostUpd(R(A), R(B))        -- root relabeling

    for i = 1..M:  Dist[i][0] = Dist[i-1][0] + CostDelTree(Ai)
    for j = 1..N:  Dist[0][j] = Dist[0][j-1] + CostInsTree(Bj)

    for i = 1..M:
        for j = 1..N:
            Dist[i][j] = min(
                Dist[i-1][j-1] + TED(Ai, Bj),       -- match  (recursive)
                Dist[i-1][j]   + CostDelTree(Ai),    -- delete
                Dist[i][j-1]   + CostInsTree(Bj)     -- insert
            )

    return Dist[M][N]
"""

from tree_loader import load_tree_from_xml, TreeNode

# ── Weights ────────────────────────────────────────────────────────────────────
STRUCT_W  = 2.0   # rename a structural (tag) node
CONTENT_W = 2.0   # change a leaf value
XTYPE_W   = 4.0   # structural node ↔ content node


# ── Cost functions ─────────────────────────────────────────────────────────────

def cost_upd(a: TreeNode, b: TreeNode) -> float:
    """
    CostUpd(a, b): cost to relabel node a into node b.
    Only looks at the nodes themselves, not their subtrees.
    """
    if a.node_type != b.node_type:
        return XTYPE_W
    if a.node_type == "structure":
        return 0.0 if a.label == b.label else STRUCT_W
    # content node: both the field label AND the value must match
    return 0.0 if (a.label == b.label and a.value == b.value) else CONTENT_W


def cost_del_tree(node: TreeNode) -> float:
    """CostDelTree: cost to delete this node and its entire subtree."""
    w = STRUCT_W if node.node_type == "structure" else CONTENT_W
    return w + sum(cost_del_tree(c) for c in node.children)


def cost_ins_tree(node: TreeNode) -> float:
    """CostInsTree: cost to insert this node and its entire subtree."""
    w = STRUCT_W if node.node_type == "structure" else CONTENT_W
    return w + sum(cost_ins_tree(c) for c in node.children)


# ── TED ────────────────────────────────────────────────────────────────────────

# One dict per comparison run, keyed by (id(a), id(b)).
# Recreated fresh in compare_countries() to avoid stale id() hits across runs.
_memo: dict = {}


def ted(a: TreeNode, b: TreeNode) -> float:
    """
    TED(A, B) — direct transcription of Nierman & Jagadish pseudocode.
    """
    key = (id(a), id(b))
    if key in _memo:
        return _memo[key]

    M = len(a.children)   # Degree(A)
    N = len(b.children)   # Degree(B)

    # Dist[0..M][0..N]
    Dist = [[0.0] * (N + 1) for _ in range(M + 1)]

    # Line 4 — seed: cost of relabeling the two roots
    Dist[0][0] = cost_upd(a, b)

    # Line 5 — delete all children of A (column 0)
    for i in range(1, M + 1):
        Dist[i][0] = Dist[i - 1][0] + cost_del_tree(a.children[i - 1])

    # Line 6 — insert all children of B (row 0)
    for j in range(1, N + 1):
        Dist[0][j] = Dist[0][j - 1] + cost_ins_tree(b.children[j - 1])

    # Lines 7-17 — fill the rest of the table
    for i in range(1, M + 1):
        for j in range(1, N + 1):
            Ai = a.children[i - 1]
            Bj = b.children[j - 1]
            Dist[i][j] = min(
                Dist[i - 1][j - 1] + ted(Ai, Bj),        # match  (line 12)
                Dist[i - 1][j]     + cost_del_tree(Ai),   # delete (line 13)
                Dist[i][j - 1]     + cost_ins_tree(Bj),   # insert (line 14)
            )

    result = Dist[M][N]
    _memo[key] = result
    return result


# ── Similarity ─────────────────────────────────────────────────────────────────

def similarity(t1: TreeNode, t2: TreeNode, ted_value: float) -> float:
    """
    Dice-coefficient normalisation:

        sim = 1 - (2 * TED) / (CostDelTree(t1) + CostInsTree(t2) + TED)
    """
    denom = cost_del_tree(t1) + cost_ins_tree(t2) + ted_value
    if denom == 0:
        return 1.0
    return max(0.0, 1.0 - (2.0 * ted_value) / denom)


# ── Public API ─────────────────────────────────────────────────────────────────

def compare_countries(file1: str, file2: str) -> tuple[float, float]:
    """
    Load two country XML files and return (TED distance, similarity in [0,1]).
    """
    global _memo
    _memo = {}                          # fresh cache — avoids stale id() hits

    t1 = load_tree_from_xml(file1)
    t2 = load_tree_from_xml(file2)

    d   = ted(t1, t2)
    sim = similarity(t1, t2, d)
    return d, sim


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pairs = [
        ("xml_output/Lebanon.xml",  "xml_output/Lebanon.xml"),   # sanity: identical
        ("xml_output/Jordan.xml",   "xml_output/Syria.xml"),     # very similar
        ("xml_output/Algeria.xml",  "xml_output/Morocco.xml"),   # similar
        ("xml_output/Germany.xml",  "xml_output/France.xml"),    # similar
        ("xml_output/Iceland.xml",  "xml_output/Lebanon.xml"),   # dissimilar
        ("xml_output/Lebanon.xml",  "xml_output/France.xml"),    # dissimilar
    ]

    print(f"{'Pair':<40}  {'TED':>10}  {'Similarity':>10}")
    print("─" * 65)
    for f1, f2 in pairs:
        try:
            d, sim = compare_countries(f1, f2)
            name = (
                f"{f1.split('/')[1].replace('.xml','')} vs "
                f"{f2.split('/')[1].replace('.xml','')}"
            )
            print(f"{name:<40}  {d:>10.2f}  {sim:>10.4f}")
        except FileNotFoundError as e:
            print(f"  SKIP — {e}")
