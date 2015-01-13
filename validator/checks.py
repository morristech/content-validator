import requests
import re
import difflib
import hoep
from bs4 import BeautifulSoup, element
from collections import defaultdict
from html2text import html2text

from .reports import ContentError, UrlError, ComparisonError, MarkdownError
from .fs import Filetype, read_content
from .parsers import create_parser


class ContentCheck(object):

    def _check_content(self, content):
        pass

    def check(self, paths, parser):
        errors = {}
        for path in paths:
            content = parser.parse(read_content(path))
            error = self._check_content(content)
            if error:
                errors[path] = ContentError(path, error)
        return errors


class ComparisonCheck(object):

    def _compare(self, base, other):
        pass

    def check(self, paths, parser):
        if not paths:
            return {}

        errors = {}
        base_path = paths.pop(0)
        base = parser.parse(read_content(base_path))
        for other_path in paths:
            try:
                other = parser.parse(read_content(other_path))
            except FileNotFoundError:
                other = ''
            error = self._compare(base, other)
            if error:
                errors[other_path] = ComparisonError(base_path, other_path, error)
        return errors


class TxtUrlCheck(ContentCheck):
    retry_max_count = 3
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

    def _make_request(self, url):
        try:
            return requests.get(url).status_code
        except Exception:
            logging.exception('Error making request to %s', url)
            return 500

    def _retry_request(self, url, status):
        new_status = status
        times = 1
        while times < self.retry_max_count and status == new_status:
            new_status = self._make_request(url)
            times = times + 1
        return new_status

    def _request_status_code(self, url):
        status = self._make_request(url)
        if status == 500:
            return self._retry_request(url, status)
        return status

    def _is_valid(self, status_code):
        return 200 <= status_code < 300

    def _extract_urls(self, content):
        return set(match.group().strip(')').strip('.') for match in re.finditer(self.url_pattern, content))

    def _check_content(self, content):
        error_messages = []
        urls = self._extract_urls(content)
        for url in urls:
            status_code = self._request_status_code(url)
            if not self._is_valid(status_code):
                error_messages.append('{} returned status code {}'.format(url, status_code))
        if error_messages:
            return UrlError(error_messages)
        else:
            return None


class HtmlUrlCheck(TxtUrlCheck):

    def _extract_urls(self, content):
        soup = BeautifulSoup(content)
        return set([url.get('href') or url.text for url in soup.find_all('a')])


class ReplaceTextContentRenderer(hoep.Hoep):
    _placeholder_pattern = '[placeholder{}]'

    def __init__(self, extensions=0, render_flags=0):
        super(ReplaceTextContentRenderer, self).__init__(extensions, render_flags)
        self._counter = 1
        self._links = 1
        self.mapping = {}

    # def _link(self, link, title, content):
    #     key = self.link_pattern.format(self.links)
    #     self.links += 1
    #     self.mapping[key] = content
    #     return key

    def normal_text(self, text):
        if not text.strip():
            return text
        key = self._placeholder_pattern.format(self._counter)
        self._counter += 1
        self.mapping[key] = text
        return key


class MarkdownComparator(ComparisonCheck):

    def _diff(self, base, other, base_mapping, other_mapping):
        diff = difflib.HtmlDiff(tabsize=4).make_table(base.splitlines(), other.splitlines())
        diff_soup = BeautifulSoup(diff, 'html.parser')

        changes = diff_soup.find_all('span', 'diff_chg')
        for change in changes:
            change.replace_with(change.get_text())

        diff_rows = diff_soup.find_all('tr')
        for row in diff_rows:
            cells = row.find_all('td')
            base_cell = str(cells[2])
            other_cell = str(cells[5])
            for k, v in base_mapping.items():
                base_cell = base_cell.replace(k, v, 1)
            for k, v in other_mapping.items():
                other_cell = other_cell.replace(k, v, 1)
            cells[2].replace_with(BeautifulSoup(base_cell))
            cells[5].replace_with(BeautifulSoup(other_cell))
        return str(diff_soup)

    def _parse(self, content):
        renderer = ReplaceTextContentRenderer()
        content_html = renderer.render(content)
        parsed_content = html2text(content_html).strip()
        parsed_content = re.sub(r'\([^\)]*\)', '()', parsed_content)
        return parsed_content, renderer.mapping

    def _compare(self, base, other):
        base_parsed, base_mapping = self._parse(base)
        other_parsed, other_mapping = self._parse(other)
        diff = self._diff(base_parsed, other_parsed, base_mapping, other_mapping)

        if base_parsed != other_parsed:
            return MarkdownError(hoep.render(base, render_flags=hoep.HTML_SKIP_HTML), hoep.render(other, render_flags=hoep.HTML_SKIP_HTML), diff)
        else:
            return None


def urls_txt():
    return TxtUrlCheck()


def urls_html():
    return HtmlUrlCheck()


def markdown():
    return MarkdownComparator()
