import os
import json
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from weather_api import fetch_weather
from road_api import fetch_route
from rail_api import fetch_train_by_name_or_number

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
    logger.info(f"Fetching weather for {location}")
    data = fetch_weather(location)
    if data:
        w = data.get('real_time_weather', {})
        return (f"The current weather in {data.get('location', location)} is "
                f"{w.get('weather_condition','Unknown')} with temperature "
                f"{w.get('temperature','N/A')}°C, humidity "
                f"{w.get('humidity','N/A')}%, wind "
                f"{w.get('wind_speed','N/A')} m/s "
                f"{w.get('wind_direction','')}.")

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
    logger.info(f"Fetching train info for train #{train_number}")
    try:
        api_response = fetch_train_by_name_or_number(train_number)
        body_data = api_response.get("body", [])
        if body_data:
            trains = body_data[0].get("trains", [])
            if trains:
                train = trains[0]
                name     = train.get('trainName', '')
                schedule = train.get('schedule', [])
                if schedule:
                    dep  = schedule[0].get('departureTime', '--')
                    arr  = schedule[-1].get('arrivalTime', '--')
                    dist = schedule[-1].get('distance', 'N/A')
                    return (f"Train {train_number} ({name}) starts at {dep} and ends "
                            f"at {arr}, covering {dist} km.")
    except Exception as e:
        logger.warning(f"API call failed for train #{train_number}: {e}")

    for train in fallback_train_data:
        if train.get('train_number') == str(train_number):
            name  = train.get('train_name', '')
            sched = train.get('schedule', [])
            if sched:
                dep  = sched[0].get('departureTime', '--')
                arr  = sched[-1].get('arrivalTime', '--')
                dist = sched[-1].get('distance', 'N/A')
                return (f"Train {train_number} ({name}) starts at {dep} and ends "
                        f"at {arr}, covering {dist} km.")

    return f"Sorry, no train with number {train_number} was found."

def get_trains_by_route(start, end):
    """Return schedules of trains between start and end stations (fallback JSON only)."""
    logger.info(f"Fetching trains between {start} and {end}")
    start_low, end_low = start.lower(), end.lower()
    matches = []

    for train in fallback_train_data:
        schedule = train.get('schedule', [])
        indices  = {}
        for i, stop in enumerate(schedule):
            name = stop.get('stationName', '').lower()
            if start_low in name:
                indices['start'] = i
            if end_low in name:
                indices['end'] = i
        if 'start' in indices and 'end' in indices and indices['start'] < indices['end']:
            num  = train.get('train_number')
            name = train.get('train_name', '')
            dep  = schedule[indices['start']].get('departureTime', '--')
            arr  = schedule[indices['end']].get('arrivalTime', '--')
            matches.append(f"Train {num} ({name}) departs at {dep} and arrives at {arr}.")

    if matches:
        return " ".join(matches[:3])
    return f"Sorry, no trains found from {start} to {end}."

def get_road_info(start, end):
    """Return driving time and distance between start and end (API or fallback)."""
    logger.info(f"Fetching road info from {start} to {end}")
    data = fetch_route(f"{start},India", f"{end},India")
    if data:
        eta = data.get('eta', {})
        return (f"By road, from {start} to {end} it takes about "
                f"{eta.get('hours',0)} hours {eta.get('minutes',0)} minutes "
                f"covering {data.get('distance_km','N/A')} km.")

    for route in fallback_routes_data:
        s = route.get('start', '').split(',')[0].lower()
        e = route.get('end',   '').split(',')[0].lower()
        if s == start.lower() and e == end.lower():
            eta   = route.get('eta', {})
            hours = eta.get('hours', 0)
            mins  = round(eta.get('minutes', 0))
            dist  = route.get('distance_km', 'N/A')
            return (f"By road, from {start} to {end} it takes about "
                    f"{hours} hours {mins} minutes covering {dist} km.")

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
    
    # Broad travel catch-all — if ANY travel-adjacent word is present, treat as general_travel
    broad_travel_keywords = [
        "go to", "going to", "visit", "travel", "stay", "hotel", "hostel", "guesthouse",
        "cheap", "budget", "wifi", "internet", "work from", "wfh", "nomad",
        "how to reach", "how to get", "route", "way to", "cab", "bus", "taxi",
        "trek", "hike", "trip", "tour", "place", "destination", "location",
    ]
    if any(kw in message for kw in broad_travel_keywords):
        # Try to extract a destination
        indian_places = [
            "kasol", "manali", "shimla", "dharamsala", "mcleod ganj", "spiti", "leh", "ladakh",
            "rishikesh", "haridwar", "mussoorie", "nainital", "dehradun", "kedarnath", "badrinath",
            "goa", "kerala", "munnar", "alleppey", "coorg", "ooty", "kodaikanal",
            "jaipur", "udaipur", "jodhpur", "jaisalmer", "pushkar", "ajmer",
            "varanasi", "agra", "delhi", "mumbai", "bangalore", "chennai", "kolkata", "hyderabad",
            "darjeeling", "sikkim", "gangtok", "meghalaya", "shillong", "cherrapunji",
            "andaman", "lakshadweep", "pondicherry", "hampi", "mysore", "coorg",
            "srinagar", "gulmarg", "pahalgam", "vaishnodevi", "amritsar",
            "puri", "bhubaneswar", "konark", "vizag", "tirupati", "hampi",
        ]
        for place in indian_places:
            if place in message:
                return {"intent": "general_travel", "location": place.title()}
        return {"intent": "general_travel"}

    return {"intent": "unknown"}

