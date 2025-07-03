import requests
import os
import time
import math
import json
import re
import io
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaFileUpload
import pickle

GOOGLE_API_KEY = "GOOGLE_API_KEY"  
large_chains = ["migros", "carrefour", "bim", "a101", "şok", "metro", "macrocenter", "kim", "sok", "file", "happy center"]


SCOPES = ['https://www.googleapis.com/auth/drive']

class GoogleDriveManager:
    def __init__(self, credentials_file='credentials.json'):
        
        self.service = None
        self.credentials_file = credentials_file
        self.dataset_folder_id = None
        self.authenticate()
    
    def authenticate(self):
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('drive', 'v3', credentials=creds)
        print("Google Drive API connection successful! (With read and write permissions)")
    
    def find_or_create_dataset_folder(self, folder_name="DATASET"):
        try:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, parents)').execute()
            
            items = results.get('files', [])
            
            if not items:
                print(f"'{folder_name}' folder not found, creating new folder")
                file_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = self.service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                
                self.dataset_folder_id = folder.get('id')
                print(f"'{folder_name}' klasörü oluşturuldu (ID: {self.dataset_folder_id})")
            
            else:
                self.dataset_folder_id = items[0]['id']
                print(f"'{folder_name}' folder found (ID: {self.dataset_folder_id})")
            
            return self.dataset_folder_id
            
        except HttpError as error:
            print(error)
            return None
    
    def get_existing_market_folders(self):
        existing_place_ids = set()
        
        if not self.dataset_folder_id:
            return existing_place_ids
        
        try:
            query = f"'{self.dataset_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            keep_paginating = True
            page_token = None
            while keep_paginating:
                results = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name)',
                    pageToken=page_token).execute()
                
                items = results.get('files', [])
                
                for item in items:
                    folder_name = item['name']
                    parts = folder_name.split('_')
                    if len(parts) >= 3:  
                        place_id = parts[0]
                        existing_place_ids.add(place_id)
                        print(f"  Existing market found: {folder_name}")
                
                page_token = results.get('nextPageToken', None)
                if page_token is None:
                    keep_paginating = False
            
            print(f"\nToplam {len(existing_place_ids)} existing market found.")
            return existing_place_ids
            
        except HttpError as error:
            print(f'An error occurred while listing folders: {error}')
            return set()
    
    def create_market_folder(self, folder_name):
        """
        Creates a new market folder inside the DATASET folder.
        
        Args:
            folder_name: Name of the folder to be created
            
        Returns:
            folder_id: ID of the created folder
        """
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.dataset_folder_id]
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id')
            
        except HttpError as error:
            print(f'Error creating folder: {error}')
            return None
    
    def upload_json_to_folder(self, folder_id, filename, content):
        """
        Uploads the JSON content to the specified folder.
        """
        try:
            json_str = json.dumps(content, ensure_ascii=False, indent=2)
            file_content = io.BytesIO(json_str.encode('utf-8'))
            
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            media = MediaIoBaseUpload(file_content, mimetype='application/json')
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            print(f"    JSON  file is uploaded: {filename}")
            return file.get('id')
            
        except HttpError as error:
            print(f'Error loading JSON: {error}')
            return None
    
    def upload_image_to_folder(self, folder_id, filename, image_data):
        """
        Loads image data into the specified folder.
        """
        try:
            file_content = io.BytesIO(image_data)
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            media = MediaIoBaseUpload(file_content, mimetype='image/jpeg')
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            print(f"    Image uploaded: {filename}")
            return file.get('id')
            
        except HttpError as error:
            print(f'Error while loading image: {error}')
            return None

drive_manager = None

def initialize_drive_manager():
    """Starts Google Drive connection"""
    global drive_manager
    
    print("\n=== Establishing Google Drive Connection ===")
    print("Note: You may need to log in to your Google account in your browser for the first run.")
    
    if not os.path.exists('credentials.json'):
        print("\nWARNING: 'credentials.json' file not found!")
        return None
    
    try:
        drive_manager = GoogleDriveManager('credentials.json')
        drive_manager.find_or_create_dataset_folder()
        return drive_manager
    except Exception as e:
        print(e)
        return None

