import spotipy 
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, request, url_for, session, redirect
from flask_session import Session
import time
from dotenv import load_dotenv
import os

import json # just for testing

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
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions in the filesystem
app.config['SESSION_PERMANENT'] = False    # Sessions are not permanent

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
    session.clear()
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
    sp = spotipy.Spotify(auth=token_info['access_token'])
    
    # build dictionary of user tracks and genres
    get_user_tracks(sp)

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
    sp = spotipy.Spotify(auth=token_info['access_token'])
    
    # retrieve tracks if the user has already 
    all_tracks = session.get('ALL_TRACKS')
    last_fetched = session.get('LAST_FETCHED')
    CACHE_DURATION = 3600 # only save for an hour

    # if cache duration is up or user hasn't fetched tracks already 
    if not all_tracks or (time.time() - last_fetched > CACHE_DURATION):
        return redirect(url_for('wait_page'))

    # this would be in the UI anyways
    genre_keys = all_tracks.keys()
    print("Available Genres: ", genre_keys)
    genre_selected = input("Please select a genre from the list above: \n")
    
    # get the list of songs in the chosen genre
    genre_playlist_list = all_tracks.get(genre_selected) # check to make sure not none

    # call function to create new playlist
    new_playlist_url = create_genre_playlist(sp, genre_selected, genre_playlist_list)
    print(new_playlist_url)

    # would have to adjust this with the UI
    next_choice = input("Do you want to pick another? ")
    if next_choice == 'yes':
        sort_songs()

    
    return ('New playlist created!') 


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
def get_user_tracks(sp_user):

    offset = 0 # index to offset by 
    TRACKS_LIMIT = 50
    tracks_results = [] # temporarily hold the list returned from current_user_saved_tracks
    all_tracks = {} # saves all tracks according to the genre
           
    # loop through all user tracks 
    while True:
        tracks_results = sp_user.current_user_saved_tracks(limit=TRACKS_LIMIT, offset=offset)
        tracks_results_items = tracks_results['items']
        
        for track in tracks_results_items:
            curr_song = track['track']['uri']
            artist_id = track['track']['artists'][0]['id']
            artist_info = sp_user.artist(artist_id)
            for genre in artist_info['genres']:
                # add new genre if it doesn't exist
                if genre not in all_tracks:
                    all_tracks[genre] = (0, [])

                # make sure there are not duplicates
                if curr_song not in all_tracks[genre][1]:
                    all_tracks[genre] = (all_tracks[genre][0] + 1, all_tracks[genre][1] + [curr_song])

        # add offset if there are more tracks
        if not tracks_results['next']:
            break

        offset += TRACKS_LIMIT

        # save the tracks to a session variable so that it is only done once
        session['ALL_TRACKS'] = all_tracks
        session['LAST_FETCHED'] = time.time()

        # with open("tracks.txt", "w") as fp:
        #     json.dump(all_tracks, fp)  # encode dict into JSON

    return all_tracks

# CREATES NEW PLAYLIST 
def create_genre_playlist(sp_user, genre_selected, genre_playlist_list):

    # get user id
    user_id = sp_user.current_user()['id']

    # find playlist to add to 
    new_playlist_id = None
    current_playlists =  sp_user.current_user_playlists()['items']

    for playlist in current_playlists:
        if (playlist['name'] == 'of the ' + genre_selected + ' sort'):
            new_playlist_id = playlist['id']
    
    # create new playlist if it doesn't exist
    if new_playlist_id is None: 
        new_playlist = sp_user.user_playlist_create(user_id, 'of the ' + genre_selected + ' sort', True)
        new_playlist_id = new_playlist['id'] 

    # make sure user can only choose one from the list in UI anyways
    if not genre_playlist_list: 
        return ("No songs in genre")
    
    sp_user.user_playlist_add_tracks(user_id, new_playlist_id, genre_playlist_list)

    new_playlist_url = new_playlist['external_urls']['spotify']

    return new_playlist_url

app.run(debug=True)

