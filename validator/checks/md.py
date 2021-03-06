import re
from sdiff import diff, renderer
from markdown import markdown

from ..errors import MdDiff, ContentData

LINK_RE = r'\]\(([^\)]+)\)'


def save_file(content, filename):
    with open(filename, 'w') as fp:
        fp.write(content)


class MarkdownComparator(object):
    def check(self, data, parser, reader):
        if not data:
            return []

        # TODO use yield instead of array
        errors = []
        for row in data:
            base = row.pop(0)
            base_parsed = parser.parse(reader.read(base))
            base_html = markdown(base_parsed)
            for other in row:
                other_parsed = parser.parse(reader.read(other))
                other_html = markdown(other_parsed)
                other_diff, base_diff, error = diff(other_parsed, base_parsed, renderer=renderer.HtmlRenderer())
                if error:
                    error_msgs = []
                    if error:
                        error_msgs = map(lambda e: e.message, error)
                    base_data = ContentData(base, base_parsed, base_diff, base_html)
                    other_data = ContentData(other, other_parsed, other_diff, other_html)
                    errors.append(MdDiff(base_data, other_data, error_msgs))
        return errors

    def get_broken_links(self, base, other):
        base_links = re.findall(LINK_RE, base)
        other_links = re.findall(LINK_RE, other.replace('\u200e', ''))
        broken_links = set(other_links) - set(base_links)
        return broken_links
