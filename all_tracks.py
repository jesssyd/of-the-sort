class all_tracks:
    def __init__(self):
        self.all_tracks_dict = {}
        self.genre_count = {}
        self.top_genres = []
        self.artists_genres_dict = {}
    
    def add_track(self, track, sp):
        # handle documentation for track vs. playlist
        if 'track' in track and track['track'] is not None:
            curr_song = track['track']
        else:
            curr_song = track
 
        if curr_song is None or 'uri' not in curr_song:
            return
        
        print(curr_song['name'], '\n')
        song_uri = curr_song['uri']
        artist_id = curr_song['artists'][0]['id'] # this only handles the first artist also

        # handle if its an episode or local file, just skip to next 
        if not artist_id: 
            return 

        artist_info = sp.artist(artist_id)
        
        for genre in artist_info['genres']:
            # add new genre if it doesn't exist
            if genre not in self.all_tracks_dict:
                self.all_tracks_dict[genre] = []
                self.genre_count[genre] = 0

            # make sure there are not duplicates
            if song_uri not in self.all_tracks_dict[genre]:
                self.all_tracks_dict[genre].append(song_uri)
                self.genre_count[genre] += 1
    
    def find_top_genres(self):
        self.top_genres = [genre for genre, tracks in sorted(self.all_tracks_dict.items(), key=lambda item: len(item[1]), reverse=True)][:15]
        