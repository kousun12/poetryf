import os
import sqlite3
from songs import Song, Artist, Album
import argparse

ARTISTS = [
    Artist('cohen', 'leonardcohen'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="clear the entire db before scraping")
    parser.add_argument("-d", "--database", type=str, help="database name", default='songs.db')

    args = parser.parse_args()
    db_file = args.database

    if args.fresh and os.path.exists(db_file):
        conn = sqlite3.connect(db_file, isolation_level=None)  # auto commit
        cursor = conn.cursor()
        drop_tables(cursor)
        os.remove(db_file)
        print(f'deleted {db_file}')
        conn.commit()
        cursor.close()

    conn = sqlite3.connect(db_file, isolation_level=None)  # auto commit
    cursor = conn.cursor()
    create_tables(cursor)

    scrape_artists(ARTISTS, cursor)

    conn.commit()
    cursor.close()


def scrape_artists(artists, cursor):
    for artist in artists:
        scrape_albums(artist.get_album_infos(), artist, cursor)


def _song_exists(name, cursor):
    statement = """SELECT id FROM songs WHERE name = ?;"""
    return cursor.execute(statement, name).fetchall()


def scrape_albums(albums, artist, cursor):
    for album in albums:
        album = Album('cohen', album)
        print(album.title)
        for song_name in album.songs:
            if not _song_exists(song_name, cursor):
                song = Song(artist.get_song_page_name(), song_name)
                _insert_song(song, album, cursor)
            else:
                print(f' ↛ {song_name} [skip]')


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


if __name__ == '__main__':
    main()
