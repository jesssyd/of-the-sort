class all_tracks:
    def __init__(self):
        self.all_tracks_dict = {}
        self.genre_count = {}
        self.top_genres = []
    
    def add_track(self, track, sp):
        
        curr_song = track['track'] if ('track' in track) else track # handle documentation for track vs. playlist
        print('in class')
        song_uri = curr_song['uri']
        artist_id = curr_song['artists'][0]['id']

        # handle if its an episode, just skip to next 
        if not artist_id: 
            return 

        artist_info = sp.artist(artist_id)
        
        print('adding genre info')
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
        # self.top_genres = [k for k, v in sorted(self.all_tracks_dict.items(), key=lambda key:len(self.all_tracks_dict[key]), reverse=True)][:15] 
        # self.top_genres = [genre for genre, _ in self.top_genres]
