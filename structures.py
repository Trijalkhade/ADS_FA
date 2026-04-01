import heapq
import csv
import os
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
#  EDIT DISTANCE
# ─────────────────────────────────────────────────────────────────────────────

def edit_distance_fast(word1, word2):
    """
    Optimised Levenshtein distance — O(m*n) time, O(n) space.
    Used internally by BKTree (no table needed).
    """
    m, n = len(word1), len(word2)
    if m == 0:
        return n
    if n == 0:
        return m
    # Early exit: length difference alone guarantees minimum distance
    if abs(m - n) > 3:
        return abs(m - n)

    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            if word1[i - 1] == word2[j - 1]:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr
    return prev[n]


def edit_distance(word1, word2):
    """
    Full Levenshtein with complete DP table returned.
    Used for visualisation (the animated grid in the UI).
    Returns: (distance, dp_table)
    """
    m, n = len(word1), len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i - 1] == word2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    return dp[m][n], dp


# ─────────────────────────────────────────────────────────────────────────────
#  TRIE
# ─────────────────────────────────────────────────────────────────────────────

class TrieNode:
    __slots__ = ['children', 'is_end', 'frequency', 'word', 'subtree_count']

    def __init__(self):
        self.children: dict = {}
        self.is_end: bool = False
        self.frequency: int = 0
        self.word: str | None = None
        self.subtree_count: int = 0   # words in subtree (set by compute_subtree_counts)


class Trie:
    def __init__(self):
        self.root = TrieNode()
        self.word_count = 0
        self.node_count = 1  # root counts as 1

    def insert(self, word: str, frequency: int):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
                self.node_count += 1
            node = node.children[char]
        node.is_end = True
        node.frequency = frequency
        node.word = word
        self.word_count += 1

    def compute_subtree_counts(self):
        """Post-order DFS — sets subtree_count on every node."""
        def _count(node: TrieNode) -> int:
            cnt = 1 if node.is_end else 0
            for child in node.children.values():
                cnt += _count(child)
            node.subtree_count = cnt
            return cnt
        _count(self.root)

    def get_children_info(self, path: str) -> dict | None:
        """
        Returns info about the node reached by 'path' and its children.
        path='' → root's children.
        Returns None if path is invalid.
        """
        node = self.root
        for ch in path:
            if ch not in node.children:
                return None
            node = node.children[ch]

        children = []
        for char, child in sorted(node.children.items()):
            children.append({
                'char':          char,
                'is_end':        child.is_end,
                'frequency':     child.frequency,
                'word':          child.word,
                'subtree_count': child.subtree_count,
                'has_children':  bool(child.children),
                'child_count':   len(child.children),
            })

        return {
            'path':          path,
            'is_end':        node.is_end,
            'word':          node.word,
            'subtree_count': node.subtree_count,
            'children':      children,
        }

    def autocomplete(self, prefix: str, k: int = 10):
        """
        Traverse to prefix end, collect top-k words by frequency.

        Returns:
            suggestions : list of {word, frequency}
            path_data   : list of {char, siblings, chosen} — one entry per
                          typed character, siblings = other letters available
                          at that same parent node (shown dimmed in the UI)
        """
        node = self.root
        path_data = []

        for char in prefix:
            # Record siblings at this level (other children of current node)
            siblings = sorted(node.children.keys())
            path_data.append({
                'char': char,
                'siblings': siblings,   # ALL options at this level
                'chosen': char,         # the one the user actually typed
                'valid': char in node.children
            })

            if char not in node.children:
                # Prefix not found — signal dead-end and stop
                return [], path_data

            node = node.children[char]

        # Mark whether the final node is a complete word
        if path_data:
            path_data[-1]['is_terminal'] = node.is_end

        # Iterative DFS to collect all words under this prefix node
        results = []
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur.is_end:
                results.append((cur.frequency, cur.word))
            stack.extend(cur.children.values())

        top_k = heapq.nlargest(k, results, key=lambda x: x[0])
        suggestions = [{'word': w, 'frequency': f} for f, w in top_k]

        return suggestions, path_data


# ─────────────────────────────────────────────────────────────────────────────
#  BK-TREE
# ─────────────────────────────────────────────────────────────────────────────

class BKTreeNode:
    __slots__ = ['word', 'children']

    def __init__(self, word: str):
        self.word = word
        self.children: dict[int, 'BKTreeNode'] = {}


