from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import requests
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# YouTube API configuration
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3'

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
    """Main page"""
    return render_template('index.html')

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
    results = youtube.get_playlist_videos(playlist_id)
    videos = []
    playlist_title = "Playlist"
    
    if results and 'items' in results:
        for item in results['items']:
            if 'videoId' in item['snippet']['resourceId']:
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
    results = youtube.get_channel_videos(channel_id)
    videos = []
    channel_title = "Channel"
    
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
        
        if videos:
            channel_title = videos[0]['channel']
    
    return render_template('channel.html', videos=videos, channel_title=channel_title)

@app.route('/watch/<video_id>')
def watch(video_id):
    """Watch a video"""
    return render_template('watch.html', video_id=video_id)

@app.route('/favorites')
def favorites():
    """Your favorite playlists and channels"""
    # Customize these with your actual playlist IDs and channel IDs
    favorite_playlists = [
        {'id': 'PLrAXtmRdnEQy4VElvNpzeLVnOO8bWqTkP', 'title': 'Kids Educational Videos'},
        {'id': 'PLQOGdSeUGEwt2_-9_lZP6_NvHO_jdAbQE', 'title': 'Science for Kids'},
        # Add your actual playlist IDs here
    ]
    
    favorite_channels = [
        {'id': 'UCKlLH1lp7QEKIbLbXPjTU7A', 'title': 'SciShow Kids'},
        {'id': 'UCNVEsYbiZjH5QLmGeSgj9wA', 'title': 'National Geographic Kids'},
        # Add your actual channel IDs here
    ]
    
    return render_template('favorites.html', 
                         playlists=favorite_playlists, 
                         channels=favorite_channels)

if __name__ == '__main__':
    # For DigitalOcean deployment
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
