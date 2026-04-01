#!/usr/bin/env python3
"""
Test script to verify all POST endpoints and functionality
"""

import requests
import json

BASE_URL = "http://127.0.0.1:5001"

def test_endpoint(endpoint, method="GET", data=None):
    """Test an endpoint and return response"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "PUT":
            response = requests.put(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url)
        
        print(f"\n{method} {endpoint}")
        print(f"Status: {response.status_code}")
        
        try:
            json_data = response.json()
            print(f"Response: {json.dumps(json_data, indent=2)}")
        except:
            print(f"Response: {response.text}")
        
        return response
        
    except Exception as e:
        print(f"Error testing {endpoint}: {e}")
        return None

def main():
    print("Testing Smart Event Manager API...")
    
    # Test 1: Get all events
    test_endpoint("/events")
    
    # Test 2: Add a new event
    new_event = {
        "name": "Test Meeting",
        "date": "02-04-2026",
        "time": "14:30",
        "type": "work",
        "location": "Office"
    }
    response = test_endpoint("/events", "POST", new_event)
    
    if response and response.status_code == 200:
        event_data = response.json()
        event_id = event_data.get('event', {}).get('id')
        
        if event_id:
            # Test 3: Update the event
            update_data = {
                "name": "Updated Test Meeting",
                "time": "15:00"
            }
            test_endpoint(f"/events/{event_id}", "PUT", update_data)
            
            # Test 4: Get the updated event
            test_endpoint(f"/events/{event_id}")
            
            # Test 5: Delete the event
            test_endpoint(f"/events/{event_id}", "DELETE")
    
    # Test 6: Search events
    search_data = {
        "query": "meeting",
        "max_dist": 2,
        "k": 10
    }
    test_endpoint("/search-events", "POST", search_data)
    
    # Test 7: Autocomplete event names
    autocomplete_data = {
        "prefix": "meet",
        "k": 5
    }
    test_endpoint("/autocomplete/event-name", "POST", autocomplete_data)
    
    # Test 8: Autocomplete locations
    location_data = {
        "prefix": "off",
        "k": 5
    }
    test_endpoint("/autocomplete/location", "POST", location_data)
    
    # Test 9: Get stats
    test_endpoint("/event-stats")
    
    print("\nAPI testing completed!")

if __name__ == "__main__":
    main()
