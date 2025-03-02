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

# OpenWeatherMap API key
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')

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
        
        # Print the status code and response for debugging
        print(f"Status code: {response.status_code}")
        print(f"Response content: {response.text}")
        
        # Check if request was successful
        if response.status_code != 200:
            print(f"API error: Status code {response.status_code}")
            return None
        
        data = response.json()
        
        # Check if 'list' key exists in response
        if 'list' not in data or not data['list']:
            print(f"Unexpected API response format: {data}")
            return None
        
        # OpenWeatherMap uses a different AQI scale (1-5)
        aqi_index = data['list'][0]['main']['aqi']
        
        # Get pollutant values
        pollutants = data['list'][0]['components']
        pm25 = pollutants.get('pm2_5', 0)
        pm10 = pollutants.get('pm10', 0)
        
        # Return both the index and raw values
        return {
            'aqi_index': aqi_index,
            'pm25': pm25,
            'pm10': pm10
        }
    except Exception as e:
        print(f"Error fetching AQI: {e}")
        print(f"Full exception: {repr(e)}")
        return None

def get_aqi_category(aqi_index, pm25):
    """Convert OpenWeatherMap AQI (1-5) to category and US EPA equivalent"""
    # OpenWeatherMap AQI: 1=Good, 2=Fair, 3=Moderate, 4=Poor, 5=Very Poor
    
    if aqi_index == 1:
        category = "Good"
        emoji = "🟢"
        # Approximate EPA AQI value based on PM2.5
        epa_aqi = min(int(pm25 * 4.8), 50)
    elif aqi_index == 2:
        category = "Fair"
        emoji = "🟢"
        epa_aqi = min(50 + int((pm25 - 10) * 4.8), 100)
    elif aqi_index == 3:
        category = "Moderate"
        emoji = "🟡"
        epa_aqi = min(100 + int((pm25 - 25) * 1.8), 150)
    elif aqi_index == 4:
        category = "Poor"
        emoji = "🟠"
        epa_aqi = min(150 + int((pm25 - 50) * 1.8), 200)
    else:  # aqi_index == 5
        category = "Very Poor"
        emoji = "🔴"
        epa_aqi = min(200 + int((pm25 - 75) * 2.8), 300)
    
    return {
        'category': category,
        'emoji': emoji,
        'epa_aqi': epa_aqi
    }

def post_tweet(aqi_data, location_name):
    """Post AQI update to Twitter"""
    # Create Twitter API client
    client = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
        bearer_token=None
    )
    
    # Get AQI category information
    aqi_info = get_aqi_category(aqi_data['aqi_index'], aqi_data['pm25'])
    
    # Create tweet text
    current_time = datetime.now().strftime("%I:%M %p")
    tweet = f"Air Quality Index for {location_name} at {current_time}:\n\n"
    tweet += f"Status: {aqi_info['category']} {aqi_info['emoji']}\n"
    tweet += f"US EPA Equivalent: ~{aqi_info['epa_aqi']}\n"
    tweet += f"PM2.5: {aqi_data['pm25']:.1f} μg/m³\n"
    tweet += f"PM10: {aqi_data['pm10']:.1f} μg/m³"
    
    try:
        # Uncomment this line to actually post the tweet
        result = client.create_tweet(text=tweet)
        print(f"Tweet posted with ID: {result.data['id']}")
        
        # For testing, just print the tweet
        print(f"Tweet would be posted: {tweet}")
        return True
    except Exception as e:
        print(f"Error posting tweet: {e}")
        print(f"Full exception: {repr(e)}")
        return False

# Location configuration - customize as needed
LOCATION = {
    'name': 'Delhi',
    'latitude': 28.704060,
    'longitude': 77.102493
}

# Check environment variables
def check_env_vars():
    required_vars = [
        'TWITTER_API_KEY', 
        'TWITTER_API_SECRET', 
        'TWITTER_ACCESS_TOKEN', 
        'TWITTER_ACCESS_TOKEN_SECRET', 
        'OPENWEATHER_API_KEY'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Please ensure these are set in your .env file")
        return False
    
    print("All required environment variables are set")
    return True

# Main execution
if __name__ == "__main__":
    # Check environment variables
    if not check_env_vars():
        exit(1)
        
    # Fetch AQI data
    print(f"Fetching AQI data for {LOCATION['name']}...")
    aqi_data = get_aqi_openweather(LOCATION['latitude'], LOCATION['longitude'])
    
    if aqi_data:
        print("AQI data fetched successfully.")
        # Post to Twitter
        success = post_tweet(aqi_data, LOCATION['name'])
        if success:
            print("Process completed successfully.")
        else:
            print("Failed to post tweet.")
    else:
        print("Failed to fetch AQI data.")