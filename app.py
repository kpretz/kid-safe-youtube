from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import os
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# YouTube API configuration
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3'

# Admin password (set via environment variable)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# File to store favorites (persists across app restarts)
FAVORITES_FILE = 'favorites.json'

def load_favorites():
    """Load favorites from file"""
    try:
        with open(FAVORITES_FILE, 'r') as f:
            return json.load(f)
    except:
        # Default favorites if file doesn't exist
        return {
            'playlists': [
                {
                    'id': 'PLrAXtmRdnEQy4VElvNpzeLVnOO8bWqTkP',
                    'title': 'Science for Kids',
                    'description': 'Educational science videos for children'
                }
            ],
            'channels': [
                {
                    'id': 'UCKlLH1lp7QEKIbLbXPjTU7A',
                    'title': 'SciShow Kids',
                    'description': 'Science education for kids'
                }
            ]
        }

def save_favorites(favorites):
    """Save favorites to file"""
    with open(FAVORITES_FILE, 'w') as f:
        json.dump(favorites, f, indent=2)

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
            flash(f'Added playlist: {info["title"]}', 'success')
    else:
        # Check if already exists
        if any(c['id'] == info['id'] for c in favorites['channels']):
            flash('Channel already exists!', 'error')
        else:
            favorites['channels'].append(info)
            save_favorites(favorites)
            flash(f'Added channel: {info["title"]}', 'success')
    
    return redirect(url_for('admin'))

@app.route('/admin/remove/<item_type>/<item_id>')
def admin_remove(item_type, item_id):
    """Remove playlist or channel"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    favorites = load_favorites()
    
    if item_type == 'playlist':
        favorites['playlists'] = [p for p in favorites['playlists'] if p['id'] != item_id]
        flash('Playlist removed!', 'success')
    elif item_type == 'channel':
        favorites['channels'] = [c for c in favorites['channels'] if c['id'] != item_id]
        flash('Channel removed!', 'success')
    
    save_favorites(favorites)
    return redirect(url_for('admin'))

@app.route('/search')
def search():
    """Search for videos"""
    query = request.args.get('q', '')
    if not query:
        return render_template('search.html', videos=[], query='')
    
    results = youtube.search_videos(query)
    videos = []
    
    if results and 'items' in results:
        for item in results['items']:
            video = {
                'id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'channel': item['snippet']['channelTitle'],
                'thumbnail': item['snippet']['thumbnails']['medium']['url'],
                'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
            }
            videos.append(video)
    
    return render_template('search.html', videos=videos, query=query)

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
                    video = {
                        'id': video_id,
                        'title': item['snippet']['title'],
                        'channel': item['snippet'].get('channelTitle', 'Unknown Channel'),
                        'thumbnail': item['snippet']['thumbnails']['medium']['url'] if 'thumbnails' in item['snippet'] else '',
                        'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
                    }
                    videos.append(video)
    
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
                    video = {
                        'id': video_id,
                        'title': item['snippet']['title'],
                        'channel': item['snippet'].get('channelTitle', 'Unknown Channel'),
                        'thumbnail': item['snippet']['thumbnails']['medium']['url'] if 'thumbnails' in item['snippet'] else '',
                        'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
                    }
                    videos.append(video)
    
    return render_template('channel.html', videos=videos, channel_title=channel_title)

@app.route('/watch/<video_id>')
def watch(video_id):
    """Watch a video"""
    # Basic validation of video ID format
    if not video_id or len(video_id) < 10:
        flash('Invalid video ID', 'error')
        return redirect(url_for('home'))
    
    return render_template('watch.html', video_id=video_id)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)