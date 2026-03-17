"""
Red-Black Tree — Course Project
"""

from __future__ import annotations
import sys
import time
import math
import random
from typing import Optional, List, Tuple

# ═══════════════════════════════════════════════════════════════════════
#  1.  RED-BLACK NODE
# ═══════════════════════════════════════════════════════════════════════

RED = True
BLACK = False


class RBNode:
    """A single node in the Red-Black Tree.

    Each node stores:
      - key     : the value
      - color   : RED (True) or BLACK (False)
      - left, right, parent : tree pointers

    """
    __slots__ = ("key", "color", "left", "right", "parent")

    def __init__(self, key: int, color: bool = RED,
                 left: Optional["RBNode"] = None,
                 right: Optional["RBNode"] = None,
                 parent: Optional["RBNode"] = None):
        self.key = key
        self.color = color
        self.left = left
        self.right = right
        self.parent = parent

    @property
    def color_name(self) -> str:
        return "RED" if self.color == RED else "BLACK"


# ═══════════════════════════════════════════════════════════════════════
#  2.  RED-BLACK TREE
# ═══════════════════════════════════════════════════════════════════════

class RBTree:
    """Full Red-Black Tree with operation logging.

    """

    def __init__(self) -> None:
        self.NIL = RBNode(key=0, color=BLACK)
        self.root: RBNode = self.NIL
        self.log: List[str] = []
        self.rotation_count: int = 0
        self.recolor_count: int = 0
        self.comparison_count: int = 0

    def insert(self, key: int) -> None:
        """Insert *key* and fix up.  O(log n)."""
        self.log.append(f"INSERT {key}")
        node = RBNode(key=key, color=RED, left=self.NIL, right=self.NIL, parent=self.NIL)

        # Standard BST insert
        parent = self.NIL
        current = self.root
        while current != self.NIL:
            parent = current
            if key < current.key:
                current = current.left
            elif key > current.key:
                current = current.right
            else:
                self.log.append(f"  (duplicate {key} — skipped)")
                return

        node.parent = parent
        if parent == self.NIL:
            self.root = node
            self.log.append(f"  + Created root node {key} (RED)")
        elif key < parent.key:
            parent.left = node
            self.log.append(f"  + Inserted {key} as left child of {parent.key} (RED)")
        else:
            parent.right = node
            self.log.append(f"  + Inserted {key} as right child of {parent.key} (RED)")

        self._insert_fixup(node)

    def delete(self, key: int) -> None:
        """Delete *key* and fix up.  O(log n)."""
        self.log.append(f"DELETE {key}")
        node = self._search_node(self.root, key)
        if node == self.NIL:
            self.log.append(f"  (key {key} not found)")
            return
        self._delete_node(node)

    def search(self, key: int) -> Tuple[bool, int]:
        """Return (found, comparisons)."""
        self.comparison_count = 0
        found = self._search_bool(self.root, key)
        return found, self.comparison_count

    def inorder(self) -> List[int]:
        result: List[int] = []
        self._inorder(self.root, result)
        return result

    def get_height(self) -> int:
        return self._height(self.root)

    def get_node_count(self) -> int:
        return self._count(self.root)

    def get_black_height(self) -> int:
        """Black-height = number of black nodes on any root-to-NIL path."""
        bh = 0
        node = self.root
        while node != self.NIL:
            if node.color == BLACK:
                bh += 1
            node = node.left
        return bh

    def validate(self) -> Tuple[bool, List[str]]:
        """Check all 5 RB properties.  Returns (valid, list_of_violations)."""
        errors = []

        # Property 1: Every node is red or black (always true by construction)

        # Property 2: Root is black
        if self.root != self.NIL and self.root.color != BLACK:
            errors.append("Property 2 violated: root is RED")

        # Property 3: NIL nodes are black (always true — sentinel is BLACK)

        # Property 4: No red-red parent-child
        self._check_no_red_red(self.root, errors)

        # Property 5: All paths same black-height
        bh = self._check_black_height(self.root, errors)

        return len(errors) == 0, errors

    def clear_log(self) -> None:
        self.log.clear()
        self.rotation_count = 0
        self.recolor_count = 0

    # ── rotations ─────────────────────────────────────────────────────

    def _rotate_left(self, x: RBNode) -> None:
        """Left rotation at x.  O(1)."""
        y = x.right
        x.right = y.left
        if y.left != self.NIL:
            y.left.parent = x
        y.parent = x.parent
        if x.parent == self.NIL:
            self.root = y
        elif x == x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y
        self.rotation_count += 1
        self.log.append(f"  - Left rotation at {x.key}")

    def _rotate_right(self, y: RBNode) -> None:
        """Right rotation at y.  O(1)."""
        x = y.left
        y.left = x.right
        if x.right != self.NIL:
            x.right.parent = y
        x.parent = y.parent
        if y.parent == self.NIL:
            self.root = x
        elif y == y.parent.left:
            y.parent.left = x
        else:
            y.parent.right = x
        x.right = y
        y.parent = x
        self.rotation_count += 1
        self.log.append(f"  - Right rotation at {y.key}")

    # ── insert fix-up ─────────────────────────────────────────────────

    def _insert_fixup(self, z: RBNode) -> None:
        while z.parent.color == RED:
            if z.parent == z.parent.parent.left:
                uncle = z.parent.parent.right
                if uncle.color == RED:
                    # Case 2: Uncle is RED → recolor
                    self.log.append(f"Case 2: Parent {z.parent.key} & Uncle {uncle.key} are RED → recolor")
                    z.parent.color = BLACK
                    uncle.color = BLACK
                    z.parent.parent.color = RED
                    self.recolor_count += 3
                    z = z.parent.parent
                else:
                    if z == z.parent.right:
                        # Case 3: Triangle → rotate to make it a line
                        self.log.append(f"Case 3: Triangle at {z.key} → left rotate parent {z.parent.key}")
                        z = z.parent
                        self._rotate_left(z)
                    # Case 4: Line → rotate grandparent + recolor
                    self.log.append(f"Case 4: Line → right rotate grandparent {z.parent.parent.key} + recolor")
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self.recolor_count += 2
                    self._rotate_right(z.parent.parent)
            else:
                # Mirror cases (parent is right child)
                uncle = z.parent.parent.left
                if uncle.color == RED:
                    self.log.append(f"Case 2: Parent {z.parent.key} & Uncle {uncle.key} are RED → recolor")
                    z.parent.color = BLACK
                    uncle.color = BLACK
                    z.parent.parent.color = RED
                    self.recolor_count += 3
                    z = z.parent.parent
                else:
                    if z == z.parent.left:
                        self.log.append(f"Case 3: Triangle at {z.key} → right rotate parent {z.parent.key}")
                        z = z.parent
                        self._rotate_right(z)
                    self.log.append(f"Case 4: Line → left rotate grandparent {z.parent.parent.key} + recolor")
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self.recolor_count += 2
                    self._rotate_left(z.parent.parent)

        if self.root.color == RED:
            self.log.append(f"Root recolored to BLACK")
            self.root.color = BLACK
            self.recolor_count += 1

    # ── delete helpers ────────────────────────────────────────────────

    def _transplant(self, u: RBNode, v: RBNode) -> None:
        if u.parent == self.NIL:
            self.root = v
        elif u == u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        v.parent = u.parent

    def _delete_node(self, z: RBNode) -> None:
        y = z
        y_original_color = y.color

        if z.left == self.NIL:
            x = z.right
            self.log.append(f"  - Removing {z.key} (no left child)")
            self._transplant(z, z.right)
        elif z.right == self.NIL:
            x = z.left
            self.log.append(f"  - Removing {z.key} (no right child)")
            self._transplant(z, z.left)
        else:
            y = self._minimum(z.right)
            y_original_color = y.color
            x = y.right
            self.log.append(f"  - Replacing {z.key} with successor {y.key}")
            if y.parent == z:
                x.parent = y
            else:
                self._transplant(y, y.right)
                y.right = z.right
                y.right.parent = y
            self._transplant(z, y)
            y.left = z.left
            y.left.parent = y
            y.color = z.color

        if y_original_color == BLACK:
            self.log.append(f"  - Deleted node was BLACK → fix-up needed")
            self._delete_fixup(x)

    def _delete_fixup(self, x: RBNode) -> None:
        while x != self.root and x.color == BLACK:
            if x == x.parent.left:
                w = x.parent.right  # sibling
                if w.color == RED:
                    self.log.append(f"    Delete Case 1: Sibling {w.key} is RED → rotate + recolor")
                    w.color = BLACK
                    x.parent.color = RED
                    self._rotate_left(x.parent)
                    w = x.parent.right
                if w.left.color == BLACK and w.right.color == BLACK:
                    self.log.append(f"    Delete Case 2: Sibling's children both BLACK → recolor sibling {w.key}")
                    w.color = RED
                    self.recolor_count += 1
                    x = x.parent
                else:
                    if w.right.color == BLACK:
                        self.log.append(f"    Delete Case 3: Sibling's far child BLACK → rotate sibling")
                        w.left.color = BLACK
                        w.color = RED
                        self._rotate_right(w)
                        w = x.parent.right
                    self.log.append(f"    Delete Case 4: Sibling's far child RED → rotate parent + recolor")
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.right.color = BLACK
                    self._rotate_left(x.parent)
                    self.recolor_count += 3
                    x = self.root
            else:
                w = x.parent.left
                if w.color == RED:
                    self.log.append(f"    Delete Case 1: Sibling {w.key} is RED → rotate + recolor")
                    w.color = BLACK
                    x.parent.color = RED
                    self._rotate_right(x.parent)
                    w = x.parent.left
                if w.right.color == BLACK and w.left.color == BLACK:
                    self.log.append(f"    Delete Case 2: Sibling's children both BLACK → recolor sibling {w.key}")
                    w.color = RED
                    self.recolor_count += 1
                    x = x.parent
                else:
                    if w.left.color == BLACK:
                        self.log.append(f"    Delete Case 3: Sibling's far child BLACK → rotate sibling")
                        w.right.color = BLACK
                        w.color = RED
                        self._rotate_left(w)
                        w = x.parent.left
                    self.log.append(f"    Delete Case 4: Sibling's far child RED → rotate parent + recolor")
                    w.color = x.parent.color
                    x.parent.color = BLACK
                    w.left.color = BLACK
                    self._rotate_right(x.parent)
                    self.recolor_count += 3
                    x = self.root
        x.color = BLACK

    # ── internal helpers ──────────────────────────────────────────────

    def _search_node(self, node: RBNode, key: int) -> RBNode:
        while node != self.NIL and key != node.key:
            node = node.left if key < node.key else node.right
        return node

    def _search_bool(self, node: RBNode, key: int) -> bool:
        while node != self.NIL:
            self.comparison_count += 1
            if key == node.key:
                return True
            node = node.left if key < node.key else node.right
        return False

    def _minimum(self, node: RBNode) -> RBNode:
        while node.left != self.NIL:
            node = node.left
        return node

    def _inorder(self, node: RBNode, result: List[int]) -> None:
        if node != self.NIL:
            self._inorder(node.left, result)
            result.append(node.key)
            self._inorder(node.right, result)

    def _height(self, node: RBNode) -> int:
        if node == self.NIL:
            return 0
        return 1 + max(self._height(node.left), self._height(node.right))

    def _count(self, node: RBNode) -> int:
        if node == self.NIL:
            return 0
        return 1 + self._count(node.left) + self._count(node.right)

    def _check_no_red_red(self, node: RBNode, errors: List[str]) -> None:
        if node == self.NIL:
            return
        if node.color == RED:
            if node.left.color == RED:
                errors.append(f"Property 4: RED node {node.key} has RED left child {node.left.key}")
            if node.right.color == RED:
                errors.append(f"Property 4: RED node {node.key} has RED right child {node.right.key}")
        self._check_no_red_red(node.left, errors)
        self._check_no_red_red(node.right, errors)

    def _check_black_height(self, node: RBNode, errors: List[str]) -> int:
        if node == self.NIL:
            return 1
        lbh = self._check_black_height(node.left, errors)
        rbh = self._check_black_height(node.right, errors)
        if lbh != rbh and lbh != -1 and rbh != -1:
            errors.append(f"Property 5: Unequal black-height at node {node.key} (L={lbh}, R={rbh})")
            return -1
        return (lbh if lbh != -1 else rbh) + (1 if node.color == BLACK else 0)


