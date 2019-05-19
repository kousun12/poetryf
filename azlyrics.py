import os
import sqlite3
from songs import Song, Artist, Album
import argparse

ARTISTS = [
    # Artist('cohen', 'leonardcohen'),
    Artist('dylan', 'bobdylan'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="clear the entire db before scraping")
    parser.add_argument("-w", "--write", action="store_true", help="write database to output txt file")
    parser.add_argument("-d", "--database", type=str, help="database name", default='songs.db')
    parser.add_argument("-o", "--out", type=str, help="out file", default='out/songs.txt')

    args = parser.parse_args()
    db_file = args.database

    if args.fresh and os.path.exists(db_file):
        conn = sqlite3.connect(db_file, isolation_level=None)
        cursor = conn.cursor()
        drop_tables(cursor)
        os.remove(db_file)
        print(f'deleted {db_file}')
        conn.commit()
        cursor.close()

    conn = sqlite3.connect(db_file, isolation_level=None)
    cursor = conn.cursor()
    create_tables(cursor)

    scrape_artists(ARTISTS, cursor)

    if args.write:
        songs = songs_from_db(cursor)
        write_to(args.out, songs)

    conn.commit()
    cursor.close()


def scrape_artists(artists, cursor):
    for artist in artists:
        albums, total = scrape_albums(artist, cursor)
        print(f'☛ {artist.artist_name} ✯ {len(albums)} albums ✯ {total} songs')


def _song_exists(name, artist, cursor):
    statement = """SELECT id FROM songs WHERE name = ? AND artist = ?;"""
    return cursor.execute(statement, (name, artist)).fetchall()


def scrape_albums(artist, cursor):
    res = []
    count = 0
    artist_name = artist.get_song_page_name()
    for album in artist.get_album_infos():
        album = Album(artist.artist_name, album)
        res.append(album)
        print(f'{album.title} [{len(album.songs)}]')
        for song_name in album.songs:
            count = count + 1
            if _song_exists(song_name, artist_name, cursor):
                print(f' ↛ {song_name} [skip]')
            else:
                song = Song(artist_name, song_name)
                _insert_song(song, album, cursor)
    return res, count


def _insert_song(s, album, cursor):
    row = (s.song_name, s.artist_name, album.type, album.title, album.year, s.lyrics)
    cursor.execute("INSERT INTO songs (name, artist, url, type, year, lyrics) VALUES (?, ?, ?, ?, ?, ?);", row)


def create_tables(cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS songs(
           id INTEGER PRIMARY KEY, 
           name VARCHAR(124),
           artist VARCHAR(256),
           url VARCHAR(256),
           type VARCHAR(124),
           year INTEGER,
           lyrics VARCHAR(256)
           );""")


def drop_tables(cursor):
    for table in ['SONGS']:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')


def write_to(filename, songs):
    overwrote = False
    if os.path.exists(filename):
        os.remove(filename)

    f = open(filename, "w")
    f.write('\n\n\n\n\n\n'.join([f'{s.song_name}\n\n\n\n\n\n{s.lyrics}' for s in songs]))
    f.close()
    if overwrote:
        print(f'✍︎ overwrote {filename} [{len(songs)} songs]')
    else:
        print(f'✍︎ wrote to {filename} [{len(songs)} songs]')


def songs_from_db(cursor):
    statement = "SELECT name, artist, lyrics from songs;"
    results = cursor.execute(statement).fetchall()
    if not results:
        print("query for songs failed")
        return None
    songs = []
    for name, artist, lyrics in results:
        song = Song(artist, name, lyrics)
        songs.append(song)

    return songs


if __name__ == '__main__':
    main()