class BKTree:
    def __init__(self):
        self.root: BKTreeNode | None = None
        self.size = 0

    def insert(self, word: str):
        if self.root is None:
            self.root = BKTreeNode(word)
            self.size += 1
            return

        node = self.root
        while True:
            dist = edit_distance_fast(word, node.word)
            if dist == 0:
                return  # duplicate — skip
            if dist not in node.children:
                node.children[dist] = BKTreeNode(word)
                self.size += 1
                return
            node = node.children[dist]

    def search(self, word: str, max_dist: int = 2, k: int = 10):
        """
        BK-Tree search. Candidates with edit-dist <= max_dist are returned.
        Also tracks which nodes were checked vs pruned (for visualisation).

        Returns:
            suggestions : list of {word, distance, frequency}  — sorted by dist
            checked     : list of {word, distance}             — nodes examined
            pruned      : list of {word}                       — nodes skipped
        """
        if self.root is None:
            return [], [], []

        suggestions = []
        checked = []
        pruned = []

        stack = [self.root]

        while stack:
            node = stack.pop()
            dist = edit_distance_fast(word, node.word)
            checked.append({'word': node.word, 'distance': dist})

            if dist <= max_dist:
                suggestions.append({'word': node.word, 'distance': dist})

            # BK invariant: only descend into children whose stored distance
            # falls within [dist - max_dist, dist + max_dist]
            lo, hi = dist - max_dist, dist + max_dist
            for child_dist, child_node in node.children.items():
                if lo <= child_dist <= hi:
                    stack.append(child_node)
                else:
                    pruned.append({'word': child_node.word})

        # Sort by edit distance, then caller enriches with frequency
        suggestions.sort(key=lambda x: x['distance'])

        # Cap lists to keep JSON payload small
        return suggestions[:k], checked[:100], pruned[:100]


# ─────────────────────────────────────────────────────────────────────────────
#  RED-BLACK TREE FOR EVENT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class Event:
    def __init__(self, id, name, date, time, event_type, location):
        self.id = id
        self.name = name
        self.date = date
        self.time = time
        self.event_type = event_type
        self.location = location
    
    def datetime_obj(self):
        return datetime.strptime(f"{self.date} {self.time}", "%d-%m-%Y %H:%M")
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'date': self.date,
            'time': self.time,
            'type': self.event_type,
            'location': self.location
        }

class RBNode:
    def __init__(self, event):
        self.event = event
        self.left = None
        self.right = None
        self.parent = None
        self.color = "RED"