# ═══════════════════════════════════════════════════════════════════════
#  3.  VISUAL TREE PRINTER
# ═══════════════════════════════════════════════════════════════════════

def print_tree(tree: RBTree, node: Optional[RBNode] = None,
               prefix: str = "", is_left: bool = True, is_root: bool = True) -> None:
    if node is None:
        node = tree.root
    if node == tree.NIL:
        return

    R = "\033[91m"   # bright red
    B = "\033[97m"   # bright white (for black nodes)
    DIM = "\033[90m"
    RESET = "\033[0m"

    color_tag = f"{R}R{RESET}" if node.color == RED else f"{B}B{RESET}"
    connector = "" if is_root else ("├── " if is_left else "└── ")
    new_prefix = prefix + ("" if is_root else ("│   " if is_left else "    "))

    print(f"{prefix}{connector}[{node.key} {color_tag}]")

    has_left = node.left != tree.NIL
    has_right = node.right != tree.NIL

    if has_left or has_right:
        if has_left:
            print_tree(tree, node.left, new_prefix, True, False)
        else:
            print(f"{new_prefix}├── {DIM}(NIL){RESET}")
        if has_right:
            print_tree(tree, node.right, new_prefix, False, False)
        else:
            print(f"{new_prefix}└── {DIM}(NIL){RESET}")


