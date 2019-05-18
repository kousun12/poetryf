"""
A generic poem class
"""

class Poem(object):
    """
    A generic poem class
    """

    def __init__(self, title, lines=None, author=None, url=None, year=None,
                 translator=None, source=None, text=None):
        if lines is None:
            lines = []
        self.title = title
        self.author = author
        self.lines = lines
        self.url = url
        self.year = year
        self.translator = translator
        self.source = source
        self.text = text

    def full_text(self):
        return self.text or self.lines.join("\n")
