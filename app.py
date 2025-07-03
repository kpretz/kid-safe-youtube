from flask import Flask, render_template, request
import requests
import os

app = Flask(__name__)

# YouTube API configuration
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3'

# YOUR FAMILY'S FAVORITE PLAYLISTS AND CHANNELS
# Add your actual playlist IDs and channel IDs here
FAMILY_PLAYLISTS = [
    {
        'id': 'PLrAXtmRdnEQy4VElvNpzeLVnOO8bWqTkP',
        'title': 'Science for Kids',
        'description': 'Educational science videos for children'
    },
    {
        'id': 'PLQOGdSeUGEwt2_-9_lZP6_NvHO_jdAbQE',
        'title': 'Fun Learning',
        'description': 'Fun educational content'
    },
    # Add more playlists here - just copy the playlist ID from YouTube URLs
]

FAMILY_CHANNELS = [
    {
        'id': 'UCKlLH1lp7QEKIbLbXPjTU7A',
        'title': 'SciShow Kids',
        'description': 'Science education for kids'
    },
    {
        'id': 'UCNVEsYbiZjH5QLmGeSgj9wA',
        'title': 'National Geographic Kids',
        'description': 'Nature and science content'
    },
    {
        'id': 'UC4-a7R9g-yQhTGHrKKGYvMA',
        'title': 'Crash Course Kids',
        'description': 'Educational videos on science topics'
    },
    # Add more channels here - get channel IDs from YouTube URLs
]

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
    return render_template('index.html', 
                         playlists=FAMILY_PLAYLISTS, 
                         channels=FAMILY_CHANNELS)

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
    # Find playlist title from our hardcoded list
    playlist_title = "Playlist"
    for playlist in FAMILY_PLAYLISTS:
        if playlist['id'] == playlist_id:
            playlist_title = playlist['title']
            break
    
    results = youtube.get_playlist_videos(playlist_id)
    videos = []
    
    if results and 'items' in results:
        for item in results['items']:
            if 'resourceId' in item['snippet'] and 'videoId' in item['snippet']['resourceId']:
                video = {
                    'id': item['snippet']['resourceId']['videoId'],
                    'title': item['snippet']['title'],
                    'channel': item['snippet']['channelTitle'],
                    'thumbnail': item['snippet']['thumbnails']['medium']['url'],
                    'description': item['snippet']['description'][:100] + '...' if len(item['snippet']['description']) > 100 else item['snippet']['description']
                }
                videos.append(video)
    
    return render_template('playlist.html', videos=videos, playlist_title=playlist_title)

@app.route('/channel/<channel_id>')
def channel(channel_id):
    """View channel videos"""
    # Find channel title from our hardcoded list
    channel_title = "Channel"
    for channel in FAMILY_CHANNELS:
        if channel['id'] == channel_id:
            channel_title = channel['title']
            break
    
    results = youtube.get_channel_videos(channel_id)
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
    
    return render_template('channel.html', videos=videos, channel_title=channel_title)

@app.route('/watch/<video_id>')
def watch(video_id):
    """Watch a video"""
    return render_template('watch.html', video_id=video_id)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