# ----------------- HF Inference API Setup -----------------
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

# System prompt that gives the LLM its travel expert identity.
# Used in every LLM call so the model always responds in character.
TRAVEL_EXPERT_SYSTEM = """You are an expert AI travel assistant with deep knowledge of:
- Indian travel: cities, states, hill stations, beaches, heritage sites, culture, food, festivals, history
- Indian transport: trains (IRCTC, routes, classes, booking tips), buses, flights, road trips, local transport
- International travel: visa processes, passport requirements, popular destinations, travel advisories
- Practical travel: packing lists, travel insurance, budgeting, solo travel, family travel, honeymoon travel
- Accommodation: hotels, hostels, homestays, resorts, camping, OYO, Booking.com, Airbnb tips; budget vs premium options
- Work-from-home & digital nomad travel: WiFi-reliable stays, co-working spaces, internet connectivity at hill stations
  and remote destinations, best WFH-friendly hostels/guesthouses, power backup, mobile data (Jio/BSNL/Airtel coverage),
  cost of long stays, digital nomad communities in India (Kasol, McLeod Ganj, Rishikesh, Goa, Manali, etc.)
- Adventure & outdoor: trekking (Himalayas, Western Ghats), wildlife safaris, water sports, camping
- Health & safety: vaccinations, altitude sickness, monsoon travel, travel safety tips
- Food & culture: regional Indian cuisine, street food, dietary restrictions, cultural etiquette
- Seasonal advice: monsoon travel, winter hill stations, summer escapes, festival seasons

When answering complex questions that mix travel + stay + connectivity + budget:
- Address EVERY part of the question — don't skip WiFi, budget, or "how to get there" aspects
- For "how to get there": give the full route (train/bus to nearest railhead, then local transport)
- For stays: give 2-3 specific budget options with approximate price ranges and WiFi notes
- For WFH/WiFi: mention actual connectivity quality, mobile network coverage, and backup options
- Always mention if starting city is unclear: give options from multiple major cities

You give honest, practical, well-organized answers. Be conversational and friendly like a knowledgeable friend,
not a formal guide. If asked about real-time data (live prices, exact availability), explain you can provide
general guidance and suggest where to check for live data (IRCTC, Google Flights, Booking.com, etc.).
Never say you cannot help with a travel question — always give your best knowledge-based answer."""