def display_tree(tree: RBTree, title: str = "") -> None:
    if title:
        print(f"\n{'─' * 50}")
        print(f"  {title}")
        print(f"{'─' * 50}")
    if tree.root == tree.NIL:
        print("  (empty tree)")
    else:
        print_tree(tree)
    print()


def print_log(tree: RBTree) -> None:
    for line in tree.log:
        print(f"  {line}")
    tree.clear_log()


# ═══════════════════════════════════════════════════════════════════════
#  4.  DEMO SCENARIO
# ═══════════════════════════════════════════════════════════════════════

def pause(msg: str = "Press Enter to continue...") -> None:
    input(f"\033[90m  {msg}\033[0m")


def demo_insertion_walkthrough():
    """Slides 8–9: step-by-step insertion of [10, 20, 30, 15]."""
    print("\n" + "=" * 60)
    print("  DEMO 1: INSERTION WALKTHROUGH")
    print("  Sequence: 10 → 20 → 30 → 15")
    print("=" * 60)

    tree = RBTree()
    for key in [10, 20, 30, 15]:
        tree.insert(key)
        print_log(tree)
        valid, errs = tree.validate()
        status = "✓ Valid" if valid else f"✗ {errs}"
        display_tree(tree, f"After inserting {key}  [{status}]")
        pause()



