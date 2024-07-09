import spotipy 
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, url_for, session, redirect
import time
from dotenv import load_dotenv
import os

load_dotenv()
CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

# initialize Flask app
app = Flask(__name__)

# set the name of the session cookie
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'

# set a random secret key to sign the cookie
app.secret_key = SECRET_KEY

# set the key for the token info in the session dictionary
TOKEN_INFO = 'token_info'

# route to handle logging in
@app.route('/')
def login():
    # create a SpotifyOAuth instance and get the authorization URL
    auth_url = create_spotify_oauth().get_authorize_url()
    # redirect the user to the authorization URL
    return redirect(auth_url)

# route to handle the redirect URI after authorization
@app.route('/redirect')
def redirect_page():
    # clear the session
    session.clear()
    # get the authorization code from the request parameters
    code = request.args.get('code')
    # exchange the authorization code for an access token and refresh token
    token_info = create_spotify_oauth().get_access_token(code)
    # save the token info in the session
    session[TOKEN_INFO] = token_info
    # redirect the user to the sort_songs route
    return redirect(url_for('sort_songs',_external=True))

# route to save the Discover Weekly songs to a playlist
@app.route('/sortSongs')
def sort_songs():
    try: 
        # get the token info from the session
        token_info = get_token()
    except:
        # if the token info is not found, redirect the user to the login route
        print('User not logged in')
        return redirect("/")

    # create a Spotipy instance with the access token
    sp = spotipy.Spotify(auth=token_info['access_token'])
    user_id = sp.current_user()['id']
    
    # looping to get all user's saved tracks
    offset = 0
    TRACKS_LIMIT = 50
    tracks_results = []
    all_tracks = {} # saves all tracks according to the genre

    while True:
        tracks_results = sp.current_user_saved_tracks(limit=TRACKS_LIMIT, offset=offset)
        tracks_results_items = tracks_results['items']
            
        for track in tracks_results_items:
            curr_song = track['track']['uri']
            artist_id = track['track']['artists'][0]['id']
            artist_info = sp.artist(artist_id)
            for genre in artist_info['genres']:
                if genre not in all_tracks:
                    all_tracks[genre] = []
                all_tracks[genre].append(curr_song)

        if tracks_results['next']:
            offset += TRACKS_LIMIT
        else:
            break
    
    genre_keys = all_tracks.keys()
    print("Available Genres: ", genre_keys)
    genre_selected = input("Please select a genre from the list above: \n")
    genre_playlist_list = all_tracks.get(genre_selected) # check to make sure not none

    
    new_playlist_id = None
    current_playlists =  sp.current_user_playlists()['items']

    for playlist in current_playlists:
        # find playlist to add to 
        if (playlist['name'] == 'of the ' + genre_selected + ' sort'):
            new_playlist_id = playlist['id']
    
    # create new playlist if it doesn't exist
    if new_playlist_id is None: 
        new_playlist = sp.user_playlist_create(user_id, 'of the ' + genre_selected + ' sort', True)
        new_playlist_id = new_playlist['id'] 

    # make sure user can only choose one from the list in UI anyways
    if not genre_playlist_list: 
        return ("No songs in genre")
    
    sp.user_playlist_add_tracks(user_id, new_playlist_id, genre_playlist_list)

    return ('New playlist created!')

# want to create functionality so that the genres don't have to be retrieved everytime

# function to get the token info from the session
def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        # if the token info is not found, redirect the user to the login route
        redirect(url_for('login', _external=False))
    
    # check if the token is expired and refresh it if necessary
    now = int(time.time())

    is_expired = token_info['expires_at'] - now < 60
    if(is_expired):
        spotify_oauth = create_spotify_oauth()
        token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id = CLIENT_ID,
        client_secret = CLIENT_SECRET,
        redirect_uri = url_for('redirect_page', _external=True),
        scope='user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private'
    )

app.run(debug=True)

