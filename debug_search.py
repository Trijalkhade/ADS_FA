#!/usr/bin/env python3
"""
Debug script to test search functionality directly
"""

import sys
sys.path.append('/Users/trijal/Downloads/ADS_FA')

from event_manager import EventManager

def test_search():
    em = EventManager()
    em.load_cache()
    
    # Test event map creation
    print("=== Events in RBT ===")
    events = em.rbt.get_events_chronological()
    event_map = {}
    
    for event in events:
        event_text = f"{event.name} {event.event_type} {event.location}".lower().strip()
        event_text = ' '.join(event_text.split())  # Normalize whitespace
        event_map[event_text] = event
        print(f"Event {event.id}: '{event_text}'")
    
    print(f"\n=== Event Map Keys ===")
    for key in event_map.keys():
        print(f"'{key}'")
    
    # Test search
    print(f"\n=== Search Test ===")
    query = "test"
    suggestions, checked, pruned = em.search_tree.search(query.lower(), 2, 10)
    
    print(f"Search suggestions for '{query}':")
    for suggestion in suggestions:
        event_text = suggestion['word'].strip()
        event_text = ' '.join(event_text.split())  # Normalize whitespace
        print(f"  Looking for: '{event_text}'")
        if event_text in event_map:
            print(f"  ✓ FOUND: {event_map[event_text].name}")
        else:
            print(f"  ✗ NOT FOUND")

if __name__ == "__main__":
    test_search()
