from enum import Enum
from bs4 import BeautifulSoup
from markdown import Markdown
from markdown.inlinepatterns import Pattern
from itertools import zip_longest
import requests
import re
import logging
import difflib
import html2text

from .errors import LinkError, TagsCountError, TagNameError, ContentError, CompareError, MissingFileError, MarkdownCompareElementError, MarkdownExtraElementError, MarkdownCompareError
from .utils import clean_html_tree


class ContentCheck(object):

    def validate(parser, reader, file_path):
        pass


class CompareCheck(object):

    def compare(self, parser, reader, base_file_path, other_file_path):
        pass


class LinkCheck(ContentCheck):
    retry_max_count = 3
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

    def _make_request(self, url):
        try:
            return requests.get(url).status_code
        except Exception as e:
            logging.error(e)
            return 500

    def _retry_request(self, url, status):
        new_status = status
        times = 1
        while times < self.retry_max_count and status == new_status:
            new_status = self._make_request(url)
            times = times + 1
        return new_status

    def _url_status_code(self, url):
        status = self._make_request(url)
        if status == 500:
            return self._retry_request(url, status)
        return status

    def validate(self, parser, reader, file_path):
        content = parser.parse(reader.read(file_path))
        error = ContentError(file_path)
        links = set(match.group().strip(')').strip('.') for match in re.finditer(self.url_pattern, content))
        for link in links:
            status_code = self._url_status_code(link.strip(')'))
            if not (200 <= status_code < 300):
                error.add_error(LinkError(link, status_code))
        return error


class StructureCheck(CompareCheck):

    def _pretty_html(self, parser, reader, file_path, replace_txt=''):
        content = parser.parse(reader.read(file_path))
        soup = BeautifulSoup(content)
        clean_soup = clean_html_tree(soup, replace_txt)
        return clean_soup.prettify()

    def compare(self, parser, reader, base_path, other_path):
        error = CompareError(base_path, other_path)

        base_html = self._pretty_html(parser, reader, base_path, 'placeholder')
        other_html = self._pretty_html(parser, reader, other_path, 'placeholder')
        base_text = html2text.html2text(base_html)
        other_text = html2text.html2text(other_html)

        if base_text != other_text:
            differ = difflib.Differ()
            diff = list(differ.compare(base_text.splitlines(keepends=True), other_text.splitlines(keepends=True)))
            error.add_error(MarkdownCompareError('\n'.join(diff)))

        return error


class RecordItem(object):
    def __init__(self, element, data):
        self.element = element
        self.data = data

    def __str__(self):
        return '{}: {}'.format(self.element, self.data)

    def __repr__(self):
        return '{}: {}'.format(self.element, self.data)

    def __eq__(self, other):
        return self.element == other.element


class RecordPattern(object):
    record = []

    def __init__(self, baseObject):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.__baseObject = baseObject

    def handleMatch(self, m):
        self.record.append(RecordItem(self.__baseObject.__class__.__name__, m.string))
        return self.__baseObject.handleMatch(m)

    def run(self, parent, blocks):
        self.record.append(RecordItem(self.__baseObject.__class__.__name__, blocks[0]))
        return self.__baseObject.run(parent, blocks)


class ReplayPattern(object):
    index = 0

    def __init__(self, baseObject, record, error):
        self.__class__ = type(baseObject.__class__.__name__,
                              (self.__class__, baseObject.__class__),
                              {})
        self.__dict__ = baseObject.__dict__
        self.__baseObject = baseObject
        self.__record = record
        self.__error = error

    def __match_next(self, item):
        if self.index >= len(self.__record):
            self.__error.add_error(MarkdownExtraElementError(item.element, item.data))
        else:
            match = self.__record[self.index]
            ReplayPattern.index = ReplayPattern.index + 1
            if item != match:
                self.__error.add_error(MarkdownCompareElementError(match.element, match.data, item.element, item.data))

    def handleMatch(self, m):
        if self.__match_next(RecordItem(self.__baseObject.__class__.__name__, m.string)):
            self.__error.add_error(MarkdownElementError)
        return self.__baseObject.handleMatch(m)

    def run(self, parent, blocks):
        if self.__match_next(RecordItem(self.__baseObject.__class__.__name__, blocks[0])):
            self.__error.add_error(MarkdownElementError)
        return self.__baseObject.run(parent, blocks)


class MarkdownCheck(CompareCheck):
    def _make_recorder(self):
        markdown = Markdown()
        for inlinePattern in markdown.inlinePatterns:
            markdown.inlinePatterns[inlinePattern] = RecordPattern(markdown.inlinePatterns[inlinePattern])
        for blockProcessors in markdown.parser.blockprocessors:
            markdown.parser.blockprocessors[blockProcessors] = RecordPattern(markdown.parser.blockprocessors[blockProcessors])
        return markdown

    def _make_replay(self, record, error):
        markdown = Markdown()
        for inlinePattern in markdown.inlinePatterns:
            markdown.inlinePatterns[inlinePattern] = ReplayPattern(markdown.inlinePatterns[inlinePattern], record, error)
        for blockProcessors in markdown.parser.blockprocessors:
            markdown.parser.blockprocessors[blockProcessors] = ReplayPattern(markdown.parser.blockprocessors[blockProcessors], record, error)
        return markdown

    def compare(self, parser, reader, base_file_path, other_file_path):
        RecordPattern.record = []
        ReplayPattern.index = 0

        base_content = reader.read(base_file_path)
        other_content = reader.read(other_file_path)
        error = CompareError(base_file_path, other_file_path)

        recorder = self._make_recorder()
        recorder.convert(base_content)

        replay = self._make_replay(RecordPattern.record, error)
        replay.convert(other_content)

        return error


def check_links():
    return LinkCheck()


def check_structure():
    return StructureCheck()


def check_markdown():
    return MarkdownCheck()
