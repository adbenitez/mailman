# Copyright (C) 2016-2022 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# GNU Mailman is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# GNU Mailman.  If not, see <https://www.gnu.org/licenses/>.

"""Test queries."""

import unittest

from mailman.utilities.queries import QuerySequence
from operator import getitem


class TestQueries(unittest.TestCase):

    def test_index_error(self):
        query = QuerySequence(None)
        self.assertRaises(IndexError, getitem, query, 1)

    def test_iterate_with_none(self):
        query = QuerySequence(None)
        self.assertEqual(list(query), [])
