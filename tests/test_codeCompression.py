# Copyright 2026 Xzonn
#
# This file is part of ndspy.
#
# ndspy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ndspy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ndspy.  If not, see <https://www.gnu.org/licenses/>.
"""
Unit tests for ndspy.codeCompression.
"""


from ndspy import codeCompression


def test_arm9_round_trip_with_overlapping_matches():
    data = b'\0' * 0x4000 + b'A' * 256
    compressed = codeCompression.compress(data, True)
    assert codeCompression.decompress(compressed) == data