# ----------------- Improved LLM Prompting -----------------
def classify_intent(message):
    """
    Classify user intent via LLM, falling back to rule-based on failure.
    """
    if not llm_client:
        logger.warning("LLM unavailable, using rule-based classification")
        return rule_based_classify(message)

    prompt = f"""User message: "{message}"

Classify the intent. Choose exactly one from:
- "weather"         → wants current weather for a location
- "train_number"    → asking about a specific train by its 5-digit number
- "train_route"     → wants trains between two cities
- "road"            → wants road travel time/distance between two places
- "trip_planning"   → wants a full trip plan covering transport + destination info
- "place_info"      → wants tourist/attraction info about a place
- "best_time"       → wants to know the best season/time to visit a place
- "greeting"        → just saying hi, hello, or asking for help/what you can do
- "general_travel"  → ANY other travel question (visa, packing, flights, hotels, trekking, budgeting, food, culture, safety, international destinations, tips, etc.)
- "unknown"         → completely unrelated to travel (e.g. maths, coding, recipes)

Rules:
- Use "general_travel" broadly — if it's travel-related in any way, prefer it over "unknown"
- Only use "unknown" when the message has absolutely nothing to do with travel

Parameters to extract:
- weather / place_info / best_time: "location"
- train_number: "train_number"
- train_route / road / trip_planning: "start" and "end"
- general_travel: "location" if a specific destination/place is mentioned (else omit)
- greeting / unknown: no extra parameters

Output format (JSON only, no explanation):
{{"intent": "...", ...params}}

Examples:
- "What's the weather in Mumbai?" → {{"intent":"weather","location":"Mumbai"}}
- "Trains from Delhi to Mumbai?" → {{"intent":"train_route","start":"Delhi","end":"Mumbai"}}
- "Drive time from Pune to Goa?" → {{"intent":"road","start":"Pune","end":"Goa"}}
- "Plan a trip from Chennai to Kerala" → {{"intent":"trip_planning","start":"Chennai","end":"Kerala"}}
- "Tell me about Jaipur" → {{"intent":"place_info","location":"Jaipur"}}
- "Best time to visit Ladakh?" → {{"intent":"best_time","location":"Ladakh"}}
- "Hi there!" → {{"intent":"greeting"}}
- "Do I need a visa for Thailand?" → {{"intent":"general_travel"}}
- "Best budget hotels in Rishikesh?" → {{"intent":"general_travel","location":"Rishikesh"}}
- "What to pack for a Himalayan trek?" → {{"intent":"general_travel"}}
- "Is it safe to travel solo in Rajasthan?" → {{"intent":"general_travel","location":"Rajasthan"}}
- "I want to go to Kasol for work from home, how to get there and cheap stays with WiFi?" → {{"intent":"general_travel","location":"Kasol"}}
- "Cheapest flights from Bangalore to Goa?" → {{"intent":"general_travel","location":"Goa"}}
- "What is 2+2?" → {{"intent":"unknown"}}

Return only the JSON. Nothing else."""

    try:
        response_text = ""
        stream = llm_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[
                {"role": "system", "content": TRAVEL_EXPERT_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.1,
            max_tokens=150,
            stream=True
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                response_text += chunk.choices[0].delta.content

        json_start = response_text.find('{')
        json_end   = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(response_text[json_start:json_end])
            logger.info(f"Intent classified: {result}")
            return result
        raise ValueError("No JSON in response")

    except Exception as e:
        logger.warning(f"LLM classification failed ({e}), falling back to rules")
        return rule_based_classify(message)

def generate_response(message, data_collection=None, intent=None):
    """
    Generate a conversational reply using the LLM.
    - When data_collection is provided: synthesise the fetched data into a friendly answer.
    - When data_collection is empty/None (general_travel): answer entirely from LLM knowledge.
    """
    if not llm_client:
        if data_collection:
            return data_collection[0] if len(data_collection) == 1 else "Here's what I found:\n\n- " + "\n- ".join(data_collection)
        return "I'm unable to answer right now as the AI service is not configured."

    intent_context = {
        "trip_planning":  "Give a well-organised trip plan covering how to get there, current weather at the destination, what to see, and the ideal travel season.",
        "place_info":     "Highlight what makes this place unique, top attractions, food, and practical visitor tips.",
        "train_number":   "Present the train schedule clearly with departure/arrival times and key stops.",
        "train_route":    "List the available trains with timings and suggest the best option.",
        "road":           "State the driving time and distance clearly, and add any useful road-trip tips.",
        "weather":        "Describe the current weather naturally and suggest what to wear or bring.",
        "best_time":      "Explain the best seasons to visit with reasons (weather, festivals, crowds, prices).",
        "general_travel": (
            "Answer EVERY part of the user's question thoroughly. Structure your response with clear sections:\n"
            "- If they ask HOW TO GET THERE: give the complete route (train to nearest railhead + bus/taxi onward) "
            "from major cities like Delhi, Mumbai, Chandigarh as applicable. Include travel time and cost estimates.\n"
            "- If they ask about STAYS/ACCOMMODATION: give 3-5 specific budget/mid-range options with "
            "approximate nightly rates (₹ range). Mention WiFi quality honestly for each if relevant.\n"
            "- If they mention WORK FROM HOME / WiFi: rate the internet connectivity at the destination honestly, "
            "name specific hostels/guesthouses known for good WiFi, mention mobile network coverage (Jio/BSNL/Airtel), "
            "and suggest backup options (local SIM, hotspot).\n"
            "- If they mention BUDGET: suggest the cheapest realistic options without sacrificing basic needs.\n"
            "Be specific with names, prices, and practical tips — not vague generalities."
        ),
    }.get(intent or "", "")

    if data_collection:
        user_prompt = f"""The user asked: "{message}"

Here is the fetched data to base your answer on:
{chr(10).join(data_collection)}

{intent_context}

Write a natural, friendly response that directly answers the user. Do not mention
"fetched data" or the structure of this prompt. Be conversational and helpful."""
    else:
        # No API data — answer entirely from training knowledge
        user_prompt = f"""The user asked: "{message}"

{intent_context}

Answer this travel question thoroughly and helpfully from your knowledge.
Be practical, specific, and friendly. Organise the answer clearly."""

    try:
        response_text = ""
        stream = llm_client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct",
            messages=[
                {"role": "system", "content": TRAVEL_EXPERT_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=1500,
            stream=True
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                response_text += chunk.choices[0].delta.content
        return response_text

    except Exception as e:
        logger.warning(f"LLM response generation failed: {e}")
        if data_collection:
            return data_collection[0] if len(data_collection) == 1 else "Here's what I found:\n\n- " + "\n- ".join(data_collection)
        return "I'm having trouble connecting to the AI service right now. Please try again in a moment."

def validate_parameters(intent, info):
    """Validate and clean up extracted parameters. Returns (valid, params_or_error)."""
    if intent in ["general_travel", "greeting", "unknown"]:
        return True, {}

    if intent in ["weather", "place_info", "best_time"]:
        location = info.get("location", "").strip()
        if not location or len(location) < 2:
            return False, f"Could you tell me which place you're asking about?"
        return True, {"location": location}

    if intent == "train_number":
        num = info.get("train_number", "").strip()
        if not num or not re.match(r'^\d{5}$', num):
            return False, "Please provide a valid 5-digit train number."
        return True, {"train_number": num}

    if intent in ["train_route", "road", "trip_planning"]:
        start = info.get("start", "").strip()
        end   = info.get("end",   "").strip()
        if not start or len(start) < 2:
            return False, "Could you tell me the starting city for your journey?"
        if not end or len(end) < 2:
            return False, "Could you tell me the destination city for your journey?"
        return True, {"start": start, "end": end}

    return True, {}

def parse_and_respond(message):
    """
    Main entry point.
    1. Classify intent (LLM or rule-based fallback).
    2. For data-backed intents: call the relevant APIs then generate response.
    3. For general_travel / greeting: answer directly from LLM knowledge.
    4. For unknown (non-travel): politely decline.
    """
    logger.info(f"Processing: {message}")

    # ── Greetings handled locally — no LLM call needed ───────────
    stripped = message.strip().lower().rstrip("!.,?")
    if stripped in {"hi", "hello", "hey", "hola", "namaste", "help",
                    "what can you do", "commands", "start"}:
        return (
            "Hello! I'm your AI travel assistant. I can help you with:\n\n"
            "• Weather in any Indian city\n"
            "• Train schedules by number or route\n"
            "• Road travel time and distance\n"
            "• Tourist info, best time to visit any place\n"
            "• Full trip planning (transport + destination guide)\n"
            "• Visa info, packing tips, budget travel, hotels, trekking, and any other travel question\n\n"
            "What would you like to know?"
        )

    # ── Classify ─────────────────────────────────────────────────
    info   = classify_intent(message)
    intent = info.get("intent", "general_travel")
    logger.info(f"Intent: {intent} | params: {info}")

    # ── Greeting from LLM classification ─────────────────────────
    if intent == "greeting":
        return (
            "Hey there! Ask me anything travel-related — weather, trains, road trips, "
            "tourist spots, visa questions, packing advice, budget tips, or anything else "
            "about travelling in India or abroad. What's on your mind?"
        )

    # ── Non-travel question ───────────────────────────────────────
    if intent == "unknown":
        return (
            "I'm specialised in travel! Ask me about destinations, trains, weather, "
            "road routes, trip planning, visas, packing, hotels, or anything else travel-related."
        )

    # ── Validate parameters for data-backed intents ───────────────
    valid, result = validate_parameters(intent, info)
    if not valid:
        return result
    info.update(result)

    # ── General travel: enrich with place/weather data if a location was detected ──
    if intent == "general_travel":
        location = info.get("location", "").strip()
        enriched = []
        if location:
            place = get_place_info(location)
            if place:
                enriched.append(place)
            enriched.append(get_best_time_to_visit(location))
            weather = get_weather(location)
            if "don't have weather" not in weather:
                enriched.append(weather)
        return generate_response(message, data_collection=enriched or None, intent="general_travel")

    # ── Data-backed intents: fetch from APIs then generate ─────────
    collected_data = []

    if intent == "weather":
        collected_data.append(get_weather(info["location"]))

    elif intent == "train_number":
        collected_data.append(get_train_by_number(info["train_number"]))

    elif intent == "train_route":
        collected_data.append(get_trains_by_route(info["start"], info["end"]))

    elif intent == "road":
        collected_data.append(get_road_info(info["start"], info["end"]))

    elif intent == "place_info":
        loc  = info["location"]
        data = get_place_info(loc)
        collected_data.append(data if data else f"I don't have specific data about {loc} yet.")

    elif intent == "best_time":
        collected_data.append(get_best_time_to_visit(info["location"]))

    elif intent == "trip_planning":
        start, end = info["start"], info["end"]
        collected_data.extend([
            get_trains_by_route(start, end),
            get_road_info(start, end),
            get_weather(end),
        ])
        place = get_place_info(end)
        if place:
            collected_data.append(place)
        collected_data.append(get_best_time_to_visit(end))

    return generate_response(message, collected_data, intent)

