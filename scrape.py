"""
Web scraper that scrapes a poets' poems from the PoetryFoundation
website into a sqlite database
"""

from __future__ import print_function

import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
import argparse
import os
import re

from bs4 import BeautifulSoup

from poem import Poem
from sql_util import *

POET_URL = "https://www.poetryfoundation.org/poets/%s#about"
COLLECTION_URL = "https://www.poetryfoundation.org/collections/%s"

POETS = "poets.txt"
COLLECTIONS = "collections.txt"

INSERT_LINE = """INSERT INTO LINES (lid, pid, poem_line) VALUES (?, ?, ?);"""
INSERT_TAG = """INSERT INTO TAGS (pid, name) VALUES (?, ?);"""
INSERT_POEM = """INSERT INTO POEMS (poem_name, poet_id, num_lines%s) VALUES (?, ?, ?%s);"""
INSERT_POET_DEAD = """INSERT INTO POETS (poet_name, born, died) VALUES (?, ?, ?);"""
INSERT_POET_ALIVE = """INSERT INTO POETS (poet_name, born) VALUES (?, ?);"""
INSERT_POET = """INSERT INTO POETS (poet_name) VALUES (?);"""

SELECT_POET_ID = """SELECT PID FROM POETS WHERE poet_name = ?;"""
SELECT_POET_EXISTS = """SELECT * FROM POETS WHERE poet_name = ?;"""

SELECT_POEM_ID = """SELECT PID FROM POEMS WHERE poem_name = ? AND poet_id = ?;"""
SELECT_POEM_EXISTS = """SELECT * FROM POEMS WHERE poem_name = ? AND poet_id = ?;"""

SELECT_TAG_EXISTS = """SELECT * FROM TAGS WHERE name = ?;"""

WHITESPACE = '[ \t\n\r]+'


