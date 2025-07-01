import os
import json
import requests
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load fallback JSON data for weather, trains, and routes
try:
    with open('updated-data-weather.json', 'r') as f:
        fallback_weather_data = json.load(f).get('weather_data', [])
except Exception as e:
    logger.warning(f"Failed to load weather data: {e}")
    fallback_weather_data = []

try:
    with open('updated-json-data-for-train.json', 'r') as f:
        fallback_train_data = json.load(f).get('indian_railways', {}).get('trains', [])
except Exception as e:
    logger.warning(f"Failed to load train data: {e}")
    fallback_train_data = []

try:
    with open('updated-routes-data.json', 'r') as f:
        fallback_routes_data = json.load(f)
except Exception as e:
    logger.warning(f"Failed to load routes data: {e}")
    fallback_routes_data = []

# Load tourism and places information (new addition)
try:
    with open('tourism-data.json', 'r') as f:
        tourism_data = json.load(f)
except Exception as e:
    logger.warning(f"Failed to load tourism data: {e}")
    tourism_data = {
        "places": [
            {
                "name": "Mumbai",
                "description": "Financial capital of India with beautiful coastline",
                "best_time": "October to February",
                "attractions": ["Gateway of India", "Marine Drive", "Elephanta Caves"]
            },
            {
                "name": "Delhi",
                "description": "Capital city with rich historical heritage",
                "best_time": "October to March",
                "attractions": ["Red Fort", "India Gate", "Qutub Minar"]
            },
            {
                "name": "Jaipur",
                "description": "Pink City known for its palaces and forts",
                "best_time": "October to March",
                "attractions": ["Amber Fort", "Hawa Mahal", "City Palace"]
            },
            {
                "name": "Bangalore",
                "description": "Garden City and IT hub of India",
                "best_time": "September to February",
                "attractions": ["Lalbagh", "Cubbon Park", "Bangalore Palace"]
            }
        ]
    }

