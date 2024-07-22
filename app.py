import spotipy 
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, url_for, session, redirect, render_template
import jinja2
from flask_session import Session
import redis
import time
from dotenv import load_dotenv
import os
from flask_redis import FlaskRedis
import cProfile

from all_tracks import all_tracks

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

# configure the flask session for server side session storage 
app.config['SESSION_TYPE'] = 'redis' #originally filesystem
# app.config['SESSION_TYPE'] = 'filesystem' #originally filesystem

redis_client = redis.Redis(host='localhost', port=6379, db=0)
app.config['SESSION_REDIS'] = redis_client

app.config['SESSION_PERMANENT'] = False
app.config['SECRET_KEY'] = SECRET_KEY

# Initialize the session
Session(app) 

# set the key for the token info in the session dictionary
TOKEN_INFO = 'token_info'

# ROUTE TO HANDLE LOGIN
@app.route('/')
def login():
    # create a SpotifyOAuth instance and get the authorization URL
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url) # redirect the user to the authorization URL

# HANDLE REDIRECT AFTER AUTHENTICATION
@app.route('/redirect')
def redirect_page():
    # clear the session
    session.clear() # session.pop('the thing', default=None)
    # get the authorization code from the request parameters
    code = request.args.get('code')
    # exchange the authorization code for an access token and refresh token
    token_info = create_spotify_oauth().get_access_token(code)
    # save the token info in the session
    session[TOKEN_INFO] = token_info
    # redirect the user to the sort_songs route redirect(url_for('sort_songs',_external=True))
    return redirect(url_for('wait_page')) # external?

# PAGE WHERE USER WAITS FOR TRACKS TO BE RETRIEVED
@app.route('/wait')
def wait_page():
    try: 
        # get the token info from the session
        token_info = get_token()
    except:
        # if the token info is not found, redirect the user to the login route
        print('User not logged in')
        return redirect("/")

    # create a Spotipy instance with the access token
    spotify_user = spotipy.Spotify(auth=token_info['access_token'])
    
    # build dictionary of user tracks and genres
    all_tracks_instance = all_tracks()
    get_user_tracks(spotify_user, all_tracks_instance)

    return redirect(url_for('sort_songs'))

# ROUTE TO SAVE SONGS
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
    spotify_user = spotipy.Spotify(auth=token_info['access_token'])
    
    # retrieve tracks if the user has already 
    session_info_dict = session.get('ALL_TRACKS') 
    session_all_tracks = session_info_dict.get('all_tracks_dict', {})
    session_top_genres = session_info_dict.get('top_genres', [])

    last_fetched = session.get('LAST_FETCHED')
    CACHE_DURATION = 3600 # only save for an hour
    
    # if cache duration is up or user hasn't fetched tracks already 
    # ** session_info_dict or all tracks
    if not session_info_dict or (time.time() - last_fetched > CACHE_DURATION):
        return redirect(url_for('wait_page'))

    # this would be in the UI anyways
    print("Available Genres: ", session_top_genres)
    genre_selected = input("Please select a genre from the list above: \n")
    
    # get the list of songs in the chosen genre [shouldn't ever be none but maybe add case]
    genre_playlist_list = session_all_tracks.get(genre_selected) 
    print(len(genre_playlist_list))
    # call function to create new playlist
    new_playlist_url = create_genre_playlist(spotify_user, genre_selected, genre_playlist_list)
    print(new_playlist_url)

    return session_all_tracks

    # would have to adjust this with the UI
    #next_choice = input("Do you want to pick another? ")
    #if next_choice == 'yes':
    #     sort_songs()

    #return "all done"

# -- HELPER FUNCTIONS --
# GET TOKEN INFO FROM SESSION
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

# CREATE THE SPOITIFY OAUTH
def create_spotify_oauth(): #  want to upload image at somepoint
    return SpotifyOAuth(
        client_id = CLIENT_ID,
        client_secret = CLIENT_SECRET,
        redirect_uri = url_for('redirect_page', _external=True),
        scope='user-library-read playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private'
    )

# GETS ALL USER TRACKS AND CREATES DICTIONARY
def get_user_tracks(spotify_user, all_tracks_instance):
    
    try:
        # get the token info from the session
        token_info = get_token()
    except:
        # if the token info is not found, redirect the user to the login route
        print('User not logged in')
        return redirect("/")
        
    print('getting your songs!', '\n')

    all_results_items = []
    tracks_results = spotify_user.current_user_saved_tracks()
    all_results_items.extend(tracks_results['items'])
    
    # loop through all user tracks 
    while tracks_results['next']:
        tracks_results = spotify_user.next(tracks_results)
        all_results_items.extend(tracks_results['items'])

    print("adding tracks")
    for track in all_results_items:
        all_tracks_instance.add_track(track, spotify_user)
    print('tracks added')

    # now all tracks are saved, find user's top genres
    all_tracks_instance.find_top_genres()

    # create dictionary of all tracks and top genres to save to session variable
    session_info_dict = { 
                    'all_tracks_dict': all_tracks_instance.all_tracks_dict, 
                    'top_genres': all_tracks_instance.top_genres
                }
    
    # save the tracks to a session variable so that it is only done once
    session['ALL_TRACKS'] = session_info_dict
    session['LAST_FETCHED'] = time.time()
    print('returning to next page')
    # might have to change because its an object
    return all_tracks_instance

# CREATES NEW PLAYLIST 
def create_genre_playlist(spotify_user, genre_selected, genre_playlist_list):

    try:
        # get the token info from the session
        token_info = get_token()
    except:
        # if the token info is not found, redirect the user to the login route
        print('User not logged in')
        return redirect("/")
    
    # get user id
    user_id = spotify_user.current_user()['id']
    new_playlist_name = 'of the ' + genre_selected + ' sort'

    # find playlist to add to 
    sorted_playlist_id = None
    current_playlists =  spotify_user.current_user_playlists()['items']

    # check if playlist exists
    for playlist in current_playlists:
        if (playlist['name'] == new_playlist_name):
            sorted_playlist_id = playlist['id']
            existing_tracks = spotify_user.playlist_tracks(
               sorted_playlist_id,
               fields='items(track(uri)),next'
            )

            # append all existing tracks
            existing_tracks_list = []
            existing_tracks_list.extend([item['track']['uri'] for item in existing_tracks['items']]) 
       
            while existing_tracks['next']:
                existing_tracks = spotify_user.next(existing_tracks)
                existing_tracks_list.extend([item['track']['uri'] for item in existing_tracks['items']])

            # remove what overlaps in existing playlist
            genre_playlist_list = list(set(genre_playlist_list) - set(existing_tracks_list))

            break
    
    # create new playlist if it doesn't exist
    if sorted_playlist_id is None: 
        new_playlist = spotify_user.user_playlist_create(user_id, new_playlist_name, False)
        sorted_playlist_id = new_playlist['id'] 

    # this helps for when all songs overlap in existing playlist
    if not genre_playlist_list: 
        return ("No songs in genre or all songs already added")
    
    # spotify allows only 100 songs to be added at a time, add in 100 song sections
    sections = [genre_playlist_list[i:i + 100] for i in range(0, len(genre_playlist_list), 100)]

    for section in sections:
        spotify_user.playlist_add_items(sorted_playlist_id, section)

    # would have to just access url seperately returns as json
    new_playlist_url = spotify_user.playlist(
        sorted_playlist_id, 
        fields='external_urls(spotify)'
    )['spotify']
    
    return new_playlist_url

if __name__ == '__main__':
    app.run(debug=True)