def save_market_to_drive(market):
    """
    Saves market information and images to Google Drive.
    """
    if not drive_manager:
        print("No Google Drive connection, market could not be saved.")
        return None
    
    place_id = market.get("place_id")
    lat = market.get("location", {}).get("lat", "unknown_lat")
    lng = market.get("location", {}).get("lng", "unknown_lng")
    
    folder_name = f"{place_id}_{lat}_{lng}"
    
    print(f"\nCreating a folder in Drive for '{market.get('name')}'...")
    folder_id = drive_manager.create_market_folder(folder_name)
    
    if folder_id:
        json_filename = f"{place_id}_details.json"
        drive_manager.upload_json_to_folder(folder_id, json_filename, market)
        return folder_id
    
    return None


def download_and_upload_street_view_images(target_name, target_lat, target_lng, place_id, drive_folder_id):
    """
    Downloads Street View images and uploads them to Google Drive.
    """
    if not drive_manager or not drive_folder_id:
        print("There is no Google Drive link or folder ID.")
        return 0
    
    print(f"\nDownloading Street View images and uploading them to Drive {target_name}...")
    metadata = get_streetview_metadata(target_lat, target_lng)

    if not metadata or metadata.get("status") != "OK":
        print(f"Could not get Street View metadata for coordinates {target_lat}, {target_lng}!")
        camera_lat, camera_lng = target_lat, target_lng
        nearest_pano = None
    else:
        camera_lat = metadata.get("location", {}).get("lat", target_lat)
        camera_lng = metadata.get("location", {}).get("lng", target_lng)
        nearest_pano = metadata.get("pano_id")

        from_target_meters = haversine_distance(target_lat, target_lng, camera_lat, camera_lng)
        if from_target_meters > 30:
            print(f"The closest Street View location is {from_target_meters:.1f} meters from the target!")
            camera_lat, camera_lng = target_lat, target_lng
            nearest_pano = None

    base_heading = calculate_heading_to_target(camera_lat, camera_lng, target_lat, target_lng)
    print(f"Target direction : {base_heading:.1f}°")

    angle_variations = [-30, 0, 30]
    position_offsets = [-20, 0, 20]

    base_url = "https://maps.googleapis.com/maps/api/streetview"
    common_params = {
        "size": "1280x1024",
        "key": GOOGLE_API_KEY,
        "return_error_code": "true"
    }

    if nearest_pano:
        common_params["pano"] = nearest_pano

    total_successful = 0
    total_attempts = len(position_offsets) * len(angle_variations)

    for pos_idx, offset in enumerate(position_offsets):
        perpendicular_bearing = (base_heading + 90) % 360
        position_lat, position_lng = offset_coordinates(camera_lat, camera_lng, offset, perpendicular_bearing)
        position_heading = calculate_heading_to_target(position_lat, position_lng, target_lat, target_lng)

        for angle_idx, angle_offset in enumerate(angle_variations):
            heading = (position_heading + angle_offset) % 360
            params = common_params.copy()

            if "pano" not in params:
                params["location"] = f"{position_lat},{position_lng}"

            params.update({
                "heading": heading,
                "pitch": 0,
                "fov": 60,
                "quality": 100
            })

            response = requests.get(base_url, params=params, stream=True)

            if response.status_code == 200 and not response.content.startswith(b"<?xml"):
                image_data = response.content
                filename = f"pos_{offset}_angle_{angle_offset}.jpg"
    
                if drive_manager.upload_image_to_folder(drive_folder_id, filename, image_data):
                    total_successful += 1
                else:
                    print(f"    ERROR: {filename} could not be uploaded to Drive")
            else:
                print(f"    Failed to download image for position {offset}m, angle {angle_offset}°")

    print(f"\n{total_successful} of {total_attempts} images for {target_name} successfully uploaded to Drive.")
    return total_successful

def get_place_details(place_id):
    """Retrieves detail information for a specific place_id."""
    base_url = "https://maps.googleapis.com/maps/api/place/details/json"
    
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,geometry,types,rating,user_ratings_total,opening_hours,formatted_phone_number",
        "key": GOOGLE_API_KEY
    }
    
    response = requests.get(base_url, params=params)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("status") == "OK":
            return result.get("result")
    
    return None

