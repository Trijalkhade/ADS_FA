"""
app.py — Flask backend for AutoMind
Routes:
  GET  /              → serves index.html
  GET  /stats         → structure sizes
  GET  /graph-data    → letter co-occurrence graph (nodes + edges)
  POST /autocomplete  → {prefix, k}  → {suggestions, path, stats}
  POST /autocorrect   → {word, k}    → {suggestions, checked, pruned,
                                         dp_table, dp_rows, dp_cols,
                                         best_match, stats}
"""

import time
from flask import Flask, render_template, request, jsonify

from dataset import trie, bktree, word_freq, letter_frequency, letter_edges, bigram_freq
from structures import edit_distance
from event_manager import EventManager

app = Flask(__name__)

# Initialize Event Manager
event_manager = EventManager()
event_manager.load_cache()

# Add sample events if no events exist
if event_manager.rbt.size == 0:
    event_manager.add_sample_events()


# ── helpers ──────────────────────────────────────────────────────────────────

def _bad_request(msg: str):
    return jsonify({'error': msg}), 400


# ── routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/stats')
def stats():
    # Compute max depth and leaves on the fly. Since it's only 25k nodes, DFS is fast.
    def get_max_depth(node):
        if not node.children:
            return 0
        return 1 + max(get_max_depth(child) for child in node.children.values())

    leaf_count = 0
    stack = [trie.root]
    while stack:
        curr = stack.pop()
        if not curr.children:
            leaf_count += 1
        else:
            stack.extend(curr.children.values())

    total_chars = sum(len(w) for w in word_freq.keys())

    return jsonify({
        'trie_nodes':  trie.node_count,
        'trie_edges':  trie.node_count - 1 if trie.node_count > 0 else 0,
        'trie_words':  trie.word_count,
        'bktree_size': bktree.size,
        'max_level':   get_max_depth(trie.root),
        'leaf_nodes':  leaf_count,
        'root_nodes':  1,
        'total_chars': total_chars,
    })


@app.route('/trie-node')
def trie_node():
    """
    Lazily loads one level of the Trie for the interactive graph.
    ?path=  (empty = root)
    Returns: {path, is_end, word, subtree_count, children[{char, is_end,
              frequency, word, subtree_count, has_children, child_count,
              bigram_weight}]}
    """
    path = request.args.get('path', '').strip().lower()
    info = trie.get_children_info(path)

    if info is None:
        return jsonify({'error': f'Path not found: {path}'}), 404

    # Attach bigram weight (parent_char -> child_char co-occurrence)
    parent_char = path[-1] if path else ''
    for child in info['children']:
        bw = bigram_freq.get((parent_char, child['char']), 0.0) if parent_char else 0.0
        child['bigram_weight'] = round(bw, 4)

    return jsonify(info)


@app.route('/graph-data')
def graph_data():
    """
    Returns letter co-occurrence graph for visualisation.
    Nodes: 26 letters with relative frequency sizes.
    Edges: bigram pairs weighted by corpus co-occurrence.
    """
    nodes = [
        {
            'id':        ch,
            'frequency': letter_frequency.get(ch, 0.0),
        }
        for ch in 'abcdefghijklmnopqrstuvwxyz'
    ]
    return jsonify({'nodes': nodes, 'edges': letter_edges})


@app.route('/autocomplete', methods=['POST'])
def autocomplete():
    data   = request.get_json(force=True) or {}
    prefix = data.get('prefix', '').strip().lower()
    k      = int(data.get('k', 10))

    if not prefix:
        return jsonify({'suggestions': [], 'path': [], 'stats': {}})

    t0 = time.perf_counter()
    suggestions, path = trie.autocomplete(prefix, k)
    elapsed = round((time.perf_counter() - t0) * 1000, 2)

    return jsonify({
        'suggestions': suggestions,
        'path':        path,
        'stats': {
            'time_ms':       elapsed,
            'matches':       len(suggestions),
            'prefix_length': len(prefix),
        },
    })


@app.route('/autocorrect', methods=['POST'])
def autocorrect():
    data     = request.get_json(force=True) or {}
    word     = data.get('word', '').strip().lower()
    k        = int(data.get('k', 10))
    max_dist = int(data.get('max_dist', 2))

    if not word:
        return jsonify({
            'suggestions': [], 'checked': [], 'pruned': [],
            'dp_table': [], 'dp_rows': [], 'dp_cols': [],
            'best_match': None, 'stats': {},
        })

    t0 = time.perf_counter()
    suggestions, checked, pruned = bktree.search(word, max_dist=max_dist, k=k)

    # Enrich suggestions with normalised frequency from dataset
    for s in suggestions:
        s['frequency'] = word_freq.get(s['word'], 1)

    # DP table for the best match (first suggestion, or word itself)
    best_match = suggestions[0]['word'] if suggestions else word
    best_dist, dp_table = edit_distance(word, best_match)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)

    return jsonify({
        'suggestions':   suggestions[:k],
        'checked':       checked,
        'pruned':        pruned,
        'dp_table':      dp_table,
        'dp_rows':       [''] + list(word),        # row headers (source word)
        'dp_cols':       [''] + list(best_match),  # col headers (target word)
        'best_match':    best_match,
        'best_distance': best_dist,
        'stats': {
            'time_ms':       elapsed,
            'nodes_visited': len(checked),
            'nodes_pruned':  len(pruned),
            'matches':       len(suggestions),
        },
    })


