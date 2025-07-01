# chat_server.py
from flask import Flask, request, jsonify, send_from_directory
from promptflow_router import parse_and_respond

from rail_api import rail_api
from road_api import road_api
from weather_api import weather_api

app = Flask(__name__, static_folder='static', template_folder='templates')

# Register blueprints for all APIs
app.register_blueprint(rail_api, url_prefix='')
app.register_blueprint(road_api, url_prefix='')
app.register_blueprint(weather_api, url_prefix='')

@app.route('/')
def index():
    # Serve the chat UI
    return send_from_directory('templates', 'index.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message', '')
    # Pass the user's message to our router
    try:
        bot_reply = parse_and_respond(user_msg)
    except Exception as e:
        bot_reply = "Sorry, something went wrong processing your request."
    return jsonify({'response': bot_reply})

if __name__ == '__main__':
    # Run on port 8500 (to avoid conflicts with the road API on 5000)
    app.run(host='0.0.0.0', port=5000, debug=True)
