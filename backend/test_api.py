import requests
import json

def test_motion_generation():
    url = "http://localhost:8000/api/generate-motion"
    payload = {
        "topic": "trygghet",
        "municipality": "karlstad",
        "year": 2024,
        "statistics": ["trygghet", "bra_statistik"]  # Using lowercase and adding BRÅ statistics
    }
    
    response = requests.post(url, json=payload)
    print("\nStatus Code:", response.status_code)
    print("\nResponse:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_motion_generation() 