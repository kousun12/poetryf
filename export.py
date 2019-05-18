from __future__ import print_function

import sqlite3
import argparse
from sql_util import DATABASE
from poem import Poem

SELECT_POEMS_BASE = """
SELECT PM.pid,
       PM.poem_name,
       PT.poet_name,
       PM.translator,
       PM.source,
       PM.url,
       group_concat(L.poem_line, char(10)) as text
FROM POEMS AS PM
         JOIN POETS AS PT ON PT.PID = PM.poet_id
         JOIN LINES L ON L.pid = PM.pid
         LEFT OUTER JOIN TAGS T ON T.pid = PM.pid
WHERE PM.pid > 0"""

GRP_PID = """\nGROUP BY PM.pid"""

SELECT_ALL = SELECT_POEMS_BASE + GRP_PID + ";"


def main():
    """
    Main function for running from command line
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", help="parse a collection", action="store_true")
    parser.add_argument("-t", "--tag", type=str, help="tags to search over, comma-separated")
    parser.add_argument("-a", "--author", type=str, help="authors to search over, comma-separated")
    parser.add_argument("-o", "--out", type=str, help="output name", default="output.txt")

    args = parser.parse_args()
    if args.all:
        poems = get_poems()
    else:
        poems = get_poems(args.author, args.tag)

    write_poems(args.out, poems)
    conn = sqlite3.connect(DATABASE, isolation_level=None)  # auto commit
    cursor = conn.cursor()

    cursor.close()


def poems_from(result):
    results = result.fetchall()

    if not results:
        print("query for poem failed")
        return None
    poems = []
    for result in results:
        poem_id, title, author_str, translator, source, url, text = result
        poem = Poem(title=title, author=author_str, text=text, translator=translator, source=source, url=url)
        poems.append(poem)

    print(f'{len(poems)} poems')
    return poems


def get_poems(author_str=None, tag_str=None):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    statement = SELECT_POEMS_BASE

    if author_str:
        authors = filter(None, [f'"{x.strip()}"' for x in author_str.split(',')])
        statement += f"\nAND PT.poet_name IN ({','.join(authors)})"
    if tag_str:
        tags = filter(None, [f'"{x.strip()}"' for x in tag_str.split(',')])
        statement += f"\nAND T.name in ({','.join(tags)})"

    statement += GRP_PID + ";"
    # print(f'QUERY: {statement}')
    result = cursor.execute(statement)

    poems = poems_from(result)
    cursor.close()
    conn.commit()
    return poems


def write_poems(filename, poems):
    f = open(filename, "w")
    f.write('\n\n\n\n\n\n'.join([f'{p.title}\n\n\n\n\n\n{p.full_text()}'for p in poems]))
    f.close()
    print(f'wrote to {filename}')


if __name__ == '__main__':
    main()