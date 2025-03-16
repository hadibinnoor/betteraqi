import tweepy
import requests
import os
import json
from datetime import datetime
import pytz
from dotenv import load_dotenv
import google.generativeai as genai
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str
    twitter_credentials: Dict[str, str]
    openweather_api_key: str
    gemini_api_key: str

class AQIBot:
    def __init__(self, location: Location):
        self.location = location
        # Configure Gemini API
        genai.configure(api_key=location.gemini_api_key)

    def get_aqi_openweather(self) -> Optional[Dict]:
        """Fetch AQI data from OpenWeatherMap API"""
        url = "http://api.openweathermap.org/data/2.5/air_pollution"
        
        params = {
            'lat': self.location.latitude,
            'lon': self.location.longitude,
            'appid': self.location.openweather_api_key
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

    def get_aqi_category(self, aqi_index: int, pm25: float) -> Dict:
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

    def get_caring_message_from_gemini(self, aqi_category: str) -> str:
        """Fetch a caring health tip from Gemini based on AQI category"""
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            prompt = f"""
            Create a very short, caring health tip (max 70 characters) for people based on this air quality:
            AQI Category: {aqi_category}
            
            The message should be helpful, caring, and brief - something like reminding people to wear masks, 
            stay indoors, or other appropriate precautions for this air quality level. 
            Don't include any prefixes like "Tip:" or "Health advice:". Just the direct message.
            """
            
            response = model.generate_content(prompt)
            message = response.text.strip()
            
            # Ensure the message is not too long for Twitter
            # if len(message) > 70:
            #     message = message[:67] + "..."
                
            return message
        except Exception as e:
            print(f"Error getting message from Gemini: {e}")
            return "Stay safe and take appropriate precautions for today's air quality."

    def get_local_time(self) -> str:
        """Get current time in the specified timezone"""
        timezone = pytz.timezone(self.location.timezone)
        local_time = datetime.now(timezone)
        return local_time.strftime("%I:%M %p")

    def post_tweet(self, aqi_data: Dict) -> bool:
        """Post AQI update to Twitter"""
        print(f"Posting tweet for {self.location.name}...")
        
        # Get AQI category information
        aqi_info = self.get_aqi_category(aqi_data['aqi_index'], aqi_data['pm25'])
        
        # Get caring message from Gemini
        caring_message = self.get_caring_message_from_gemini(aqi_info['category'])
        
        # Get local time for the specified location
        current_time = self.get_local_time()
        
        # Create tweet text
        tweet = f"Air Quality Index for {self.location.name} at {current_time}:\n\n"
        tweet += f"Status: {aqi_info['category']} {aqi_info['emoji']}\n"
        tweet += f"Air Quality Index: ~{aqi_info['epa_aqi']}\n"
        tweet += f"PM2.5: {aqi_data['pm25']:.1f} μg/m³\n"
        tweet += f"PM10: {aqi_data['pm10']:.1f} μg/m³\n\n"
        tweet += f"💡 {caring_message}"
        
        # Print the tweet content for debugging
        print(f"Tweet content: {tweet}")
        print(f"Tweet length: {len(tweet)} characters")
        
        try:
            # Get location-specific Twitter credentials
            api_key = self.location.twitter_credentials['api_key']
            api_secret = self.location.twitter_credentials['api_secret']
            access_token = self.location.twitter_credentials['access_token']
            access_token_secret = self.location.twitter_credentials['access_token_secret']
            
            print(f"Using Twitter credentials for {self.location.name}")
            
            # Create authentication handler for v1 API (needed for some operations)
            auth = tweepy.OAuth1UserHandler(
                api_key,
                api_secret,
                access_token,
                access_token_secret
            )
            
            # Create both v1 and v2 clients
            api_v1 = tweepy.API(auth)
            client_v2 = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            
            # Try posting with v2 client first (preferred method)
            result = client_v2.create_tweet(text=tweet)
            tweet_id = result.data['id']
            print(f"Tweet successfully posted for {self.location.name} with ID: {tweet_id}")
            return True
            
        except Exception as e:
            print(f"Error posting tweet for {self.location.name}: {e}")
            print(f"Full exception: {repr(e)}")
            
            # Try using v1 API as fallback
            try:
                print(f"Attempting to post for {self.location.name} using v1 API as fallback...")
                status = api_v1.update_status(tweet)
                print(f"Tweet posted via v1 API with ID: {status.id}")
                return True
            except Exception as e2:
                print(f"V1 API fallback also failed for {self.location.name}: {e2}")
                return False

    def update_aqi(self) -> bool:
        """Main function to fetch AQI data and post tweet"""
        print(f"Fetching AQI data for {self.location.name}...")
        aqi_data = self.get_aqi_openweather()
        
        if aqi_data:
            print(f"AQI data fetched successfully for {self.location.name}.")
            # Post to Twitter
            success = self.post_tweet(aqi_data)
            if success:
                print(f"Process completed successfully for {self.location.name}.")
                return True
            else:
                print(f"Failed to post tweet for {self.location.name}.")
                return False
        else:
            print(f"Failed to fetch AQI data for {self.location.name}.")
            return False

def load_location_config(config_file: str) -> list[Location]:
    """Load location configurations from a JSON file"""
    # Load environment variables
    load_dotenv()
    
    # Get API keys from environment variables
    openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    locations = []
    for config in config_data['locations']:
        location_name = config['name']
        prefix = location_name.upper()
        
        # Get location-specific Twitter credentials from environment variables
        twitter_credentials = {
            'api_key': os.getenv(f'{prefix}_TWITTER_API_KEY'),
            'api_secret': os.getenv(f'{prefix}_TWITTER_API_SECRET'),
            'access_token': os.getenv(f'{prefix}_TWITTER_ACCESS_TOKEN'),
            'access_token_secret': os.getenv(f'{prefix}_TWITTER_ACCESS_TOKEN_SECRET')
        }
        
        # Check if credentials are available
        if not all(twitter_credentials.values()):
            print(f"Warning: Missing Twitter credentials for {location_name}")
            print(f"Using values from config file for {location_name}")
            twitter_credentials = config['twitter_credentials']
        
        location = Location(
            name=location_name,
            latitude=config['latitude'],
            longitude=config['longitude'],
            timezone=config['timezone'],
            twitter_credentials=twitter_credentials,
            openweather_api_key=openweather_api_key,
            gemini_api_key=gemini_api_key
        )
        locations.append(location)
    
    return locations

if __name__ == "__main__":
    try:
        # Load locations from config file
        locations = load_location_config('config.json')
        
        # Update AQI for each location
        for location in locations:
            print(f"\n--- Processing {location.name} ---")
            print(f"Twitter API Key: {location.twitter_credentials['api_key'][:4]}...")  # Only print first 4 chars for security
            bot = AQIBot(location)
            bot.update_aqi()
    except Exception as e:
        print(f"Error: {e}")
        print(f"Full exception: {repr(e)}")