def is_actual_market(place):
    """Determines whether a place is truly a market."""
    name = place.get("name", "").lower()
    types = [t.lower() for t in place.get("types", [])]
    
    # Strong positive indicators
    strong_market_types = ["grocery_or_supermarket", "supermarket"]
    if any(t in strong_market_types for t in types):
        if "pharmacy" in types or "eczane" in name:
            return False
        return True
    
    # Clear market names
    market_patterns = [
        r"\bmarket\b", r"\bbakkal\b", r"\bsüpermarket\b", 
        r"\bmanav\b", r"\bshop\b", r"\bgrocery\b",
        r"\bminibakkal\b", r"\bbakkaliye\b", r"\bsupermarket\b"
    ]
    
    for pattern in market_patterns:
        if re.search(pattern, name):
            if not any(re.search(exclude, name) for exclude in 
                  [r"\bpharmacy\b", r"\beczane\b", r"\bkuyumcu\b"]):
                return True
    
    # Scoring system
    score = 0
    
    # Type-based scoring
    type_scores = {
        "convenience_store": 3,
        "store": 1,
        "food": 1
    }
    
    for t in types:
        if t in type_scores:
            score += type_scores[t]
    
    # Name-based scoring
    name_scores = {
        "mini market": 3,
        "süper market": 3,
        "halk market": 3,
        "mahalle market": 3,
        "gıda": 2
    }
    
    for term, points in name_scores.items():
        if term in name:
            score += points
    
    # Negative indicators
    negative_name_patterns = [
        r"\brestaurant\b", r"\bcafe\b", r"\bkahvaltı\b", r"\bkulüp\b", 
        r"\bdernek\b", r"\bbar\b", r"\blounge\b", r"\bcoffee\b", r"\bkahve\b",r"(?i)\bsüt\b",
        r"\bçay\b", r"\btea\b", r"\bfitness\b", r"\bspa\b", r"\bmerkez\b", r"(?i)\bçiftliği\b",
        r"\bhotel\b", r"\botel\b", r"\bresort\b",r"(?i)\btekel\b",r"\bkasap\b",r"\bkuruyemiş\b",r"\bsalon\b"
    ]

    if any(re.search(pattern, name) for pattern in negative_name_patterns):
        score -= 5
    
    negative_types = [
        "pharmacy", "gas_station", "car_repair", "car_dealer",
        "clothing_store", "furniture_store", "home_goods_store",
        "electronics_store", "jewelry_store", "restaurant", "cafe", 
        "breakfast_restaurant", "bar", "wedding_venue", "gym", "event_venue", 
        "athletic_field", "sports_activity_location", "health", "club"
    ]
    
    if any(t in negative_types for t in types):
        score -= 5
    if any(term in name for term in ["shell", "bp", "petrol", "opet", "aytemiz", "total", "lukoil"]):
        score -= 4
    if "servesBreakfast" in place or "servesBrunch" in place or "servesLunch" in place or "servesDinner" in place:
        score -= 3
    if "dineIn" in place and place["dineIn"] == True:
        score -= 2
    return score >= 2