# Define helper functions
def get_weather(location):
    """Return current weather summary for the location, using API or fallback."""
    api_url = f"http://127.0.0.1:5000/weather?location={location}"
    logger.info(f"Fetching weather for {location}")
    
    try:
        res = requests.get(api_url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            weather = data.get('real_time_weather', {})
            return (f"The current weather in {data.get('location', location)} is "
                    f"{weather.get('weather_condition','Unknown')} with temperature "
                    f"{weather.get('temperature','N/A')}°C, humidity "
                    f"{weather.get('humidity','N/A')}%, wind "
                    f"{weather.get('wind_speed','N/A')} m/s "
                    f"{weather.get('wind_direction','')}.")
    except Exception as e:
        logger.warning(f"API request failed for weather ({location}): {e}")
    
    # Fallback to local JSON data
    for entry in fallback_weather_data:
        if entry.get('location','').lower() == location.lower():
            w = entry.get('real_time_weather', {})
            logger.info(f"Using fallback data for weather in {location}")
            return (f"The current weather in {location} is "
                    f"{w.get('weather_condition','Unknown')} with temperature "
                    f"{w.get('temperature','N/A')}°C, humidity "
                    f"{w.get('humidity','N/A')}%, wind "
                    f"{w.get('wind_speed','N/A')} m/s "
                    f"{w.get('wind_direction','')}.")
    
    return f"Sorry, I don't have weather data for {location}."

def get_train_by_number(train_number):
    """Return train schedule summary by train number, using API or fallback."""
    api_url = f"http://127.0.0.1:5000/train-info/{train_number}"
    logger.info(f"Fetching train info for train #{train_number}")
    
    try:
        res = requests.get(api_url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            trains = data.get('indian_railways', {}).get('trains', [])
            if trains:
                train = trains[0]  # Take first train
                name = train.get('train_name','')
                schedule = train.get('schedule', [])
                if schedule:
                    dep = schedule[0].get('departureTime','--')
                    arr = schedule[-1].get('arrivalTime','--')
                    dist = schedule[-1].get('distance','N/A')
                    return (f"Train {train_number} ({name}) starts at {dep} and ends "
                            f"at {arr}, covering {dist} km.")
    except Exception as e:
        logger.warning(f"API request failed for train info ({train_number}): {e}")
    
    # Fallback to local JSON data
    for train in fallback_train_data:
        if train.get('train_number') == str(train_number):
            name = train.get('train_name','')
            sched = train.get('schedule',[])
            if sched:
                logger.info(f"Using fallback data for train #{train_number}")
                dep = sched[0].get('departureTime','--')
                arr = sched[-1].get('arrivalTime','--')
                dist = sched[-1].get('distance','N/A')
                return (f"Train {train_number} ({name}) starts at {dep} and ends "
                        f"at {arr}, covering {dist} km.")
    
    return f"Sorry, no train with number {train_number} was found."

def get_trains_by_route(start, end):
    """Return schedules of trains between start and end stations."""
    api_url = f"http://127.0.0.1:5000/trains-between?start={start}&end={end}"
    logger.info(f"Fetching trains between {start} and {end}")
    
    try:
        res = requests.get(api_url, timeout=5)
        if res.status_code == 200:
            data = res.json().get('trains', [])
            if data:
                results = []
                for train in data[:3]:  # Limit to 3 trains for brevity
                    num = train.get('train_number')
                    name = train.get('train_name','')
                    dep = train.get('departure_time','--')
                    arr = train.get('arrival_time','--')
                    results.append(f"Train {num} ({name}) departs at {dep} and arrives at {arr}.")
                return " ".join(results)
    except Exception as e:
        logger.warning(f"API request failed for trains between {start} and {end}: {e}")
    
    # Fallback to local JSON data
    start_low = start.lower()
    end_low = end.lower()
    matches = []
    
    for train in fallback_train_data:
        schedule = train.get('schedule', [])
        indices = {}
        
        # Find start and end stations in the schedule
        for i, stop in enumerate(schedule):
            name = stop.get('stationName','').lower()
            if start_low in name:
                indices['start'] = i
            if end_low in name:
                indices['end'] = i
        
        if 'start' in indices and 'end' in indices and indices['start'] < indices['end']:
            num = train.get('train_number')
            name = train.get('train_name','')
            dep = schedule[indices['start']].get('departureTime','--')
            arr = schedule[indices['end']].get('arrivalTime','--')
            matches.append(f"Train {num} ({name}) departs at {dep} and arrives at {arr}.")
    
    if matches:
        logger.info(f"Using fallback data for trains between {start} and {end}")
        return " ".join(matches[:3])  # Limit to 3 trains for brevity
    
    return f"Sorry, no trains found from {start} to {end}."

def get_road_info(start, end):
    """Return driving time and distance between start and end (API or fallback)."""
    api_url = f"http://127.0.0.1:5000/route?start={start},India&end={end},India"
    logger.info(f"Fetching road info from {start} to {end}")
    
    try:
        res = requests.get(api_url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            eta = data.get('eta', {})
            hours = eta.get('hours', 0)
            minutes = eta.get('minutes', 0)
            dist = data.get('distance_km', 'N/A')
            return (f"By road, from {start} to {end} it takes about "
                    f"{hours} hours {minutes} minutes covering {dist} km.")
    except Exception as e:
        logger.warning(f"API request failed for road info ({start} to {end}): {e}")
    
    # Fallback to local JSON data
    for route in fallback_routes_data:
        s = route.get('start','').split(',')[0].lower()
        e = route.get('end','').split(',')[0].lower()
        if s == start.lower() and e == end.lower():
            logger.info(f"Using fallback data for road info from {start} to {end}")
            eta = route.get('eta', {})
            hours = eta.get('hours', 0)
            minutes = round(eta.get('minutes', 0))
            dist = route.get('distance_km', 'N/A')
            return (f"By road, from {start} to {end} it takes about "
                    f"{hours} hours {minutes} minutes covering {dist} km.")
    
    return f"Sorry, I don't have road info from {start} to {end}."

def get_place_info(place):
    """Return tourist information about a place."""
    for p in tourism_data.get('places', []):
        if p.get('name', '').lower() == place.lower():
            attractions = ", ".join(p.get('attractions', []))
            return (f"{place} - {p.get('description', '')}. "
                   f"The best time to visit is {p.get('best_time', 'any time of the year')}. "
                   f"Top attractions include: {attractions}.")
    
    return None

def get_best_time_to_visit(place):
    """Return the best time to visit a specific place."""
    for p in tourism_data.get('places', []):
        if p.get('name', '').lower() == place.lower():
            return f"The best time to visit {place} is {p.get('best_time', 'any time of the year')}."
    
    # If no specific data, return general seasonal advice
    current_month = datetime.now().month
    
    if place.lower() in ["rajasthan", "jaipur", "udaipur", "jodhpur", "jaisalmer"]:
        return f"The best time to visit {place} is from October to March when the weather is pleasant and not too hot."
    
    if place.lower() in ["goa", "mumbai", "kerala", "kochi"]:
        return f"The best time to visit {place} is from November to February when it's not monsoon season and the weather is comfortable."
    
    if place.lower() in ["delhi", "agra", "varanasi", "lucknow"]:
        return f"The best time to visit {place} is from October to March when the weather is cooler and more comfortable."
    
    if place.lower() in ["darjeeling", "gangtok", "shimla", "manali", "srinagar"]:
        return f"The best time to visit {place} is from March to June or September to November, avoiding the monsoon season."
    
    # Generic recommendation based on season
    if 11 <= current_month <= 12 or 1 <= current_month <= 2:
        return f"Currently it's winter in most of India, making it a good time to visit {place} if it's in the plains or southern India."
    elif 3 <= current_month <= 5:
        return f"Currently it's summer in India, making it a good time to visit hill stations like Shimla or Darjeeling. If {place} is in the plains, it might be quite hot."
    elif 6 <= current_month <= 9:
        return f"Currently it's monsoon season in most of India. If {place} is affected by monsoons, you might want to check the weather forecast before planning your trip."
    else:
        return f"The post-monsoon season (October) is generally a good time to visit most places in India, including {place}."

# ----------------- Improved Rule-based Classification -----------------
def extract_location_after_prep(message, prep):
    """Extract location after a preposition in a message."""
    if prep in message:
        parts = message.split(prep, 1)
        if len(parts) > 1:
            # Take the word after the preposition and strip punctuation
            location = ""
            words = parts[1].strip().split()
            for word in words:
                if word[0].isupper() or word.lower() in ["delhi", "mumbai", "chennai", "kolkata", "bangalore", 
                                                       "hyderabad", "jaipur", "pune", "ahmedabad", "lucknow"]:
                    location += word + " "
                else:
                    break
            return location.strip()
    return None

def extract_locations_from_route(message):
    """Extract start and end locations from a route query."""
    start, end = None, None
    
    # Pattern: from X to Y
    from_to_match = re.search(r'from\s+([a-zA-Z\s]+)\s+to\s+([a-zA-Z\s]+)', message, re.IGNORECASE)
    if from_to_match:
        start = from_to_match.group(1).strip()
        end = from_to_match.group(2).strip()
        # Clean up end location (remove trailing punctuation)
        end = re.split(r'[^a-zA-Z\s]', end)[0].strip()
        return start, end
    
    # Pattern: between X and Y
    between_match = re.search(r'between\s+([a-zA-Z\s]+)\s+and\s+([a-zA-Z\s]+)', message, re.IGNORECASE)
    if between_match:
        start = between_match.group(1).strip()
        end = between_match.group(2).strip()
        end = re.split(r'[^a-zA-Z\s]', end)[0].strip()
        return start, end
    
    # Pattern: to Y from X
    to_from_match = re.search(r'to\s+([a-zA-Z\s]+)\s+from\s+([a-zA-Z\s]+)', message, re.IGNORECASE)
    if to_from_match:
        end = to_from_match.group(1).strip()
        start = to_from_match.group(2).strip()
        start = re.split(r'[^a-zA-Z\s]', start)[0].strip()
        return start, end
    
    # Try to find any pair of cities in the query
    cities = ["delhi", "mumbai", "bangalore", "chennai", "kolkata", "hyderabad", 
              "ahmedabad", "pune", "jaipur", "lucknow", "agra", "varanasi", 
              "kochi", "goa", "srinagar", "shimla", "darjeeling"]
    found_cities = []
    
    for city in cities:
        if re.search(r'\b' + city + r'\b', message.lower()):
            found_cities.append(city.title())
    
    if len(found_cities) >= 2:
        return found_cities[0], found_cities[1]
        
    return None, None

def extract_train_numbers(message):
    """Extract 5-digit train numbers from message."""
    train_numbers = re.findall(r'\b(\d{5})\b', message)
    return train_numbers

def rule_based_classify(message):
    """Improved fallback classification when LLM is unavailable"""
    message = message.lower()
    
    # Extract any train numbers first - high confidence indicator
    train_numbers = extract_train_numbers(message)
    if train_numbers and ("train" in message or "railway" in message or "rail" in message):
        return {"intent": "train_number", "train_number": train_numbers[0]}
    
    # Weather intent detection (improved)
    weather_keywords = ["weather", "temperature", "raining", "rain", "sunny", 
                        "forecast", "humidity", "climate", "hot", "cold", 
                        "windy", "thunderstorm", "precipitation"]
    
    if any(word in message for word in weather_keywords):
        # Extract location using various prepositions
        location = None
        for prep in ["in ", "for ", "at ", " of "]:
            location = extract_location_after_prep(message, prep)
            if location:
                break
        
        # If no location found through prepositions, try to find any major city mentioned
        if not location:
            major_cities = ["delhi", "mumbai", "bangalore", "chennai", "kolkata", "hyderabad", 
                          "ahmedabad", "pune", "jaipur", "lucknow"]
            for city in major_cities:
                if city in message:
                    location = city.title()
                    break
        
        return {"intent": "weather", "location": location or "Delhi"}  # Default to Delhi if no location found
    
    # Trip planning intent detection - comprehensive
    trip_keywords = ["trip", "travel", "journey", "plan", "vacation", "holiday", "visit", 
                     "tour", "explore", "sightseeing", "tourist", "tourism"]
    
    if any(word in message for word in trip_keywords):
        start, end = extract_locations_from_route(message)
        if start and end:
            return {"intent": "trip_planning", "start": start, "end": end}
        elif end:  # If only destination is found
            return {"intent": "place_info", "location": end}
    
    # Place info intent detection
    place_keywords = ["about", "information", "tell me about", "what is", "attractions", 
                      "places to see", "tourist spots", "best time", "when to visit"]
    
    if any(phrase in message for phrase in place_keywords):
        # Try to extract location after key phrases
        location = None
        for phrase in ["about ", "visit ", "know about "]:
            location = extract_location_after_prep(message, phrase)
            if location:
                break
        
        # Check if we're specifically asking about best time to visit
        if "best time" in message or "when" in message and "visit" in message:
            return {"intent": "best_time", "location": location} if location else {"intent": "unknown"}
        
        if location:
            return {"intent": "place_info", "location": location}
    
    # Train route intent detection
    if ("train" in message or "rail" in message) and ("route" in message or "from" in message or "between" in message):
        start, end = extract_locations_from_route(message)
        if start and end:
            return {"intent": "train_route", "start": start, "end": end}
    
    # Road route intent detection
    road_keywords = ["road", "drive", "driving", "car", "bus", "route", "travel by road", 
                     "highway", "travel time", "how long", "how far"]
    
    if any(word in message for word in road_keywords):
        start, end = extract_locations_from_route(message)
        if start and end:
            return {"intent": "road", "start": start, "end": end}
    
    return {"intent": "unknown"}

# ----------------- HF Inference API Setup -----------------
# Read Hugging Face token from environment
load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
llm_client = None

if not HF_TOKEN:
    logger.warning("HF_TOKEN not found in environment. LLM features will be unavailable.")
else:
    try:
        llm_client = InferenceClient(
            provider="novita",
            api_key=HF_TOKEN
        )
        logger.info("HF Inference API successfully initialized")
    except Exception as e:
        logger.error(f"Failed to initialize HF Inference client: {e}")

# ----------------- Improved LLM Prompting -----------------
def classify_intent(message):
    """
    Ask the LLM to classify the intent and extract parameters.
    Returns the intent JSON dict, or uses rule-based fallback.
    """
    if not llm_client:
        logger.warning("LLM unavailable, using rule-based classification")
        return rule_based_classify(message)
    
    prompt = f"""
User message: "{message}"

Your task is to determine the user's intent and extract relevant parameters. The intent must be one of:
- "weather": User wants to know weather conditions for a specific location
- "train_number": User is asking about a specific train identified by its number
- "train_route": User wants to know about trains between two locations
- "road": User wants information about road travel between two places
- "trip_planning": User wants comprehensive travel information for a trip (multiple modes of transport)
- "place_info": User wants information about a specific place (tourist attractions, etc.)
- "best_time": User wants to know the best time to visit a place
- "unknown": The intent doesn't match any of the above categories

Extract the parameters carefully:
1. For "weather", "place_info", "best_time": Extract "location" (city/place name)
2. For "train_number": Extract "train_number" (5-digit number)
3. For "train_route" or "road": Extract "start" and "end" locations
4. For "trip_planning": Extract "start" and "end" locations

Parse carefully and focus on the actual request. For locations, extract proper nouns or place names.

Output format (JSON):
{{"intent": "one_of_the_intents", ...relevant_parameters}}

Examples:
- "What's the weather like in Mumbai?" → {{"intent":"weather", "location":"Mumbai"}}
- "Tell me about train 12345" → {{"intent":"train_number", "train_number":"12345"}}
- "Are there trains from Delhi to Mumbai?" → {{"intent":"train_route", "start":"Delhi", "end":"Mumbai"}}
- "How long does it take to drive from Bengaluru to Hyderabad?" → {{"intent":"road", "start":"Bengaluru", "end":"Hyderabad"}}
- "I'm planning a trip from Chennai to Kolkata" → {{"intent":"trip_planning", "start":"Chennai", "end":"Kolkata"}}
- "Tell me about attractions in Jaipur" → {{"intent":"place_info", "location":"Jaipur"}}
- "When is the best time to visit Goa?" → {{"intent":"best_time", "location":"Goa"}}

Return only the valid JSON object with one of the specified intents. Nothing else.
"""
    
    try:
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response_text = ""
        stream = llm_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=messages, 
            temperature=0.1,  # Low temperature for more deterministic output
            max_tokens=300,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response_text += chunk.choices[0].delta.content
        
        # Try to parse JSON response
        try:
            # Clean up response text - find the first { and last }
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result = json.loads(json_str)
                logger.info(f"LLM classification succeeded with result: {result}")
                return result
            else:
                raise ValueError("No JSON object found in response")
        except Exception as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}, response: {response_text}")
            return rule_based_classify(message)
            
    except Exception as e:
        logger.warning(f"LLM classification failed: {e}")
        return rule_based_classify(message)

def generate_response(message, data_collection=None, intent=None):
    """
    Ask the LLM to generate a conversational answer from data collection.
    Falls back to a simple template if LLM is unavailable.
    """
    if not data_collection:
        return "I don't have any information to share on that topic."
    
    if not llm_client:
        # Simple fallback response template
        return f"Here's what I found: {' '.join(data_collection)}"
    
    # Create a more specific prompt based on intent
    intent_context = ""
    if intent == "trip_planning":
        intent_context = "The user is planning a trip. Focus on providing helpful travel advice that covers transportation options, weather conditions, and attraction information in a well-organized way."
    elif intent == "place_info":
        intent_context = "The user wants information about a place. Focus on what makes this place special, attractions, and practical tips."
    elif intent in ["train_route", "train_number"]:
        intent_context = "The user wants train information. Provide clear details about schedules, timings, and any relevant travel tips."
    elif intent == "road":
        intent_context = "The user wants road travel information. Provide clear details about travel time, distance, and any relevant driving tips."
    
    prompt = f"""
The user asked: "{message}"

I've collected the following information to answer their question:
{' '.join(data_collection)}

{intent_context}

Your task is to create a helpful, conversational response that:
1. Directly addresses the user's query in a personalized way
2. Provides all the relevant information in a natural, well-organized manner
3. Is friendly and helpful, like a knowledgeable travel advisor
4. Includes practical advice where appropriate
5. Organizes information logically if there are multiple parts

Make your response sound natural and engaging, not like you're just reading data.
Do not mention "collected information" or the structure of this prompt in your answer.
Focus on giving the information the user wants in a clear, conversational style.
"""
    
    try:
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response_text = ""
        stream = llm_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=messages, 
            temperature=0.7,  # Higher temperature for more natural language
            max_tokens=800,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response_text += chunk.choices[0].delta.content
        
        return response_text
    except Exception as e:
        logger.warning(f"LLM response generation failed: {e}")
        # Fallback to simply joining the data pieces with better formatting
        if len(data_collection) == 1:
            return data_collection[0]
        else:
            return f"Here's what I found:\n\n- " + "\n- ".join(data_collection)

def validate_parameters(intent, info):
    """Validate and clean up extracted parameters"""
    if intent in ["weather", "place_info", "best_time"]:
        location = info.get("location", "").strip()
        if not location or len(location) < 2:
            return False, f"Please specify a valid location for the {intent.replace('_', ' ')}."
        return True, {"location": location}
    
    elif intent == "train_number":
        num = info.get("train_number", "").strip()
        if not num or not re.match(r'^\d{5}$', num):
            return False, "Please provide a valid 5-digit train number."
        return True, {"train_number": num}
    
    elif intent in ["train_route", "road", "trip_planning"]:
        start = info.get("start", "").strip()
        end = info.get("end", "").strip()
        if not start or len(start) < 2:
            return False, f"Please specify a valid starting location for your {intent.replace('_', ' ')}."
        if not end or len(end) < 2:
            return False, f"Please specify a valid destination for your {intent.replace('_', ' ')}."
        return True, {"start": start, "end": end}
    
    return False, "I couldn't understand your request. Please try again with more details."

def parse_and_respond(message):
    """
    Main entry: classify the intent with the LLM or rules,
    call the appropriate functions, then generate the final answer.
    Handles complex queries like trip planning that need multiple API calls.
    """
    logger.info(f"Processing user message: {message}")
    
    # 1. Classify and extract parameters
    info = classify_intent(message)
    intent = info.get("intent", "unknown")
    
    logger.info(f"Classified intent: {intent} with info: {info}")
    
    # Handle unknown intent
    if intent == "unknown":
        return "I'm sorry, I couldn't understand your request. You can ask me about weather, train schedules, road routes, or tourist information about places in India."
    
    # 2. Validate parameters
    valid, result = validate_parameters(intent, info)
    if not valid:
        return result
    
    # Update info with validated parameters
    info.update(result)
    
    # 3. Call the appropriate function based on intent
    collected_data = []
    
    if intent == "weather":
        loc = info.get("location")
        weather_data = get_weather(loc)
        collected_data.append(weather_data)
    
    elif intent == "train_number":
        num = info.get("train_number")
        train_data = get_train_by_number(num)
        collected_data.append(train_data)
    
    elif intent == "train_route":
        start = info.get("start")
        end = info.get("end")
        train_route_data = get_trains_by_route(start, end)
        collected_data.append(train_route_data)
    
    elif intent == "road":
        start = info.get("start")
        end = info.get("end")
        road_data = get_road_info(start, end)
        collected_data.append(road_data)
    
    elif intent == "place_info":
        loc = info.get("location")
        place_info = get_place_info(loc)
        if place_info:
            collected_data.append(place_info)
        else:
            collected_data.append(f"I don't have specific tourist information about {loc}.")
    
    elif intent == "best_time":
        loc = info.get("location")
        best_time = get_best_time_to_visit(loc)
        collected_data.append(best_time)
    
    elif intent == "trip_planning":
        # Comprehensive trip planning with multiple APIs
        start = info.get("start")
        end = info.get("end")
        
        # Get transportation options
        train_route_data = get_trains_by_route(start, end)
        road_data = get_road_info(start, end)
        
        # Get destination weather and tourist info
        weather_data = get_weather(end)
        place_info = get_place_info(end)
        best_time = get_best_time_to_visit(end)
        
        # Collect all relevant data
        collected_data.append(train_route_data)
        collected_data.append(road_data)
        collected_data.append(weather_data)
        if place_info:
            collected_data.append(place_info)
        collected_data.append(best_time)
    
    # 4. Generate final response
    final_response = generate_response(message, collected_data, intent)
    return final_response

# Main handler function for chat interface
def handle_message(user_message):
    """Process incoming user messages and return a response"""
    # Clean message
    clean_message = user_message.strip()
    
    # Check for greetings or empty messages
    if not clean_message or clean_message.lower() in ["hi", "hello", "hey"]:
        return "Hello! I'm your Indian travel assistant. You can ask me about weather, train schedules, road routes, or tourist information about places in India."
    
    # Check for exit commands
    if clean_message.lower() in ["exit", "quit", "bye"]:
        return "Goodbye! Have a great day!"
    
    # Check for help command
    if clean_message.lower() in ["help", "what can you do", "commands"]:
        return """I can help you with:
1. Weather information for Indian cities (e.g., "What's the weather in Mumbai?")
2. Train schedules by train number (e.g., "Tell me about train 12345")
3. Train routes between cities (e.g., "Are there trains from Delhi to Mumbai?")
4. Road travel information (e.g., "How long to drive from Bangalore to Chennai?")
5. Tourist information about places (e.g., "Tell me about Jaipur")
6. Best time to visit places (e.g., "When should I visit Goa?")
7. Trip planning (e.g., "I'm planning a trip from Delhi to Agra")

How can I assist you today?"""
    
    # Process regular queries
    try:
        response = parse_and_respond(clean_message)
        return response
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return "I'm sorry, I encountered an error while processing your request. Please try again with a different question."

# ----------------- Main Application -----------------
if __name__ == "__main__":
    print("Starting Indian Travel Assistant...")
    print("Type 'exit' to quit or 'help' for assistance")
    
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit", "bye"]:
                print("Goodbye!")
                break
            
            response = handle_message(user_input)
            print(f"\nAssistant: {response}")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")