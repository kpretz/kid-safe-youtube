from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import os
import json
import base64

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

import json
import base64

# File to store favorites (for local development)
FAVORITES_FILE = 'favorites.json'

def load_favorites():
    """Load favorites from environment variable or file"""
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
            'channels': []
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
    """Save favorites to environment variable and file"""
    # Save to file (for local development)
    try:
        with open(FAVORITES_FILE, 'w') as f:
            json.dump(favorites, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save to file: {e}")
    
    # Try to update DigitalOcean environment variable automatically
    update_digitalocean_env_var(favorites)
    
    return favorites

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
    
    def get_channel_videos(self, channel_id, max_results=20):
        """Get recent videos from a channel"""
        url = f"{YOUTUBE_API_BASE}/search"
        params = {
            'part': 'snippet',
            'channelId': channel_id,
            'type': 'video',
            'order': 'date',
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
    """Main page with family favorites"""
    favorites = load_favorites()
    return render_template('index.html', 
                         playlists=favorites['playlists'], 
                         channels=favorites['channels'])

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
    """Search for videos with debugging"""
    query = request.args.get('q', '')
    print(f"🔍 Search request received - Query: '{query}'")
    
    if not query:
        print("❌ No query provided, showing empty search page")
        return render_template('search.html', videos=[], query='')
    
    try:
        print(f"🔑 Using API key: {YOUTUBE_API_KEY[:10]}..." if YOUTUBE_API_KEY else "❌ No API key found!")
        
        # Call YouTube API
        print("📡 Calling YouTube API...")
        results = youtube.search_videos(query)
        
        print(f"📊 API Response type: {type(results)}")
        if results:
            print(f"📊 API Response keys: {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}")
            if 'items' in results:
                print(f"📊 Number of items returned: {len(results['items'])}")
            else:
                print("⚠️ No 'items' key in response")
        else:
            print("❌ API returned None/empty response")
        
        videos = []
        
        if results and 'items' in results:
            print("🎬 Processing video items...")
            for i, item in enumerate(results['items']):
                try:
                    print(f"  📹 Item {i}: {list(item.keys()) if isinstance(item, dict) else 'Not a dict'}")
                    
                    if 'id' in item:
                        print(f"    🆔 ID structure: {item['id']}")
                        if isinstance(item['id'], dict) and 'videoId' in item['id']:
                            video_id = item['id']['videoId']
                            print(f"    ✅ Video ID: {video_id}")
                            
                            # Check snippet
                            if 'snippet' in item:
                                snippet = item['snippet']
                                print(f"    📝 Snippet keys: {list(snippet.keys())}")
                                
                                video = {
                                    'id': video_id,
                                    'title': snippet.get('title', 'No title'),
                                    'channel': snippet.get('channelTitle', 'Unknown Channel'),
                                    'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                                    'description': snippet.get('description', '')[:100] + '...' if snippet.get('description', '') else 'No description'
                                }
                                videos.append(video)
                                print(f"    ✅ Added video: {video['title']}")
                            else:
                                print(f"    ❌ No snippet in item {i}")
                        else:
                            print(f"    ❌ No videoId in item {i} ID structure")
                    else:
                        print(f"    ❌ No 'id' key in item {i}")
                        
                except Exception as e:
                    print(f"    ❌ Error processing item {i}: {e}")
                    
        print(f"🎯 Final result: {len(videos)} videos processed")
        return render_template('search.html', videos=videos, query=query)
        
    except Exception as e:
        print(f"💥 Search function error: {e}")
        print(f"💥 Error type: {type(e)}")
        import traceback
        print(f"💥 Full traceback: {traceback.format_exc()}")
        
        # Return error page instead of crashing
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
def channel(channel_id):
    """View channel videos"""
    favorites = load_favorites()
    
    # Find channel title from our favorites
    channel_title = "Channel"
    for channel in favorites['channels']:
        if channel['id'] == channel_id:
            channel_title = channel['title']
            break
    
    results = youtube.get_channel_videos(channel_id)
    videos = []
    
    if results and 'items' in results:
        for item in results['items']:
            # Check if this is a valid video item from search results
            if ('snippet' in item and 
                'id' in item and 
                'videoId' in item['id']):
                
                video_id = item['id']['videoId']
                
                # Skip deleted or private videos
                if video_id and item['snippet']['title'] != 'Deleted video':
                    # Check if video is embeddable
                    if youtube.check_video_embeddable(video_id):
                        print(f"📺 Found embeddable channel video: {video_id} - {item['snippet']['title']}")
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
    
    return render_template('channel.html', videos=videos, channel_title=channel_title)

@app.route('/watch/<video_id>')
def watch(video_id):
    """Watch a video"""
    # Clean the video ID - remove any extra characters
    video_id = video_id.strip()
    
    # Basic validation of video ID format (YouTube video IDs are 11 characters)
    if not video_id or len(video_id) != 11:
        flash(f'Invalid video ID: {video_id}', 'error')
        return redirect(url_for('home'))
    
    # Log for debugging
    print(f"🎬 Playing video ID: {video_id}")
    
    return render_template('watch.html', video_id=video_id)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)