def find_markets_in_radius(lat, lng, radius_km=10):
    """
    Finds grocery stores around the given location and filters available grocery stores in Drive.
    """
    print(f"\nSearching for markets within {radius_km} km radius of {lat}, {lng} location...")
    existing_place_ids = set()
    if drive_manager:
        print("\nChecking existing markets in Google Drive...")
        existing_place_ids = drive_manager.get_existing_market_folders()

    place_types = ["grocery_or_supermarket", "convenience_store", "store", "supermarket"]
    keywords = ["market", "bakkal", "mini market", "süpermarket", "manav", "grocery", "groceries", 
               "yerel market", "mahalle marketi",]
    
    radius_meters = radius_km * 1000
    all_places = []
    base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    print("\nResmi yer türleri ile arama yapılıyor...")
    for place_type in place_types:
        params = {
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "type": place_type,
            "key": GOOGLE_API_KEY
        }
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            results = response.json()
            if results.get("status") == "OK" and results.get("results"):
                print(f"  '{place_type}' türünde {len(results.get('results', []))} places found.")
                exclude_chains = True
                
                for place in results["results"]:
                    place_id = place.get("place_id")
                    name = place.get("name", "").lower()
                    if place_id in existing_place_ids:
                        print(f"  Skipping: {place.get('name')} (available in Drive)")
                    else:
                        if not (exclude_chains and any(chain in name for chain in large_chains)):
                            if not any(p.get("place_id") == place_id for p in all_places):
                                place_lat = place["geometry"]["location"]["lat"]
                                place_lng = place["geometry"]["location"]["lng"]
                                distance = haversine_distance(lat, lng, place_lat, place_lng) / 1000
                                
                                place_info = {
                                    "name": place.get("name"),
                                    "place_id": place_id,
                                    "location": place.get("geometry", {}).get("location", {}),
                                    "types": place.get("types", []),
                                    "formatted_address": place.get("vicinity", ""),
                                    "rating": place.get("rating", 0),
                                    "user_ratings_total": place.get("user_ratings_total", 0),
                                    "search_method": f"type:{place_type}",
                                    "distance": distance
                                }
                                
                                all_places.append(place_info)
                
                process_next_pages(base_url, results, params, all_places, lat, lng, exclude_chains, large_chains, existing_place_ids)

    print("\nAnahtar kelimeler ile arama yapılıyor...")
    for keyword in keywords:
        params = {
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "keyword": keyword,
            "key": GOOGLE_API_KEY
        }
        
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            results = response.json()
            
            if results.get("status") == "OK" and results.get("results"):
                print(f"  {len(results.get('results', []))} found for '{keyword}' search.")
                exclude_chains = True
                for place in results["results"]:
                    place_id = place.get("place_id")
                    name = place.get("name", "").lower()
                    if place_id in existing_place_ids:
                        print(f"  Skipping: {place.get('name')} (available in Drive)")
                    else:
                        if not (exclude_chains and any(chain in name for chain in large_chains)):
                            if not any(p.get("place_id") == place_id for p in all_places):
                                place_lat = place["geometry"]["location"]["lat"]
                                place_lng = place["geometry"]["location"]["lng"]
                                distance = haversine_distance(lat, lng, place_lat, place_lng) / 1000
                                place_info = {
                                    "name": place.get("name"),
                                    "place_id": place_id,
                                    "location": place.get("geometry", {}).get("location", {}),
                                    "types": place.get("types", []),
                                    "formatted_address": place.get("vicinity", ""),
                                    "rating": place.get("rating", 0),
                                    "user_ratings_total": place.get("user_ratings_total", 0),
                                    "search_method": f"keyword:{keyword}",
                                    "distance": distance
                                }
                                all_places.append(place_info)
                process_next_pages(base_url, results, params, all_places, lat, lng, exclude_chains, large_chains, existing_place_ids)
    
    all_places.sort(key=lambda x: x["distance"])
    
    print(f"\nA total of {len(all_places)} unique places were found.")
    real_markets = [place for place in all_places if is_actual_market(place)]
    print(f"After filtering {len(real_markets)} NEW real markets were found.")
    if real_markets:
        for i, place in enumerate(real_markets):
            place_id = place.get("place_id")
            print(f"  {i+1}/{len(real_markets)} - Retrieving details for {place.get('name')}...")
            details = get_place_details(place_id) 
            if details:
                place["formatted_address"] = details.get("formatted_address", place.get("formatted_address", ""))
                place["formatted_phone_number"] = details.get("formatted_phone_number", "")
                if "opening_hours" in details:
                    place["open_now"] = details["opening_hours"].get("open_now", False)
                    if "weekday_text" in details["opening_hours"]:
                        place["weekday_text"] = details["opening_hours"]["weekday_text"]
    
    return real_markets

def process_next_pages(base_url, results, params, all_places, lat, lng, exclude_chains, large_chains, existing_place_ids):
    """Processes the next page results from the API."""
    next_page_token = results.get("next_page_token")
    while next_page_token:
        time.sleep(2)
        page_params = {
            "key": GOOGLE_API_KEY,
            "pagetoken": next_page_token
        }
        page_response = requests.get(base_url, params=page_params)
        if page_response.status_code == 200:
            page_results = page_response.json()
            if page_results.get("status") == "OK" and page_results.get("results"):
                for place in page_results["results"]:
                    place_id = place.get("place_id")
                    name = place.get("name", "").lower()
                    if place_id not in existing_place_ids:
                        if not (exclude_chains and any(chain in name for chain in large_chains)):
                            if not any(p.get("place_id") == place_id for p in all_places):
                                place_lat = place["geometry"]["location"]["lat"]
                                place_lng = place["geometry"]["location"]["lng"]
                                distance = haversine_distance(lat, lng, place_lat, place_lng) / 1000
                                search_method = "type:" + params.get("type", "") if "type" in params else "keyword:" + params.get("keyword", "")
                                place_info = {
                                    "name": place.get("name"),
                                    "place_id": place_id,
                                    "location": place.get("geometry", {}).get("location", {}),
                                    "types": place.get("types", []),
                                    "formatted_address": place.get("vicinity", ""),
                                    "rating": place.get("rating", 0),
                                    "user_ratings_total": place.get("user_ratings_total", 0),
                                    "search_method": search_method,
                                    "distance": distance
                                }
                                
                                all_places.append(place_info)
                
                next_page_token = page_results.get("next_page_token")
            else:
                next_page_token = None
        else:
            next_page_token = None

