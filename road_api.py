from flask import Flask, jsonify, request
import requests

from flask import Blueprint

road_api = Blueprint('road_api', __name__)

ORS_API_KEY = "5b3ce3597851110001cf62481f032e166f6e4d15af01bfe0ef9bec04"
DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"

def geocode_place(place_name):
    headers = {'Authorization': ORS_API_KEY}
    params = {'text': place_name, 'size': 1}
    try:
        response = requests.get(GEOCODE_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data['features'][0]['geometry']['coordinates'] if data.get('features') else None
    except:
        return None

@road_api.route('/route', methods=['GET'])
def get_route():
    start = request.args.get('start')
    end = request.args.get('end')

    if not start or not end:
        return jsonify({"error": "Missing start/end parameters"}), 400

    start_coords = geocode_place(start)
    end_coords = geocode_place(end)

    if not start_coords or not end_coords:
        return jsonify({"error": "Invalid location(s)"}), 400

    try:
        response = requests.get(
            DIRECTIONS_URL,
            headers={'Authorization': ORS_API_KEY},
            params={'start': f"{start_coords[0]},{start_coords[1]}",
                    'end': f"{end_coords[0]},{end_coords[1]}"}
        )
        data = response.json()
        route = data['features'][0]['properties']['segments'][0]
        duration = route['duration']
        
        # Calculate hours and minutes
        hours = int(duration // 3600)
        minutes = round((duration % 3600) / 60, 1)
        
        return jsonify({
            "start": start,
            "end": end,
            "distance_km": round(route['distance']/1000, 2),
            "duration_minutes": round(duration/60, 1),
            "eta": {
                "hours": hours,
                "minutes": minutes
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500





#http://127.0.0.1:5000/route?start=NewDelhi&end=Mumbai
