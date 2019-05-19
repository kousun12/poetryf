import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

USER_AGENTS = [
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11',
    'Mozilla/5.0 (iPad; CPU OS 8_4_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12H321 Safari/600.1.4',
    'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)',
    'Mozilla/5.0 (compatible; Konqueror/3.5; Linux) KHTML/3.5.5 (like Gecko) (Kubuntu)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36 Edge/14.14393'
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:11.0) Gecko/20100101 Firefox/11.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36']


class MakeRequest:
    baseURL = 'http://www.azlyrics.com/'

    def get(self, url):
        req = urllib.request.Request(url, headers={'User-Agent': random.choice(USER_AGENTS)})
        try:
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as err:
            print("page not found, error " + str(err))
        except urllib.error.URLError as err:
            print("page not found, error " + str(err))
        except Exception as err:
            print("generic error " + str(err))


class Artist(MakeRequest):
    def __init__(self, artist_name: str, song_page_name: str = None):
        super().__init__()
        self.artist_name = artist_name
        self.song_page_name = song_page_name

    def get_song_page_name(self):
        return self.song_page_name or self.artist_name

    def get_song_list_page(self):
        url = self.baseURL + self.artist_name[0] + '/' + self.artist_name + '.html'
        response = self.get(url)
        return response

    def get_song_list(self):
        soup = BeautifulSoup(self.get_song_list_page().read(), 'lxml')
        songs = []
        for song in soup.find_all(target='_blank'):
            songs.append(str(song.text))
        return songs

    def get_album_infos(self):
        soup = BeautifulSoup(self.get_song_list_page().read(), 'lxml')
        album_infos = []
        for album in soup.find_all("div", {"class": "album"}):
            album_info = self.parse_album_info(album.text)
            album_infos.append(album_info)
        return album_infos

    def parse_album_info(self, raw_album_info):
        album_info = {'raw': raw_album_info}
        if raw_album_info == 'other songs:':
            return {'type': None, 'year': None, 'title': 'other songs', 'raw': raw_album_info}
        album_info_split = raw_album_info.split(':', 1)
        album_info['type'] = album_info_split[0]
        album_title_year = album_info_split[1].split('"')[1:]
        year = album_title_year[1].replace('(', '').replace(')', '').strip()
        album_info['year'] = year
        title = album_title_year[0].strip()
        album_info['title'] = title
        return album_info


class Album(Artist):
    def __init__(self, artist_name, album_info):
        super(Album, self).__init__(artist_name)
        self.album_info = album_info
        self.title = self.album_info['title']
        self.type = self.album_info['type']
        self.year = self.album_info['year']
        self.artist_name = artist_name
        self.songs = self.get_album_songs()

    def get_album_songs(self):
        songs = []
        soup = BeautifulSoup(self.get_song_list_page().read(), 'lxml')
        albums = soup.find_all("div", {"id": "listAlbum"})
        children = albums[0].find_all(['a', 'div'], recursive=False)
        current = None
        for child in children:
            if child.text == self.album_info['raw']:
                current = True
            elif current:
                if child.name != 'div':
                    if child.has_attr('target'):
                        songs.append(child.text)
                else:
                    break

        return songs

    def __repr__(self):
        return "Album: {0} from year {1} of type {2}".format(self.title, self.year, self.type)


class Song(MakeRequest):

    def __init__(self, artist_name, song_name):
        """

        :rtype: object
        """
        super().__init__()
        self.song_name = song_name
        self.artist_name = artist_name
        self.lines = self.get_lines()
        self.lyrics = '\n'.join(self.lines)

    def get_lines(self):
        time.sleep(10)
        print(f' ⇅ {self.song_name}')
        soup = BeautifulSoup(self.get_song_page(), 'lxml')
        page_lyric = soup.find_all("div", limit=22)[-1]  # lyrics start on 22nd div
        return [s.strip() for s in page_lyric.find_all(text=True)[2:]]

    def get_song_url(self):
        song_url = re.sub(r'[^\w\s]', '', self.song_name).replace(" ", '').lower()
        rest = 'lyrics/' + self.artist_name + '/' + song_url + '.html'
        return self.baseURL + rest

    def get_song_page(self):
        url = self.get_song_url()
        response = self.get(url)
        return response.read()