def demo_five_properties():
    """Slide 4: validate all 5 properties on a built tree."""
    print("\n" + "=" * 60)
    print("  DEMO 2: VALIDATING THE FIVE PROPERTIES")
    print("=" * 60)

    tree = RBTree()
    for k in [13, 8, 17, 1, 11, 15, 25, 6, 22, 27]:
        tree.insert(k)
    tree.clear_log()

    display_tree(tree, "Red-Black Tree with 10 nodes")

    valid, errors = tree.validate()
    n = tree.get_node_count()
    h = tree.get_height()
    bh = tree.get_black_height()

    print(f"  Property 1: Every node is RED or BLACK")
    print(f"  Property 2: Root ({tree.root.key}) is BLACK")
    print(f"  Property 3: All NIL leaves are BLACK (sentinel)")
    print(f"  Property 4: No red node has a red child")
    print(f"  Property 5: Black-height = {bh} on all paths")
    print()
    print(f"  Nodes: {n}  |  Height: {h}  |  Black-height: {bh}")
    print(f"  Theoretical max height: {2 * math.log2(n + 1):.1f}  (2·log₂(n+1))")
    print(f"  Validation: {'✓ ALL PROPERTIES SATISFIED' if valid else '✗ VIOLATIONS: ' + str(errors)}")
    pause()


def demo_deletion():
    """Slide 10: deletion with fix-up cases."""
    print("\n" + "=" * 60)
    print("  DEMO 4: DELETION WITH FIX-UP")
    print("=" * 60)

    tree = RBTree()
    for k in [20, 10, 30, 5, 15, 25, 35, 3, 7]:
        tree.insert(k)
    tree.clear_log()

    display_tree(tree, "Starting tree (9 nodes)")
    pause()

    for target in [35, 25, 20]:
        tree.delete(target)
        print_log(tree)
        valid, _ = tree.validate()
        display_tree(tree, f"After deleting {target}  [{'✓ Valid' if valid else '✗ Invalid'}]")
        pause()


# ═══════════════════════════════════════════════════════════════════════
#  5.  MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║        RED-BLACK TREES — DEMO APPLICATIONs                ║
╚═══════════════════════════════════════════════════════════╝
    """)

    demos = [
        ("Insertion Walkthrough (Slides 8-9)", demo_insertion_walkthrough),
        ("Validate the Five Properties (Slide 4)", demo_five_properties),
        ("Deletion with Fix-Up (Slide 10)", demo_deletion),
    ]

    print("  Select a demo:\n")
    for i, (name, _) in enumerate(demos, 1):
        print(f"    {i}. {name}")
    print(f"    A. Run all demos sequentially")
    print(f"    Q. Quit\n")

    while True:
        try:
            choice = input("  Enter choice: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if choice == "Q":
            break
        elif choice == "A":
            for _, func in demos[:-1]:
                func()
            print("\n  All demos complete!")
            break
        elif choice.isdigit() and 1 <= int(choice) <= len(demos):
            demos[int(choice) - 1][1]()
            if int(choice) == len(demos):
                break
        else:
            print("  Invalid choice.")


if __name__ == "__main__":
    main()
