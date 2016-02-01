from unittest import TestCase
from unittest.mock import patch, MagicMock

from validator.checks import md


def read(path):
    with open(path) as fp:
        return fp.read()


class TestMarkdownComparator(TestCase):
    def setUp(self):
        self.parser = MagicMock()
        self.check = md.MarkdownComparator()

    def _test_markdown(self, path1, path2):
        self.parser.parse.side_effect = iter([read(path1), read(path2)])
        return self.check.check([['dummy_path1', 'dummy_path2']], self.parser)

    def test_markdown_same(self):
        diffs = self._test_markdown('tests/fixtures/lang/en/test1.md', 'tests/fixtures/lang/de/test1.md')
        self.assertEqual([], diffs)

    def test_markdown_different(self):
        diffs = self._test_markdown('tests/fixtures/lang/en/test2.md', 'tests/fixtures/lang/de/test2.md')

        self.assertEqual(1, len(diffs))
        diff = diffs[0]
        self.assertEqual('dummy_path1', diff.base.original)
        self.assertEqual('dummy_path2', diff.other.original)
        self.assertNotEqual([], diff.error_msgs)