# ── Event Management Routes ─────────────────────────────────────────────────────

@app.route('/events')
def get_events():
    """Get all events in chronological order"""
    events = event_manager.get_events_chronological()
    return jsonify({'events': events})

@app.route('/events', methods=['POST'])
def add_event():
    """Add a new event"""
    data = request.get_json(force=True) or {}
    
    try:
        name = data.get('name', '').strip()
        date = data.get('date', '').strip()
        time = data.get('time', '').strip()
        event_type = data.get('type', '').strip()
        location = data.get('location', '').strip()
        
        if not all([name, date, time, event_type, location]):
            return jsonify({'error': 'All fields are required'}), 400
        
        event = event_manager.add_event(name, date, time, event_type, location)
        return jsonify({'event': event.to_dict(), 'message': 'Event added successfully'})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to add event'}), 500

@app.route('/events/<int:event_id>')
def get_event(event_id):
    """Get a specific event by ID"""
    event = event_manager.get_event_by_id(event_id)
    if event:
        return jsonify({'event': event})
    else:
        return jsonify({'error': 'Event not found'}), 404

@app.route('/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    """Update an existing event"""
    try:
        data = request.get_json(force=True) or {}
        
        # Filter valid fields
        valid_fields = ['name', 'date', 'time', 'type', 'location']
        update_data = {k: v for k, v in data.items() if k in valid_fields}
        
        if not update_data:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        success = event_manager.update_event(event_id, **update_data)
        if success:
            event = event_manager.get_event_by_id(event_id)
            return jsonify({'event': event, 'message': 'Event updated successfully'})
        else:
            return jsonify({'error': 'Event not found'}), 404
            
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to update event'}), 500

@app.route('/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    """Delete an event"""
    try:
        success = event_manager.delete_event(event_id)
        if success:
            return jsonify({'message': 'Event deleted successfully'})
        else:
            return jsonify({'error': 'Event not found'}), 404
    except Exception as e:
        return jsonify({'error': 'Failed to delete event'}), 500

@app.route('/autocomplete/event-name', methods=['POST'])
def autocomplete_event_name():
    """
    Word-intelligence autocomplete for event name field.
    Splits the full input into already-typed words + the current word being
    typed, runs the same word-intelligence Trie against the last word, and
    returns completions along with the already-typed prefix so the JS can
    reconstruct the full suggestion (e.g. "Team " + "meet" → "Team meeting").
    """
    try:
        data = request.get_json(force=True) or {}
        full_input = data.get('prefix', '').strip().lower()
        k = int(data.get('k', 10))

        if not full_input:
            return jsonify({'suggestions': [], 'last_word': '', 'prefix_words': '', 'path': [], 'stats': {}})

        words = full_input.split()
        last_word    = words[-1] if words else ''
        prefix_words = (' '.join(words[:-1]) + ' ') if len(words) > 1 else ''

        t0 = time.perf_counter()
        suggestions_raw, path = trie.autocomplete(last_word, k)
        elapsed = round((time.perf_counter() - t0) * 1000, 2)

        return jsonify({
            'suggestions': [s['word'] for s in suggestions_raw],
            'last_word':   last_word,
            'prefix_words': prefix_words,   # words already typed before the current one
            'path':        path,
            'stats': {
                'time_ms':       elapsed,
                'matches':       len(suggestions_raw),
                'prefix_length': len(last_word),
            },
        })
    except Exception as e:
        return jsonify({'error': 'Autocomplete failed', 'suggestions': []}), 500

@app.route('/autocomplete/location', methods=['POST'])
def autocomplete_location():
    """Autocomplete for locations"""
    try:
        data = request.get_json(force=True) or {}
        prefix = data.get('prefix', '').strip().lower()
        k = int(data.get('k', 10))
        
        if not prefix:
            return jsonify({'suggestions': []})
        
        t0 = time.perf_counter()
        suggestions = event_manager.autocomplete_location(prefix, k)
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        
        return jsonify({
            'suggestions': suggestions,
            'stats': {
                'time_ms': elapsed,
                'matches': len(suggestions),
                'prefix_length': len(prefix)
            }
        })
    except Exception as e:
        return jsonify({'error': 'Autocomplete failed', 'suggestions': []}), 500

@app.route('/search-events', methods=['POST'])
def search_events():
    """Search events with typo tolerance"""
    try:
        data = request.get_json(force=True) or {}
        query = data.get('query', '').strip().lower()
        max_dist = int(data.get('max_dist', 2))
        k = int(data.get('k', 10))
        
        if not query:
            return jsonify({'events': [], 'checked': [], 'pruned': [], 'stats': {}})
        
        t0 = time.perf_counter()
        matched_events, checked, pruned = event_manager.search_events(query, max_dist, k)
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        
        return jsonify({
            'events': matched_events,
            'checked': checked,
            'pruned': pruned,
            'stats': {
                'time_ms': elapsed,
                'nodes_visited': len(checked),
                'nodes_pruned': len(pruned),
                'matches': len(matched_events)
            }
        })
    except Exception as e:
        return jsonify({'error': 'Search failed', 'events': [], 'stats': {}}), 500

@app.route('/event-stats')
def event_stats():
    """Get statistics about all data structures"""
    stats = event_manager.get_stats()
    return jsonify(stats)


if __name__ == '__main__':
    app.run(debug=True, port=5001)