def get_streetview_metadata(lat, lng):
    """Gets Street View metadata for the given coordinates."""
    base_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {
        "location": f"{lat},{lng}",
        "key": GOOGLE_API_KEY
    }
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        metadata = response.json()
        if metadata.get("status") == "OK":
            return metadata
    return None

def calculate_heading_to_target(camera_lat, camera_lng, target_lat, target_lng):
    """Calculate the heading angle from the camera position to the target position."""
    lat1 = math.radians(camera_lat)
    lng1 = math.radians(camera_lng)
    lat2 = math.radians(target_lat)
    lng2 = math.radians(target_lng)
    y = math.sin(lng2 - lng1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lng2 - lng1)
    bearing = math.atan2(y, x)
    heading = (math.degrees(bearing) + 360) % 360
    return heading

def offset_coordinates(lat, lng, distance_meters, bearing_degrees):
    """Calculates a new point with a given distance and angle from a point."""
    R = 6378137
    d = distance_meters / R
    bearing_rad = math.radians(bearing_degrees)
    lat_rad = math.radians(lat)
    lng_rad = math.radians(lng)
    lat_new_rad = math.asin(
        math.sin(lat_rad) * math.cos(d) +
        math.cos(lat_rad) * math.sin(d) * math.cos(bearing_rad)
    )
    lng_new_rad = lng_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(d) * math.cos(lat_rad),
        math.cos(d) - math.sin(lat_rad) * math.sin(lat_new_rad)
    )
    lat_new = math.degrees(lat_new_rad)
    lng_new = math.degrees(lng_new_rad)
    return lat_new, lng_new

def haversine_distance(lat1, lng1, lat2, lng2):
    """Calculates the distance between two points in meters."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = math.sin(delta_phi / 2) * math.sin(delta_phi / 2) + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

def main():
    global drive_manager
    drive_manager = initialize_drive_manager()
    if not drive_manager:
        print("\Google Drive connection failed. Terminating the program.")
        return
    try:
        lat = float(input("\nLatitude: "))
        lng = float(input("Longitude: "))
    except ValueError:
        print("Invalid coordinates! Using default values.")
        lat = 41.02633949669803
        lng = 28.876766310010403
    try:
        radius = float(input("Search radius (in km, default: 10): ") or "10")
    except ValueError:
        print("Invalid radius! Using default value (10 km).")
        radius = 10
    markets = find_markets_in_radius(lat, lng, radius_km=radius)

    if markets:
        print(f"\n{len(markets)} new markets found. Found markets")
        for i, market in enumerate(markets):
            print(f"{i+1}. {market.get('name')} - {market.get('distance', 0):.2f} km away")
            print(f" Address: {market.get('formatted_address', 'No address information')}")
            print(f" Rating: {market.get('rating', 0)}/5.0 ({market.get('user_ratings_total', 0)} rating)")
            print("")
        max_places = min(10, len(markets))
        try:
            num_places = int(input(f"\nFor how many markets will data be collected? (1-{len(markets)}, default: {max_places}): ") or str(max_places))
            num_places = min(len(markets), max(1, num_places))
        except ValueError:
            print(f"Invalid value! Using default value ({max_places}")
            num_places = max_places
        
        print(f"\nData for the first {num_places} market selected will be saved to Google Drive:")
        total_processed = 0
        
        for i, market in enumerate(markets[:num_places]):
            name = market.get('name', 'Anonymous Market')
            market_lat = market.get('location', {}).get('lat')
            market_lng = market.get('location', {}).get('lng')
            place_id = market.get('place_id')
            if market_lat and market_lng:
                print(f"\n{i+1}/{num_places} - {name} işleniyor...")
                folder_id = save_market_to_drive(market)
                if folder_id:
                    success_count = download_and_upload_street_view_images(
                        name, market_lat, market_lng, place_id, folder_id
                    )
                    if success_count > 0:
                        total_processed += 1
                        print(f"✓ {name} successfully processed.")
                    else:
                        print(f"✗ No images found for {name}.")
                else:
                    print(f"✗ Could not create Drive folder for {name}.")
            else:
                print(f"ERROR: No location information found for {name}.")
        
        print(f"\n{'='*60}")
        print(f"Process completed!")
        print(f"{num_places} {total_processed} of the market were successfully saved to Google Drive.")
        print(f"You can check your DATASET folder in Drive.")
    else:
        print(f"\nNo new markets found within {radius} km of the specified location.")
        print("All markets may already exist in Google Drive.")
        print("Try again with a different location or a larger radius.")

if __name__ == "__main__":
    main()
