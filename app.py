from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import os
import json
import base64
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# YouTube API configuration
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3'

# Admin password (set via environment variable)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# DigitalOcean API configuration (optional - for automatic updates)
DO_API_TOKEN = os.environ.get('DO_API_TOKEN', '')
DO_APP_ID = os.environ.get('DO_APP_ID', '')

# File to store favorites and watch history (for local development)
FAVORITES_FILE = 'favorites.json'

def load_favorites():
    """Load favorites and watch history from environment variable or file"""
    # Try to load from environment variable first (for production)
    favorites_env = os.environ.get('FAVORITES_DATA')
    if favorites_env:
        try:
            # Decode base64 and parse JSON
            favorites_json = base64.b64decode(favorites_env).decode('utf-8')
            return json.loads(favorites_json)
        except:
            pass
    
    # Fallback to file (for local development)
    try:
        with open(FAVORITES_FILE, 'r') as f:
            return json.load(f)
    except:
        # Default favorites if nothing exists
        return {
            'playlists': [],
            'channels': [],
            'watch_history': []
        }

def update_digitalocean_env_var(favorites):
    """Update FAVORITES_DATA environment variable in DigitalOcean"""
    if not DO_API_TOKEN or not DO_APP_ID:
        # If no API token/app ID, just print the value for manual update
        favorites_json = json.dumps(favorites)
        favorites_b64 = base64.b64encode(favorites_json.encode('utf-8')).decode('utf-8')
        print(f"\n🔄 FAVORITES_DATA environment variable value:")
        print(f"FAVORITES_DATA={favorites_b64}")
        print("💡 Add this to your DigitalOcean app environment variables")
        return False
    
    try:
        # Encode favorites for environment variable
        favorites_json = json.dumps(favorites)
        favorites_b64 = base64.b64encode(favorites_json.encode('utf-8')).decode('utf-8')
        
        # Get current app spec
        headers = {
            'Authorization': f'Bearer {DO_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        # Get app spec
        response = requests.get(f'https://api.digitalocean.com/v2/apps/{DO_APP_ID}', headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to get app spec: {response.status_code}")
            return False
        
        app_spec = response.json()['app']
        
        # Update environment variables
        if 'services' in app_spec['spec']:
            for service in app_spec['spec']['services']:
                if 'envs' not in service:
                    service['envs'] = []
                
                # Remove existing FAVORITES_DATA if it exists
                service['envs'] = [env for env in service['envs'] if env.get('key') != 'FAVORITES_DATA']
                
                # Add updated FAVORITES_DATA
                service['envs'].append({
                    'key': 'FAVORITES_DATA',
                    'value': favorites_b64,
                    'scope': 'RUN_TIME'
                })
        
        # Update the app
        update_response = requests.put(
            f'https://api.digitalocean.com/v2/apps/{DO_APP_ID}',
            headers=headers,
            json={'spec': app_spec['spec']}
        )
        
        if update_response.status_code == 200:
            print("✅ Successfully updated DigitalOcean environment variable")
            return True
        else:
            print(f"❌ Failed to update app: {update_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating DigitalOcean env var: {e}")
        return False

def save_favorites(favorites):
    """Save favorites and watch history to environment variable and file"""
    # Save to file (for local development)
    try:
        with open(FAVORITES_FILE, 'w') as f:
            json.dump(favorites, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save to file: {e}")
    
    # Try to update DigitalOcean environment variable automatically
    update_digitalocean_env_var(favorites)
    
    return favorites

def add_to_watch_history(video_id, video_title=None, channel_title=None, thumbnail=None):
    """Add a video to watch history"""
    favorites = load_favorites()
    
    # Ensure watch_history exists
    if 'watch_history' not in favorites:
        favorites['watch_history'] = []
    
    # Get video details if not provided
    if not video_title or not channel_title or not thumbnail:
        try:
            url = f"{YOUTUBE_API_BASE}/videos"
            params = {
                'part': 'snippet',
                'id': video_id,
                'key': YOUTUBE_API_KEY
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data['items']:
                    snippet = data['items'][0]['snippet']
                    video_title = video_title or snippet.get('title', 'Unknown Title')
                    channel_title = channel_title or snippet.get('channelTitle', 'Unknown Channel')
                    thumbnail = thumbnail or snippet.get('thumbnails', {}).get('medium', {}).get('url', '')
        except Exception as e:
            print(f"Error fetching video details: {e}")
            video_title = video_title or 'Unknown Title'
            channel_title = channel_title or 'Unknown Channel'
            thumbnail = thumbnail or ''
    
    # Remove if already exists (to avoid duplicates and update timestamp)
    favorites['watch_history'] = [item for item in favorites['watch_history'] if item['id'] != video_id]
    
    # Add to beginning of list
    watch_item = {
        'id': video_id,
        'title': video_title,
        'channel': channel_title,
        'thumbnail': thumbnail,
        'description': '',  # We'll keep this empty for watch history
        'watched_at': datetime.now().isoformat()
    }
    
    favorites['watch_history'].insert(0, watch_item)
    
    # Keep only last 50 videos
    favorites['watch_history'] = favorites['watch_history'][:50]
    
    # Save updated favorites
    save_favorites(favorites)
    print(f"✅ Added to watch history: {video_title}")

def get_recent_videos():
    """Get recently watched videos"""
    favorites = load_favorites()
    watch_history = favorites.get('watch_history', [])
    
    # Return last 12 watched videos
    return watch_history[:12]

def get_youtube_info(url):
    """Extract channel or playlist info from YouTube URL"""
    if 'playlist?list=' in url:
        playlist_id = url.split('list=')[1].split('&')[0]
        return fetch_playlist_info(playlist_id)
    elif 'channel/' in url:
        channel_id = url.split('channel/')[1].split('/')[0]
        return fetch_channel_info(channel_id)
    elif '@' in url:
        # Handle @username format - convert to channel ID first
        username = url.split('@')[1].split('/')[0]
        return fetch_channel_info_by_username(username)
    return None, "Invalid YouTube URL"

def fetch_playlist_info(playlist_id):
    """Fetch playlist info from YouTube API"""
    url = f"{YOUTUBE_API_BASE}/playlists"
    params = {
        'part': 'snippet',
        'id': playlist_id,
        'key': YOUTUBE_API_KEY
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data['items']:
            item = data['items'][0]
            return {
                'id': playlist_id,
                'title': item['snippet']['title'],
                'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
            }, None
    return None, "Could not fetch playlist info"

def fetch_channel_info_by_username(username):
    """Fetch channel info from YouTube API using @username"""
    # First, try to get channel info using the username/handle
    url = f"{YOUTUBE_API_BASE}/search"
    params = {
        'part': 'snippet',
        'q': username,
        'type': 'channel',
        'maxResults': 1,
        'key': YOUTUBE_API_KEY
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data['items']:
            # Get the channel ID from search results
            channel_id = data['items'][0]['snippet']['channelId']
            # Now get full channel info
            return fetch_channel_info(channel_id)
    
    # If search doesn't work, try the channels endpoint with forUsername
    url = f"{YOUTUBE_API_BASE}/channels"
    params = {
        'part': 'snippet',
        'forUsername': username,
        'key': YOUTUBE_API_KEY
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data['items']:
            item = data['items'][0]
            return {
                'id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description'],
                'thumbnail': item['snippet']['thumbnails']['medium']['url'] if 'thumbnails' in item['snippet'] else None
            }, None
    
    return None, f"Could not find channel for @{username}"

def fetch_channel_info(channel_id):
    """Fetch channel info from YouTube API"""
    url = f"{YOUTUBE_API_BASE}/channels"
    params = {
        'part': 'snippet',
        'id': channel_id,
        'key': YOUTUBE_API_KEY
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data['items']:
            item = data['items'][0]
            return {
                'id': channel_id,
                'title': item['snippet']['title'],
                'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description'],
                'thumbnail': item['snippet']['thumbnails']['medium']['url'] if 'thumbnails' in item['snippet'] else None
            }, None
    return None, "Could not fetch channel info"

class YouTubeAPI:
    def __init__(self, api_key):
        self.api_key = api_key
    
    def search_videos(self, query, max_results=20):
        """Search for videos with safe search enabled"""
        url = f"{YOUTUBE_API_BASE}/search"
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'safeSearch': 'strict',
            'maxResults': max_results,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return None
    
    def check_video_embeddable(self, video_id):
        """Check if a video can be embedded"""
        url = f"{YOUTUBE_API_BASE}/videos"
        params = {
            'part': 'status',
            'id': video_id,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data['items']:
                return data['items'][0]['status'].get('embeddable', False)
        return False

    def get_playlist_thumbnail(self, playlist_id):
        """Get thumbnail from first video in playlist"""
        url = f"{YOUTUBE_API_BASE}/playlistItems"
        params = {
            'part': 'snippet',
            'playlistId': playlist_id,
            'maxResults': 1,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('items') and len(data['items']) > 0:
                item = data['items'][0]
                thumbnails = item['snippet'].get('thumbnails', {})
                # Try different thumbnail sizes, prefer medium
                if 'medium' in thumbnails:
                    return thumbnails['medium']['url']
                elif 'default' in thumbnails:
                    return thumbnails['default']['url']
                elif 'high' in thumbnails:
                    return thumbnails['high']['url']
        return None

    def get_channel_thumbnail(self, channel_id):
        """Get thumbnail from first video in channel"""
        url = f"{YOUTUBE_API_BASE}/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'type': 'video',
            'order': 'relevance',
            'maxResults': 1,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get('items') and len(data['items']) > 0:
                item = data['items'][0]
                thumbnails = item['snippet'].get('thumbnails', {})
                # Try different thumbnail sizes, prefer medium
                if 'medium' in thumbnails:
                    return thumbnails['medium']['url']
                elif 'default' in thumbnails:
                    return thumbnails['default']['url']
                elif 'high' in thumbnails:
                    return thumbnails['high']['url']
        return None

    def get_playlist_videos(self, playlist_id, max_results=50):
        """Get videos from a playlist"""
        url = f"{YOUTUBE_API_BASE}/playlistItems"
        params = {
            'part': 'snippet',
            'playlistId': playlist_id,
            'maxResults': max_results,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_channel_playlists(self, channel_id, max_results=50):
        """Get playlists from a channel"""
        url = f"{YOUTUBE_API_BASE}/playlists"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'maxResults': max_results,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return None

    def get_channel_videos_recent_fast(self, channel_id, max_results=20, page_token=None):
        """Get recent videos from a channel (optimized for speed)"""
        url = f"{YOUTUBE_API_BASE}/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'type': 'video',  # This already filters out shorts
            'order': 'date',
            'maxResults': max_results,
            'key': self.api_key
        }
        
        if page_token:
            params['pageToken'] = page_token
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return None

    def get_channel_videos_recent(self, channel_id, max_results=50):
        """Get recent videos from a channel (most recent first, no shorts)"""
        all_videos = []
        next_page_token = None
        
        while len(all_videos) < max_results:
            url = f"{YOUTUBE_API_BASE}/search"
            params = {
                'part': 'snippet',
                'channelId': channel_id,
                'type': 'video',
                'order': 'date',  # Most recent first
                'maxResults': 50,
                'key': self.api_key
            }
            
            if next_page_token:
                params['pageToken'] = next_page_token
            
            response = requests.get(url, params=params)
            if response.status_code != 200:
                break
                
            data = response.json()
            if not data.get('items'):
                break
            
            # Filter out shorts by checking video duration
            for item in data['items']:
                if len(all_videos) >= max_results:
                    break
                    
                video_id = item['id']['videoId']
                
                # Get video details to check duration
                video_details = self.get_video_details(video_id)
                if video_details and self.is_regular_video(video_details):
                    all_videos.append(item)
            
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                break
        
        return {'items': all_videos[:max_results]}

    def get_channel_videos_comprehensive(self, channel_id):
        """Get comprehensive list of channel videos, filtering out shorts"""
        all_videos = []
        next_page_token = None
        
        while len(all_videos) < 100:  # Limit to prevent too many API calls
            url = f"{YOUTUBE_API_BASE}/search"
            params = {
                'part': 'snippet',
                'channelId': channel_id,
                'type': 'video',
                'order': 'relevance',
                'maxResults': 50,
                'key': self.api_key
            }
            
            if next_page_token:
                params['pageToken'] = next_page_token
            
            response = requests.get(url, params=params)
            if response.status_code != 200:
                break
                
            data = response.json()
            if not data.get('items'):
                break
            
            # Filter out shorts by checking video duration
            for item in data['items']:
                video_id = item['id']['videoId']
                
                # Get video details to check duration
                video_details = self.get_video_details(video_id)
                if video_details and self.is_regular_video(video_details):
                    all_videos.append(item)
            
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                break
        
        return {'items': all_videos}
    
    def get_video_details(self, video_id):
        """Get detailed video info including duration"""
        url = f"{YOUTUBE_API_BASE}/videos"
        params = {
            'part': 'contentDetails',
            'id': video_id,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            return data.get('items', [{}])[0] if data.get('items') else None
        return None
    
    def is_regular_video(self, video_details):
        """Check if video is a regular video (not a short)"""
        duration = video_details.get('contentDetails', {}).get('duration', '')
        
        # Parse ISO 8601 duration (PT1M30S = 1 minute 30 seconds)
        import re
        duration_match = re.search(r'PT(?:(\d+)M)?(?:(\d+)S)?', duration)
        
        if duration_match:
            minutes = int(duration_match.group(1) or 0)
            seconds = int(duration_match.group(2) or 0)
            total_seconds = minutes * 60 + seconds
            
            # Consider videos over 60 seconds as regular videos (not shorts)
            return total_seconds > 60
        
        return True  # Default to including if duration can't be parsed

    def get_channel_videos(self, channel_id, max_results=50):
        """Get all videos from a channel (excluding shorts)"""
        url = f"{YOUTUBE_API_BASE}/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'type': 'video',
            'order': 'relevance',  # Changed from 'date' to 'relevance' to get better mix
            'videoDuration': 'medium',  # Filters out shorts (which are usually 'short')
            'maxResults': max_results,
            'key': self.api_key
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return None

# Initialize YouTube API
youtube = YouTubeAPI(YOUTUBE_API_KEY)

@app.route('/')
def home():
    """Main page with family favorites and recently watched videos"""
    favorites = load_favorites()
    
    # Add thumbnails to playlists
    for playlist in favorites['playlists']:
        if 'thumbnail' not in playlist or not playlist['thumbnail']:
            print(f"🔍 Fetching thumbnail for playlist: {playlist['title']}")
            thumbnail_url = youtube.get_playlist_thumbnail(playlist['id'])
            print(f"📸 Got playlist thumbnail URL: {thumbnail_url}")
            playlist['thumbnail'] = thumbnail_url
    
    # Add video thumbnails to channels
    for channel in favorites['channels']:
        if 'video_thumbnail' not in channel or not channel['video_thumbnail']:
            print(f"🔍 Fetching video thumbnail for channel: {channel['title']}")
            thumbnail_url = youtube.get_channel_thumbnail(channel['id'])
            print(f"📸 Got channel video thumbnail URL: {thumbnail_url}")
            channel['video_thumbnail'] = thumbnail_url
    
    # Get recently watched videos
    recent_videos = get_recent_videos()
    print(f"📺 Found {len(recent_videos)} recently watched videos")
    
    return render_template('index.html', 
                         playlists=favorites['playlists'], 
                         channels=favorites['channels'],
                         recent_videos=recent_videos)

@app.route('/admin')
def admin():
    """Admin panel to manage favorites"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    favorites = load_favorites()
    return render_template('admin.html', 
                         playlists=favorites['playlists'], 
                         channels=favorites['channels'])

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid password', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/export')
def admin_export():
    """Export current favorites as environment variable"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    favorites = load_favorites()
    favorites_json = json.dumps(favorites)
    favorites_b64 = base64.b64encode(favorites_json.encode('utf-8')).decode('utf-8')
    
    return render_template('admin_export.html', favorites_data=favorites_b64)

@app.route('/admin/history')
def admin_history():
    """View watch history in admin"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    favorites = load_favorites()
    watch_history = favorites.get('watch_history', [])
    
    return render_template('admin_history.html', watch_history=watch_history)

@app.route('/admin/history/clear')
def admin_clear_history():
    """Clear all watch history"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    favorites = load_favorites()
    favorites['watch_history'] = []
    save_favorites(favorites)
    
    flash('✅ Watch history cleared!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/history/remove/<video_id>')
def admin_remove_from_history(video_id):
    """Remove specific video from watch history"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    favorites = load_favorites()
    favorites['watch_history'] = [item for item in favorites.get('watch_history', []) if item['id'] != video_id]
    save_favorites(favorites)
    
    flash('✅ Video removed from history!', 'success')
    return redirect(url_for('admin_history'))

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/admin/add', methods=['POST'])
def admin_add():
    """Add new playlist or channel"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    url = request.form.get('url', '').strip()
    if not url:
        flash('Please enter a YouTube URL', 'error')
        return redirect(url_for('admin'))
    
    # Get info from YouTube
    info, error = get_youtube_info(url)
    if error:
        flash(error, 'error')
        return redirect(url_for('admin'))
    
    # Load current favorites
    favorites = load_favorites()
    
    # Determine if it's a playlist or channel
    if 'playlist?list=' in url:
        # Check if already exists
        if any(p['id'] == info['id'] for p in favorites['playlists']):
            flash('Playlist already exists!', 'error')
        else:
            favorites['playlists'].append(info)
            save_favorites(favorites)
            flash(f'✅ Added playlist: {info["title"]}', 'success')
            if DO_API_TOKEN and DO_APP_ID:
                flash('🔄 Automatically updating environment variables...', 'info')
            else:
                flash('💡 Remember to update your FAVORITES_DATA environment variable to make this permanent!', 'warning')
    else:
        # Check if already exists
        if any(c['id'] == info['id'] for c in favorites['channels']):
            flash('Channel already exists!', 'error')
        else:
            favorites['channels'].append(info)
            save_favorites(favorites)
            flash(f'✅ Added channel: {info["title"]}', 'success')
            if DO_API_TOKEN and DO_APP_ID:
                flash('🔄 Automatically updating environment variables...', 'info')
            else:
                flash('💡 Remember to update your FAVORITES_DATA environment variable to make this permanent!', 'warning')
    
    return redirect(url_for('admin'))

@app.route('/admin/remove/<item_type>/<item_id>')
def admin_remove(item_type, item_id):
    """Remove playlist or channel"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    favorites = load_favorites()
    
    if item_type == 'playlist':
        favorites['playlists'] = [p for p in favorites['playlists'] if p['id'] != item_id]
        flash('✅ Playlist removed!', 'success')
    elif item_type == 'channel':
        favorites['channels'] = [c for c in favorites['channels'] if c['id'] != item_id]
        flash('✅ Channel removed!', 'success')
    
    save_favorites(favorites)
    
    if DO_API_TOKEN and DO_APP_ID:
        flash('🔄 Automatically updating environment variables...', 'info')
    else:
        flash('💡 Remember to update your FAVORITES_DATA environment variable!', 'warning')
    
    return redirect(url_for('admin'))

@app.route('/search')
def search():
    """Search for videos"""
    query = request.args.get('q', '')
    if not query:
        return render_template('search.html', videos=[], query='')
    
    try:
        results = youtube.search_videos(query)
        videos = []
        
        if results and 'items' in results:
            for item in results['items']:
                if 'id' in item and isinstance(item['id'], dict) and 'videoId' in item['id']:
                    video_id = item['id']['videoId']
                    snippet = item.get('snippet', {})
                    
                    video = {
                        'id': video_id,
                        'title': snippet.get('title', 'No title'),
                        'channel': snippet.get('channelTitle', 'Unknown Channel'),
                        'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                        'description': snippet.get('description', '')[:100] + '...' if snippet.get('description', '') else 'No description'
                    }
                    videos.append(video)
        
        return render_template('search.html', videos=videos, query=query)
        
    except Exception as e:
        error_message = f"Search error: {str(e)}"
        return render_template('search.html', videos=[], query=query, error=error_message)

@app.route('/playlist/<playlist_id>')
def playlist(playlist_id):
    """View playlist videos"""
    favorites = load_favorites()
    
    # Find playlist title from our favorites
    playlist_title = "Playlist"
    for playlist in favorites['playlists']:
        if playlist['id'] == playlist_id:
            playlist_title = playlist['title']
            break
    
    results = youtube.get_playlist_videos(playlist_id)
    videos = []
    
    if results and 'items' in results:
        for item in results['items']:
            # Check if this is a valid video item
            if ('snippet' in item and 
                'resourceId' in item['snippet'] and 
                'videoId' in item['snippet']['resourceId']):
                
                video_id = item['snippet']['resourceId']['videoId']
                
                # Skip deleted or private videos
                if video_id and item['snippet']['title'] != 'Deleted video':
                    # Check if video is embeddable
                    if youtube.check_video_embeddable(video_id):
                        print(f"🎵 Found embeddable playlist video: {video_id} - {item['snippet']['title']}")
                        video = {
                            'id': video_id,
                            'title': item['snippet']['title'],
                            'channel': item['snippet'].get('channelTitle', 'Unknown Channel'),
                            'thumbnail': item['snippet']['thumbnails']['medium']['url'] if 'thumbnails' in item['snippet'] else '',
                            'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
                        }
                        videos.append(video)
                    else:
                        print(f"⚠️ Skipping non-embeddable video: {video_id} - {item['snippet']['title']}")
    
    return render_template('playlist.html', videos=videos, playlist_title=playlist_title)

@app.route('/channel/<channel_id>')
@app.route('/channel/<channel_id>/<tab>')
def channel(channel_id, tab='videos'):
    """View channel videos or playlists with tabs"""
    favorites = load_favorites()
    page = int(request.args.get('page', 1))
    
    # Calculate page token based on page number
    page_token = None
    if page > 1:
        # This is a simplified approach - in practice you'd need to store page tokens
        # For now, we'll use a basic calculation
        page_token = request.args.get('pageToken')
    
    # Find channel title from our favorites
    channel_title = "Channel"
    for channel in favorites['channels']:
        if channel['id'] == channel_id:
            channel_title = channel['title']
            break
    
    videos = []
    playlists = []
    next_page_token = None
    total_results = 0
    
    if tab == 'playlists':
        # Get channel playlists
        results = youtube.get_channel_playlists(channel_id)
        if results and 'items' in results:
            for item in results['items']:
                playlist = {
                    'id': item['id'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description'],
                    'thumbnail': item['snippet']['thumbnails']['medium']['url'] if 'thumbnails' in item['snippet'] else ''
                }
                playlists.append(playlist)
    else:
        # Get recent videos with pagination
        results = youtube.get_channel_videos_recent_fast(channel_id, page_token=page_token)
        if results:
            next_page_token = results.get('nextPageToken')
            total_results = results.get('pageInfo', {}).get('totalResults', 0)
            
            if 'items' in results:
                for item in results['items']:
                    if ('snippet' in item and 
                        'id' in item and 
                        'videoId' in item['id']):
                        
                        video_id = item['id']['videoId']
                        
                        if video_id and item['snippet']['title'] != 'Deleted video':
                            video = {
                                'id': video_id,
                                'title': item['snippet']['title'],
                                'channel': item['snippet'].get('channelTitle', 'Unknown Channel'),
                                'thumbnail': item['snippet']['thumbnails']['medium']['url'] if 'thumbnails' in item['snippet'] else '',
                                'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
                            }
                            videos.append(video)
    
    # Calculate pagination info
    has_next = bool(next_page_token)
    has_prev = page > 1
    estimated_total_pages = min(10, (total_results // 20) + 1) if total_results > 0 else 1
    
    return render_template('channel.html', 
                         videos=videos, 
                         playlists=playlists,
                         channel_title=channel_title,
                         channel_id=channel_id,
                         current_tab=tab,
                         current_page=page,
                         has_next=has_next,
                         has_prev=has_prev,
                         next_page_token=next_page_token,
                         estimated_total_pages=estimated_total_pages)

@app.route('/watch/<video_id>')
def watch(video_id):
    """Watch a video and add to history"""
    # Clean the video ID - remove any extra characters
    video_id = video_id.strip()
    
    # Basic validation of video ID format (YouTube video IDs are 11 characters)
    if not video_id or len(video_id) != 11:
        flash(f'Invalid video ID: {video_id}', 'error')
        return redirect(url_for('home'))
    
    # Add to watch history
    add_to_watch_history(video_id)
    
    # Log for debugging
    print(f"🎬 Playing video ID: {video_id}")
    
    return render_template('watch.html', video_id=video_id)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)