class RedBlackTree:
    def __init__(self):
        self.NIL = RBNode(None)
        self.NIL.color = "BLACK"
        self.NIL.left = self.NIL.right = self.NIL
        self.root = self.NIL
        self.next_id = 1
        self.size = 0

    def left_rotate(self, x):
        y = x.right
        x.right = y.left
        if y.left != self.NIL:
            y.left.parent = x
        y.parent = x.parent
        if x.parent is None:
            self.root = y
        elif x == x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def right_rotate(self, x):
        y = x.left
        x.left = y.right
        if y.right != self.NIL:
            y.right.parent = x
        y.parent = x.parent
        if x.parent is None:
            self.root = y
        elif x == x.parent.right:
            x.parent.right = y
        else:
            x.parent.left = y
        y.right = x
        x.parent = y

    def fix_insert(self, z):
        while z.parent and z.parent.color == "RED":
            if z.parent == z.parent.parent.left:
                y = z.parent.parent.right
                if y.color == "RED":
                    z.parent.color = "BLACK"
                    y.color = "BLACK"
                    z.parent.parent.color = "RED"
                    z = z.parent.parent
                else:
                    if z == z.parent.right:
                        z = z.parent
                        self.left_rotate(z)
                    z.parent.color = "BLACK"
                    z.parent.parent.color = "RED"
                    self.right_rotate(z.parent.parent)
            else:
                y = z.parent.parent.left
                if y.color == "RED":
                    z.parent.color = "BLACK"
                    y.color = "BLACK"
                    z.parent.parent.color = "RED"
                    z = z.parent.parent
                else:
                    if z == z.parent.left:
                        z = z.parent
                        self.right_rotate(z)
                    z.parent.color = "BLACK"
                    z.parent.parent.color = "RED"
                    self.left_rotate(z.parent.parent)
        self.root.color = "BLACK"

    def insert(self, event):
        node = RBNode(event)
        node.left = self.NIL
        node.right = self.NIL

        y = None
        x = self.root
        while x != self.NIL:
            y = x
            if node.event.datetime_obj() < x.event.datetime_obj():
                x = x.left
            else:
                x = x.right

        node.parent = y
        if y is None:
            self.root = node
        elif node.event.datetime_obj() < y.event.datetime_obj():
            y.left = node
        else:
            y.right = node
        
        self.fix_insert(node)
        self.size += 1
        
    def insert_event(self, name, date, time, event_type, location):
        e = Event(
            id=self.next_id,
            name=name,
            date=date,
            time=time,
            event_type=event_type,
            location=location
        )
        self.insert(e)
        self.next_id += 1
        return e
        
    def transplant(self, u, v):
        if u.parent is None:
            self.root = v
        elif u == u.parent.left:
            u.parent.left = v
        else:
            u.parent.right = v
        v.parent = u.parent

    def minimum(self, node):
        while node.left != self.NIL:
            node = node.left
        return node

    def delete(self, event):
        z = self.root
        while z != self.NIL and z.event.id != event.id:
            if event.datetime_obj() < z.event.datetime_obj():
                z = z.left
            else:
                z = z.right
        if z == self.NIL:
            return False

        y = z
        y_original_color = y.color
        if z.left == self.NIL:
            x = z.right
            self.transplant(z, z.right)
        elif z.right == self.NIL:
            x = z.left
            self.transplant(z, z.left)
        else:
            y = self.minimum(z.right)
            y_original_color = y.color
            x = y.right
            if y.parent == z:
                x.parent = y
            else:
                self.transplant(y, y.right)
                y.right = z.right
                y.right.parent = y
            self.transplant(z, y)
            y.left = z.left
            y.left.parent = y
            y.color = z.color

        if y_original_color == "BLACK":
            self.fix_delete(x)

        self.size -= 1
        return True

    def fix_delete(self, x):
        while x != self.root and x.color == "BLACK":
            if x == x.parent.left:
                w = x.parent.right
                if w.color == "RED":
                    w.color = "BLACK"
                    x.parent.color = "RED"
                    self.left_rotate(x.parent)
                    w = x.parent.right
                if w.left.color == "BLACK" and w.right.color == "BLACK":
                    w.color = "RED"
                    x = x.parent
                else:
                    if w.right.color == "BLACK":
                        w.left.color = "BLACK"
                        w.color = "RED"
                        self.right_rotate(w)
                        w = x.parent.right
                    w.color = x.parent.color
                    x.parent.color = "BLACK"
                    w.right.color = "BLACK"
                    self.left_rotate(x.parent)
                    x = self.root
            else:
                w = x.parent.left
                if w.color == "RED":
                    w.color = "BLACK"
                    x.parent.color = "RED"
                    self.right_rotate(x.parent)
                    w = x.parent.left
                if w.right.color == "BLACK" and w.left.color == "BLACK":
                    w.color = "RED"
                    x = x.parent
                else:
                    if w.left.color == "BLACK":
                        w.right.color = "BLACK"
                        w.color = "RED"
                        self.left_rotate(w)
                        w = x.parent.left
                    w.color = x.parent.color
                    x.parent.color = "BLACK"
                    w.left.color = "BLACK"
                    self.right_rotate(x.parent)
                    x = self.root
        x.color = "BLACK"

    def inorder(self, node=None):
        if node is None:
            node = self.root
        if node == self.NIL:
            return []
        return self.inorder(node.left) + [node.event] + self.inorder(node.right)

    def get_events_chronological(self):
        return self.inorder()
    
    def find_by_id(self, event_id):
        events = self.inorder()
        for event in events:
            if event.id == event_id:
                return event
        return None
    
    def update_event(self, event_id, **kwargs):
        event = self.find_by_id(event_id)
        if not event:
            return False
        
        # Update event properties with proper field mapping
        for key, value in kwargs.items():
            if key == 'type':
                # Map 'type' to 'event_type' for the Event class
                setattr(event, 'event_type', value)
            elif hasattr(event, key):
                setattr(event, key, value)
        
        # Rebuild tree to maintain order
        events = self.inorder()
        self.root = self.NIL
        self.size = 0
        
        for e in events:
            self.insert(e)
        
        return True
    
    def get_stats(self):
        return {
            'total_events': self.size,
            'next_id': self.next_id,
            'tree_height': self._get_height(self.root),
            'black_height': self._get_black_height(self.root)
        }
    
    def _get_height(self, node):
        if node == self.NIL:
            return 0
        return 1 + max(self._get_height(node.left), self._get_height(node.right))
    
    def _get_black_height(self, node):
        if node == self.NIL:
            return 0
        left_bh = self._get_black_height(node.left)
        right_bh = self._get_black_height(node.right)
        bh = left_bh if left_bh == right_bh else max(left_bh, right_bh)
        return bh + (1 if node.color == "BLACK" else 0)
