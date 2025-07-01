from flask import Flask, request, jsonify
import requests
import re

from flask import Blueprint

weather_api = Blueprint('weather_api', __name__)

TOMORROW_API_KEY = "Gi0Ug2Yab5opfpbBy5fQ6J3lJdL9aAbG" 

def is_coordinate(location):
    """Validate latitude,longitude format"""
    pattern = r'^-?\d+\.?\d*,-?\d+\.?\d*$'
    if re.match(pattern, location):
        try:
            lat, lon = map(float, location.split(','))
            return -90 <= lat <= 90 and -180 <= lon <= 180
        except ValueError:
            return False
    return False

def get_weather_code_description(code):
    """Map weather codes to human-readable text"""
    weather_codes = {
        0: "Unknown",
        1000: "Clear",
        1001: "Cloudy",
        1100: "Mostly Clear",
        1101: "Partly Cloudy",
        1102: "Mostly Cloudy",
        2000: "Fog",
        2100: "Light Fog",
        4000: "Drizzle",
        4001: "Rain",
        4200: "Light Rain",
        4201: "Heavy Rain",
        5000: "Snow",
        5001: "Flurries",
        5100: "Light Snow",
        5101: "Heavy Snow",
        8000: "Thunderstorm"
    }
    return weather_codes.get(code, "Unknown")

def degrees_to_direction(degrees):
    """Convert wind direction degrees to compass direction"""
    directions = ["North", "North-East", "East", "South-East",
                 "South", "South-West", "West", "North-West"]
    return directions[round(degrees % 360 / 45) % 8] if degrees else "Unknown"

@weather_api.route('/weather', methods=['GET'])
def get_weather():
    location = request.args.get('location')
    if not location:
        return jsonify({"error": "Location parameter is required"}), 400

    try:
        # Handle coordinates or geocode location name
        if is_coordinate(location):
            lat, lon = map(float, location.split(','))
            location_name = location
        else:
            # Geocode location name to coordinates
            geocode_url = "https://api.tomorrow.io/v4/geocode/search"
            headers = {'apikey': TOMORROW_API_KEY}
            params = {'query': location, 'limit': 1}
            
            geo_response = requests.get(geocode_url, headers=headers, params=params)
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            
            if not geo_data.get('features'):
                return jsonify({"error": "Location not found"}), 404
                
            feature = geo_data['features'][0]
            lon, lat = feature['geometry']['coordinates']
            location_name = feature['properties']['name']

        # Get weather data
        weather_url = "https://api.tomorrow.io/v4/weather/realtime"
        headers = {'apikey': TOMORROW_API_KEY}
        params = {
            'location': f"{lat},{lon}",
            'units': 'metric',
            'fields': ','.join([
                'temperature',
                'weatherCode',
                'windSpeed',
                'windDirection',
                'humidity',
                'precipitationIntensity',
                'pressureSurfaceLevel'
            ])
        }
        
        weather_response = requests.get(weather_url, headers=headers, params=params)
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        if 'data' not in weather_data:
            return jsonify({"error": "Invalid API response format"}), 500

        values = weather_data['data']['values']

        return jsonify({
            "location": location_name,
            "real_time_weather": {
                "temperature": values.get('temperature'),
                "weather_condition": get_weather_code_description(values.get('weatherCode')),
                "wind_speed": values.get('windSpeed'),
                "wind_direction": degrees_to_direction(values.get('windDirection')),
                "humidity": values.get('humidity'),
                "precipitation": values.get('precipitationIntensity', 0),
                "air_pressure": values.get('pressureSurfaceLevel')
            }
        })

    except requests.exceptions.HTTPError as e:
        return jsonify({
            "error": f"API request failed",
            "details": f"{e.response.status_code} - {e.response.text}"
        }), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500




#http://127.0.0.1:9000/weather?location=28.6139,77.2090