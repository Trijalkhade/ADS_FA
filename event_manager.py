"""
event_manager.py — Event management system integrating Red-Black Tree, Trie, and BK-Tree
"""

import os
import pickle
import re
from datetime import datetime
from structures import RedBlackTree, Event, Trie, BKTree, edit_distance_fast

# Validation patterns
valid_date = re.compile(r"^([0-2]\d|3[01])-(0\d|1[0-2])-(\d{4})$")
valid_time = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

def isvalid_date(d: str) -> bool:
    if not valid_date.match(d or ""):
        return False
    try:
        datetime.strptime(d, "%d-%m-%Y")
        return True
    except ValueError:
        return False
    
def isvalid_time(t: str) -> bool:
    return bool(valid_time.match(t or ""))

class EventManager:
    def __init__(self):
        self.rbt = RedBlackTree()
        self.name_trie = Trie()      # For event name autocomplete
        self.location_trie = Trie()  # For location autocomplete
        self.search_tree = BKTree() # For fuzzy event search
        self.cache_file = "events_cache.pkl"
        
    def load_cache(self):
        """Load events from cache file if exists"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self.rbt = data['rbt']
                    self.name_trie = data['name_trie']
                    self.location_trie = data['location_trie']
                    self.search_tree = data['search_tree']
                print(f"[*] Loaded {self.rbt.size} events from cache")
                return True
            except Exception as e:
                print(f"[!] Cache loading failed: {e}")
        return False
    
    def save_cache(self):
        """Save events to cache file"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump({
                    'rbt': self.rbt,
                    'name_trie': self.name_trie,
                    'location_trie': self.location_trie,
                    'search_tree': self.search_tree
                }, f)
            print(f"[*] Saved {self.rbt.size} events to cache")
        except Exception as e:
            print(f"[!] Cache saving failed: {e}")
    
    def add_event(self, name, date, time, event_type, location):
        """Add a new event to all data structures"""
        if not isvalid_date(date):
            raise ValueError("Invalid date format. Use DD-MM-YYYY")
        if not isvalid_time(time):
            raise ValueError("Invalid time format. Use HH:MM")
        
        # Add to Red-Black Tree
        event = self.rbt.insert_event(name, date, time, event_type, location)
        
        # Add to name Trie for autocomplete (insert individual words)
        name_words = name.lower().split()
        for word in name_words:
            if word.isalpha():
                self.name_trie.insert(word, 1)
        
        # Add location to location Trie
        words = location.lower().split()
        for word in words:
            if word.isalpha():
                self.location_trie.insert(word, 1)
        
        # Add to search BK-Tree for fuzzy search — insert individual words
        searchable_text = f"{name} {event_type} {location}".lower()
        for word in searchable_text.split():
            if word.isalpha() and len(word) >= 2:
                self.search_tree.insert(word)
        
        self.save_cache()
        return event
    
    def delete_event(self, event_id):
        """Delete an event by ID"""
        event = self.rbt.find_by_id(event_id)
        if not event:
            return False
        
        # Remove from Red-Black Tree
        success = self.rbt.delete(event)
        
        if success:
            # Rebuild other structures (simpler than selective removal)
            self._rebuild_search_structures()
            self.save_cache()
        
        return success
    
    def update_event(self, event_id, **kwargs):
        """Update event properties"""
        # Validate date/time if provided
        if 'date' in kwargs:
            date = kwargs['date']
            if not date.strip():  # Allow empty date for partial updates
                pass
            elif not isvalid_date(date):
                raise ValueError("Invalid date format. Use DD-MM-YYYY")
        
        if 'time' in kwargs:
            time = kwargs['time']
            if not time.strip():  # Allow empty time for partial updates
                pass
            elif not isvalid_time(time):
                raise ValueError("Invalid time format. Use HH:MM")
        
        success = self.rbt.update_event(event_id, **kwargs)
        
        if success:
            # Rebuild search structures to reflect changes
            self._rebuild_search_structures()
            self.save_cache()
        
        return success
    
    def get_events_chronological(self):
        """Get all events in chronological order"""
        return [event.to_dict() for event in self.rbt.get_events_chronological()]
    
    def autocomplete_name(self, prefix, k=10):
        """Get autocomplete suggestions for event names"""
        suggestions, _ = self.name_trie.autocomplete(prefix.lower(), k)
        return [s['word'] for s in suggestions]
    
    def autocomplete_location(self, prefix, k=10):
        """Get autocomplete suggestions for locations"""
        suggestions, _ = self.location_trie.autocomplete(prefix.lower(), k)
        return [s['word'] for s in suggestions]
    
    def search_events(self, query, max_dist=2, k=10):
        """
        Search events using a pure Trie + BK-Tree pipeline — no raw string ops.

        Pipeline per query word:
          1. name_trie.autocomplete()     → prefix-matched event-name words
          2. location_trie.autocomplete() → prefix-matched location words
          3. search_tree.search()         → BK-Tree fuzzy match (typo tolerance)
        Then scans the RBT inorder for events whose word-set overlaps the
        combined candidates.  All query words must match for an event to qualify.
        """
        all_events = self.rbt.get_events_chronological()
        if not all_events:
            return [], [], []

        query_words = [w for w in query.lower().split() if w.isalpha() and len(w) >= 2]
        if not query_words:
            return [], [], []

        all_checked: list = []
        all_pruned:  list = []

        # Build a candidate-word dict for each query word
        # candidate dict: { matched_word -> min_edit_distance }
        per_word_candidates = []
        for qword in query_words:
            candidates: dict[str, int] = {}

            # — Trie path 1: name words (prefix match) ————————————————————
            for s in self.name_trie.autocomplete(qword, k=20)[0]:
                w = s['word']
                # prefix match: distance proportional to extra chars appended
                d = max(0, len(w) - len(qword)) if w.startswith(qword) else edit_distance_fast(qword, w)
                candidates[w] = min(candidates.get(w, 9999), d)

            # — Trie path 2: location words (prefix match) ————————————————
            for s in self.location_trie.autocomplete(qword, k=20)[0]:
                w = s['word']
                d = max(0, len(w) - len(qword)) if w.startswith(qword) else edit_distance_fast(qword, w)
                candidates[w] = min(candidates.get(w, 9999), d)

            # — BK-Tree path: fuzzy / typo-tolerant ———————————————————————
            if self.search_tree.root is not None:
                bk_hits, checked, pruned = self.search_tree.search(qword, max_dist, k * 3)
                all_checked.extend(checked)
                all_pruned.extend(pruned)
                for s in bk_hits:
                    w = s['word']
                    candidates[w] = min(candidates.get(w, 9999), s['distance'])

            per_word_candidates.append(candidates)

        # Scan RBT (already inorder = chronological) for qualifying events
        matched_events = []
        seen_ids: set = set()

        for event in all_events:
            if event.id in seen_ids:
                continue

            event_words = set(
                w for w in
                f"{event.name} {event.event_type} {event.location}".lower().split()
                if w.isalpha()
            )

            # Every query word must find ≥1 candidate inside this event's words
            event_dist = 0
            all_match = True
            for candidates in per_word_candidates:
                overlap = {w: d for w, d in candidates.items() if w in event_words}
                if not overlap:
                    all_match = False
                    break
                event_dist = max(event_dist, min(overlap.values()))

            if not all_match:
                continue

            matched_events.append({'event': event.to_dict(), 'distance': event_dist})
            seen_ids.add(event.id)

        matched_events.sort(key=lambda x: x['distance'])
        return matched_events[:k], all_checked[:100], all_pruned[:100]
    
    def get_event_by_id(self, event_id):
        """Get event by ID"""
        event = self.rbt.find_by_id(event_id)
        return event.to_dict() if event else None
    
    def get_stats(self):
        """Get statistics about all data structures"""
        rbt_stats = self.rbt.get_stats()
        
        return {
            'red_black_tree': rbt_stats,
            'name_trie': {
                'nodes': self.name_trie.node_count,
                'words': self.name_trie.word_count
            },
            'location_trie': {
                'nodes': self.location_trie.node_count,
                'words': self.location_trie.word_count
            },
            'search_tree': {
                'size': self.search_tree.size
            }
        }
    
    def _rebuild_search_structures(self):
        """Rebuild Trie and BK-Tree from current events"""
        events = self.rbt.get_events_chronological()
        
        # Clear existing structures
        self.name_trie = Trie()
        self.location_trie = Trie()
        self.search_tree = BKTree()
        
        # Rebuild from events
        for event in events:
            # Name trie (insert individual words)
            name_words = event.name.lower().split()
            for word in name_words:
                if word.isalpha():
                    self.name_trie.insert(word, 1)
            
            # Location trie
            words = event.location.lower().split()
            for word in words:
                if word.isalpha():
                    self.location_trie.insert(word, 1)
            
            # Search BK-Tree — insert individual words so short queries can match
            searchable_text = f"{event.name} {event.event_type} {event.location}".lower()
            for word in searchable_text.split():
                if word.isalpha() and len(word) >= 2:
                    self.search_tree.insert(word)
    
    def add_sample_events(self):
        """Add sample events for testing"""
        sample_events = [
            ("Team Meeting", "15-04-2026", "10:00", "work", "Conference Room A"),
            ("Birthday Party", "20-04-2026", "18:00", "personal", "Home"),
            ("Project Deadline", "25-04-2026", "23:59", "work", "Office"),
            ("Doctor Appointment", "05-05-2026", "14:30", "health", "City Hospital"),
            ("Conference Call", "10-05-2026", "15:00", "work", "Virtual"),
            ("Lunch with Client", "12-05-2026", "12:30", "work", "Restaurant Downtown"),
            ("Gym Session", "08-05-2026", "06:00", "personal", "Fitness Center"),
            ("Book Club Meeting", "18-05-2026", "19:00", "hobby", "Local Library"),
            ("Family Dinner", "22-05-2026", "20:00", "personal", "Parents' House"),
            ("Workshop", "28-05-2026", "09:00", "education", "Training Center")
        ]
        
        for name, date, time, event_type, location in sample_events:
            try:
                self.add_event(name, date, time, event_type, location)
            except Exception as e:
                print(f"Error adding sample event '{name}': {e}")
        
        print(f"[*] Added {len(sample_events)} sample events")