def main():
    """
    Main function for running from command line
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="clear the entire db before scraping")
    parser.add_argument("--batch", action="store_true", help="scrape batch poems by authors in poets.txt")
    parser.add_argument("--full_run", action="store_true", help="delete all and batch collections and poets")
    parser.add_argument("-c", "--collection", type=str, help="parse a collection")
    parser.add_argument("-t", "--tag", type=str, help="tag(s) to add to this collection, csv")

    args = parser.parse_args()

    conn = sqlite3.connect(DATABASE, isolation_level=None)  # auto commit
    cursor = conn.cursor()

    if (args.fresh or args.full_run)and os.path.exists(DATABASE):
        drop_tables(cursor)
        os.remove(DATABASE)
        print(f'deleted {DATABASE}')

    create_tables(cursor)

    if args.full_run:
        batch_run(cursor)
        batch_collections(cursor)
    elif args.collection:
        if not args.tag:
            raise Exception("You should tag collections")
        if args.batch:
            batch_collections(cursor)
        else:
            add_poem_collection(args.collection, args.tag, cursor)
    else:
        if args.batch:
            batch_run(cursor)
        else:
            poet = input('Enter a poet or RET to read poets.txt: ')
            add_poet_poems(poet, cursor)

    conn.commit()
    cursor.close()


def batch_run(cursor):
    """
    Batch opens poets from in POETS adds their poems to cursor
    """
    with open(POETS, "r") as poet_file:
        poets = poet_file.readlines()
        for poet in poets:
            if not poet.startswith('#'):
                add_poet_poems(poet, cursor)


def batch_collections(cursor):
    with open(COLLECTIONS, "r") as cols_file:
        cols = cols_file.readlines()
        for line in cols:
            match = re.search("(?P<id>\\d+):(?P<tags>.*)", line)
            add_poem_collection(match.group('id'), match.group('tags'), cursor)


def poet_name_to_dashes(name):
    """
    Returns name with dashes instead of spaces
    """
    name = name.lower()
    return re.sub('[^a-z]+', '-', name)


def clean_poet_name(name):
    poet = name.rstrip('\n')
    poet_dashes = poet_name_to_dashes(poet)
    print("poet is " + poet_dashes)
    return poet_dashes


def add_poet_poems(poet_name, cursor):
    """
    Adds all of the poems by poet to cursor
    """

    poet_soup = find_poet_page(clean_poet_name(poet_name))

    if not poet_soup:
        print("Poet not found")
        return

    poet_years = find_poet_years(poet_soup)
    # todo: could also add in region
    poet_id = create_poet(poet_name, poet_years, cursor)

    poem_links = find_poem_links(poet_soup)

    if not poem_links:
        print("No poems found")
        return

    for poem in poem_links:
        url = poem.get('href')
        soup = soup_for(url)
        poem = find_poem(soup, url)
        if poem:
            print("done")
            write_poem(poem, poet_id, cursor)


def add_poem_collection(collection_id, tag_csv, cursor):
    """
    Adds all of the poems in a collection
    """

    url = COLLECTION_URL % str(collection_id)
    parsed = poem_page_from(url)

    if not parsed:
        print("Collection not found")
        return

    poem_links = find_poem_links(parsed)

    if not poem_links:
        print("No poems found")
        return

    for poem in poem_links:
        poem_url = poem.get('href')
        soup = soup_for(poem_url)
        poem = find_poem(soup, poem_url)
        poet_id = create_poet(_author_from(soup), None, cursor)

        if poem:
            print("done")
            write_poem(poem, poet_id, cursor, tag_csv)


### Begin scraping functions

def soup_for(poem_url):
    req = urllib.request.Request(poem_url, headers={'User-Agent': "Google Chrome"})
    page = urllib.request.urlopen(req)
    return BeautifulSoup(page.read(), "html.parser")


def _author_from(soup):
    return find_span_beginning_remove(soup, 'c-txt_attribution', '^By')


def find_poem(poem_soup, url):
    """
    Given a poem url, attempts to parse the page. If successful, returns a
    Poem
    """
    try:
        poem_title = poem_soup.find('h1')

        if poem_title:
            title = unescape_text(poem_title.text, left=True, right=True)
            print("reading " + title)

            lines = find_poem_lines(poem_soup)
            translator = find_span_beginning_remove(poem_soup,
                                                    'c-txt_attribution',
                                                    'translated by')
            source = find_span_beginning_remove(poem_soup, 'c-txt_note', 'source:')
            year = None
            if source:
                year = find_poem_year(source)
            return Poem(title=title, lines=lines, translator=translator,
                        source=source, year=year, url=url)

    except urllib.error.HTTPError as err:
        print("Poem not found, error " + str(err))
    except urllib.error.URLError as err:
        print("Poem not found, error " + str(err))
    return None


def find_poet_years(soup):
    """
    Returns the years alive of the poet if found in soup
    """
    age_pattern = r'(b. )?\d{4}(-\d{4})?'
    poet_age_str = find_span_element(soup, 'c-txt_poetMeta', age_pattern)
    if poet_age_str:
        return re.findall(r'\d{4}', poet_age_str)
    return None


def find_poet_page(poet):
    """
    Returns the soup of the poet if it was found
    """
    url = POET_URL % poet
    return poem_page_from(url)


def poem_page_from(url):
    print("opening " + url)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': "Google Chrome"})
        page = urllib.request.urlopen(req)
        soup = BeautifulSoup(page.read(), "html.parser")

        print("opened " + url)
        return soup
    except urllib.error.HTTPError as err:
        print("Page not found, error " + str(err))
    except urllib.error.URLError as err:
        print("Page not found, error " + str(err))
    return None


def find_poem_links(soup):
    """
    Finds all links to poems in soup and returns them
    """
    poems = soup.find_all('a', href=re.compile('.*/poems/[0-9]+/.*'))
    poems2 = soup.find_all('a', href=re.compile('.*/poem/.*'))
    poems.extend(poems2)
    return poems


def find_poem_year(source):
    """
    Returns the year of the poem if found in source or None
    """
    match = re.search(r'\(\d{4}\)', source)
    if match:
        return match.group(0)
    return None


def find_poem_lines(soup):
    """
    Returns the lines of the poem as parsed from soup
    """
    poemContent = soup.find('div', {'class': 'o-poem'})
    poemLines = poemContent.findAll('div', recursive=False)

    lines = []
    for line in poemLines:
        text = unescape_text(line.text, left=True)
        cut = re.split(r'\n\r? ?', text)
        lines = lines + cut
    return lines


def find_span_beginning_remove(soup, span_class, pattern):
    """
    Given a soup a span_class and a patter, finds all examples of span_class that
    contain pattern and returns them with pattern omitted
    """
    result = find_span_element(soup, span_class, pattern)
    if result:
        result = result[len(pattern):].strip()
        return result
    return None


def find_span_element(soup, span_class, pattern):
    """
    Given a soup a span_class and a patter, finds all examples of span_class that
    contain pattern and returns them
    """
    spans = soup.find_all('span', {'class': span_class})
    for span in spans:
        text = unescape_text(span.text, left=True, right=True)
        if re.search(pattern, text, re.I | re.U):
            return text
    return None


def unescape_text(text, left=False, right=False):
    """
    Unescapes the html text and removes trailing whitespace if right and leading if left
    Returns unescaped text
    """
    text = unescape(text.replace(u'\xa0', u' '))
    if left:
        text = text.lstrip(WHITESPACE)
    if right:
        text = text.rstrip(WHITESPACE)
    return text


### Begin sql functions

def create_tables(cursor):
    """
    Sets up the tables on cursor if they don't already exist
    """
    cursor.execute(CREATE_POETS)
    cursor.execute(CREATE_POEMS)
    cursor.execute(CREATE_LINES)
    cursor.execute(CREATE_TAGS)


def drop_tables(cursor):
    for table in ['POETS', 'POEMS', 'LINES', 'TAGS']:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')


def write_poem(poem, poet_id, cursor, tag_csv=None):
    """
    Writes poem to cursor
    """
    res = poem_exists(poem.title, poet_id, cursor)
    if res:
        print("poem already exists")
        return

    poem_id = create_poem(poem, poet_id, cursor)
    for lid in range(len(poem.lines)):
        line = poem.lines[lid]
        add_line(lid, poem_id, line, cursor)

    if tag_csv:
        tags = filter(None, [f'"{x.strip()}"' for x in tag_csv.split(',')])
        for name in tags:
            add_tag(poem_id, name, cursor)


def poet_exists(poet_name, cursor):
    """
    Returns true if poet_name exists in cursor
    """
    return cursor.execute(SELECT_POET_EXISTS, (poet_name,)).fetchall()


def create_poet(poet_name, years, cursor):
    """
    Creates poet_name with years in cursor if not exists
    """
    if not poet_exists(poet_name, cursor):
        if years:
            born = years[0]
            if len(years) > 1:
                died = years[1]
                cursor.execute(INSERT_POET_DEAD, (poet_name, born, died))
            else:
                cursor.execute(INSERT_POET_ALIVE, (poet_name, born))
        else:
            cursor.execute(INSERT_POET, (poet_name,))
    return cursor.execute(SELECT_POET_ID, (poet_name,)).fetchone()[0]


def create_poem(poem, poet_id, cursor):
    """
    Creates an entry for poem of poet_id in cursor
    """
    query_names = ""
    query_values = ""
    num_lines = len(poem.lines)
    params = (poem.title, poet_id, num_lines)

    # TODO: this can be factored out
    if poem.url:
        query_names = query_names + ", url"
        query_values = query_values + ", ?"
        params = params + (poem.url,)
    if poem.source:
        query_names = query_names + ", source"
        query_values = query_values + ", ?"
        params = params + (poem.source,)
    if poem.year:
        query_names = query_names + ", year"
        query_values = query_values + ", ?"
        params = params + (poem.year,)
    if poem.translator:
        query_names = query_names + ", translator"
        query_values = query_values + ", ?"
        params = params + (poem.translator,)

    query = INSERT_POEM % (query_names, query_values)
    cursor.execute(query, params)

    return cursor.execute(SELECT_POEM_ID, (poem.title, poet_id)).fetchone()[0]


def poem_exists(poem_name, poet_id, cursor):
    """
    Returns True if poem_name and poet_id exist in cursor
    """
    return cursor.execute(SELECT_POEM_EXISTS, (poem_name, poet_id)).fetchall()


def add_line(lid, poem_id, line, cursor):
    """
    Adds line with id lid pid and value line to cursor
    """
    cursor.execute(INSERT_LINE, (lid, poem_id, line))


def add_tag(poem_id, tag_name, cursor):
    """
    Adds tag to a poem
    """
    cursor.execute(INSERT_TAG, (poem_id, tag_name))


def _debug_single(url):
    soup = soup_for(url)
    poem = find_poem(soup, url)
    if poem:
        print(poem.full_text())


if __name__ == '__main__':
    # _debug_single('https://www.poetryfoundation.org/poetrymagazine/poems/56625/visitors-from-abroad')
    main()
