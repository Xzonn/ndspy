import ndspy.lz11
import pytest


@pytest.mark.parametrize(
  "data",
  [
    b"",
    b"a",
    b"abcdefgh",
    b"abcabcabcabcabcabc",
    bytes(range(256)) * 4,
  ],
)
def test_round_trip(data):
  assert ndspy.lz11.decompress(ndspy.lz11.compress(data)) == data


def test_decompress_medium_length():
  compressed = bytes.fromhex("11 23 00 00 40 41 01 10 00")
  assert ndspy.lz11.decompress(compressed) == b"A" * 0x23


def test_decompress_long_length():
  compressed = bytes.fromhex("11 20 02 00 40 41 10 10 E0 00")
  assert ndspy.lz11.decompress(compressed) == b"A" * 0x220


def test_invalid_type():
  with pytest.raises(TypeError):
    ndspy.lz11.decompress(b"\x10\0\0\0")


def test_truncated_data():
  with pytest.raises(ValueError):
    ndspy.lz11.decompress(b"\x11\x01\0\0\0")
