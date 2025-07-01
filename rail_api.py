import http.client
import json
from flask import Flask, request, jsonify
from flask import Blueprint

rail_api = Blueprint('rail_api', __name__)

RAPIDAPI_KEY = "58a0107736msh08f7d81311e66e9p1863b4jsn3d8c8c29644d"
RAPIDAPI_HOST = "indian-railway-irctc.p.rapidapi.com"
RAPIDAPI_OTHER_HEADER = "rapid-api-database"

CITIES = [
    "New Delhi",
    "Mumbai",
    "Bangalore",
    "Chennai",
    "Kolkata",
    "Hyderabad",
    "Ahmedabad",
    "Pune",
    "Jaipur",
    "Lucknow"
]

def fetch_train_by_name_or_number(train_identifier):
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    headers = {
        'x-rapidapi-key': RAPIDAPI_KEY,
        'x-rapidapi-host': RAPIDAPI_HOST,
        'x-rapid-api': RAPIDAPI_OTHER_HEADER
    }
    endpoint = f"/api/trains-search/v1/train/{train_identifier}?isH5=true&client=web"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()
    try:
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        return {"error": "Failed to parse API response", "exception": str(e)}

@rail_api.route('/train-info/<train_identifier>', methods=['GET'])
def get_train_schedule(train_identifier):
    api_response = fetch_train_by_name_or_number(train_identifier)
    
    try:
        body_data = api_response.get("body", [])
        if not body_data:
            return jsonify({"error": "No train data found"}), 404
            
        trains_data = body_data[0].get("trains", [])
        if not trains_data:
            return jsonify({"error": "No train data found"}), 404

        formatted_trains = []
        for train in trains_data:
            schedule = train.get("schedule", [])
            filtered_schedule = [
                {
                    k: v for k, v in stop.items()
                    if k in ["arrivalTime", "departureTime", "distance", 
                            "haltTime", "routeNumber", "stationCode", 
                            "stationName", "stnSerialNumber"]
                }
                for stop in schedule
                if any(city.lower() in stop.get("stationName", "").lower() 
                      for city in CITIES)
            ]
            
            formatted_trains.append({
                "train_name": train.get("trainName"),
                "train_number": train.get("trainNumber"),
                "schedule": filtered_schedule
            })

        return jsonify({
            "indian_railways": {
                "trains": formatted_trains
            }
        })
        
    except Exception as e:
        return jsonify({
            "indian_railways": {
                "error": "Processing failed",
                "details": str(e)
            }
        }), 500




#http://127.0.0.1:8000/train-info/12002