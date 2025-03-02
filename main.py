import tweepy
import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Twitter API credentials
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

# API Keys
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def get_aqi_openweather(latitude, longitude):
    """Fetch AQI data from OpenWeatherMap API"""
    url = "http://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        'lat': latitude,
        'lon': longitude,
        'appid': OPENWEATHER_API_KEY
    }
    try:
        response = requests.get(url, params=params)
        print(f"Status code: {response.status_code}")

        if response.status_code != 200:
            print("Failed to fetch AQI")
            return None

        data = response.json()
        if 'list' not in data or not data['list']:
            print("Invalid API response")
            return None
        
        aqi_index = data['list'][0]['main']['aqi']
        pollutants = data['list'][0]['components']
        pm25 = pollutants.get('pm2_5', 0)
        pm10 = pollutants.get('pm10', 0)

        return {
            'aqi_index': aqi_index,
            'pm25': pm25,
            'pm10': pm10
        }
    except Exception as e:
        print(f"Exception: {e}")
        return None

def get_aqi_category(aqi_index, pm25):
    """Convert AQI index into readable category"""
    if aqi_index == 1:
        return {'category': 'Good', 'emoji': '🟢', 'epa_aqi': int(pm25 * 4.8)}
    elif aqi_index == 2:
        return {'category': 'Fair', 'emoji': '🟢', 'epa_aqi': 50 + int((pm25 - 10) * 4.8)}
    elif aqi_index == 3:
        return {'category': 'Moderate', 'emoji': '🟡', 'epa_aqi': 100 + int((pm25 - 25) * 1.8)}
    elif aqi_index == 4:
        return {'category': 'Poor', 'emoji': '🟠', 'epa_aqi': 150 + int((pm25 - 50) * 1.8)}
    elif aqi_index == 5:
        return {'category': 'Very Poor', 'emoji': '🔴', 'epa_aqi': 200 + int((pm25 - 75) * 2.8)}
    else:
        return {'category': 'Unknown', 'emoji': '❓', 'epa_aqi': 0}

def generate_gemini_care_message(aqi_category):
    """Generate care message using Gemini API"""
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    params = {
        "key": GEMINI_API_KEY
    }
    
    prompt = f"Write a short, helpful health tip for air quality status '{aqi_category}' in exactly one sentence for the purpose of tweeting. Include practical advice like wearing masks, staying indoors, or hydration as appropriate for this air quality level. Also add 3 hashtags related to it"
    
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 60
        }
    }

    try:
        response = requests.post(url, headers=headers, params=params, json=body)
        
        if response.status_code == 200:
            result = response.json()
            # Check the structure of the response
            if "candidates" in result and len(result["candidates"]) > 0:
                candidate = result["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if len(parts) > 0 and "text" in parts[0]:
                        message = parts[0]["text"].strip()
                        # Remove quotes if present
                        message = message.strip('"\'')
                        return message
        
        print(f"Invalid Gemini API response: {response.text}")
        return get_fallback_message(aqi_category)
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return get_fallback_message(aqi_category)

def get_fallback_message(aqi_category):
    """Return a fallback message based on AQI category"""
    fallback_messages = {
        "Good": "Enjoy the fresh air and outdoor activities today! 🌱",
        "Fair": "Air quality is acceptable - sensitive groups should monitor conditions. 🌤️",
        "Moderate": "Consider limiting prolonged outdoor exertion if you're sensitive to air pollution. 😷",
        "Poor": "Wear a mask outdoors and limit strenuous activities to protect your lungs. 😷",
        "Very Poor": "Stay indoors if possible and use air purifiers to minimize health risks. ⚠️",
        "Unknown": "Stay hydrated and be mindful of your surroundings today. 💧"
    }
    
    return fallback_messages.get(aqi_category, "Take care of your respiratory health today. 💙")

def post_tweet(aqi_data, location_name):
    """Post Tweet with Care Message"""
    client = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )

    aqi_info = get_aqi_category(aqi_data['aqi_index'], aqi_data['pm25'])
    care_message = generate_gemini_care_message(aqi_info['category'])

    current_time = datetime.now().strftime("%I:%M %p")
    tweet = (
        f"Air Quality Index for {location_name} at {current_time}:\n\n"
        f"Status: {aqi_info['category']} {aqi_info['emoji']}\n"
        f"Air Quality Index: ~{aqi_info['epa_aqi']}\n"
        f"PM2.5: {aqi_data['pm25']:.1f} μg/m³\n"
        f"PM10: {aqi_data['pm10']:.1f} μg/m³\n\n"
        f"{care_message}"
    )

    try:
        # result = client.create_tweet(text=tweet)
        print(f"Tweet would be posted:\n{tweet}")
        return True
    except Exception as e:
        print(f"Error posting tweet: {e}")
        return False

def check_env_vars():
    required_vars = ['TWITTER_API_KEY', 'TWITTER_API_SECRET', 'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN_SECRET', 'OPENWEATHER_API_KEY', 'GEMINI_API_KEY']
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print(f"Missing Environment Variables: {', '.join(missing)}")
        return False
    return True

LOCATION = {
    'name': 'Delhi',
    'latitude': 28.704060,
    'longitude': 77.102493
}

if __name__ == "__main__":
    if not check_env_vars():
        exit(1)
    
    aqi_data = get_aqi_openweather(LOCATION['latitude'], LOCATION['longitude'])
    if aqi_data:
        print("AQI Data Fetched")
        post_tweet(aqi_data, LOCATION['name'])
    else:
        print("Failed to fetch AQI data")
