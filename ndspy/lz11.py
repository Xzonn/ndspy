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
Support for LZ11 compression.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import struct
from collections.abc import Sequence

from . import _lzCommon


def decompress(data: bytes) -> bytes:
  """
  Decompress LZ11-compressed data.
  """
  if not data or data[0] != 0x11:
    raise TypeError("This isn't a LZ11-compressed file.")
  if len(data) < 4:
    raise ValueError("The LZ11 header is incomplete.")

  dataLen = int.from_bytes(data[1:4], "little")
  inPos = 4
  if dataLen == 0:
    if len(data) < 8:
      raise ValueError("The extended LZ11 header is incomplete.")
    (dataLen,) = struct.unpack_from("<I", data, 4)
    inPos = 8

  out = bytearray(dataLen)
  outPos = 0

  while outPos < dataLen:
    if inPos >= len(data):
      raise ValueError("The LZ11 data ended before decompression completed.")
    flags = data[inPos]
    inPos += 1

    for i in range(8):
      if outPos >= dataLen:
        return bytes(out)

      if flags & (0x80 >> i):
        if inPos >= len(data):
          raise ValueError("The LZ11 back-reference is incomplete.")
        first = data[inPos]
        inPos += 1
        lengthType = first >> 4

        if lengthType == 0:
          if inPos + 2 > len(data):
            raise ValueError("The LZ11 back-reference is incomplete.")
          second, third = data[inPos : inPos + 2]
          inPos += 2
          length = (((first & 0xF) << 4) | (second >> 4)) + 0x11
          displacement = ((second & 0xF) << 8) | third
        elif lengthType == 1:
          if inPos + 3 > len(data):
            raise ValueError("The LZ11 back-reference is incomplete.")
          second, third, fourth = data[inPos : inPos + 3]
          inPos += 3
          length = (((first & 0xF) << 12) | (second << 4) | (third >> 4)) + 0x111
          displacement = ((third & 0xF) << 8) | fourth
        else:
          if inPos >= len(data):
            raise ValueError("The LZ11 back-reference is incomplete.")
          second = data[inPos]
          inPos += 1
          length = lengthType + 1
          displacement = ((first & 0xF) << 8) | second

        windowPos = outPos - displacement - 1
        if windowPos < 0:
          raise ValueError("The LZ11 back-reference is out of range.")
        for _ in range(length):
          if outPos >= dataLen:
            return bytes(out)
          out[outPos] = out[windowPos]
          outPos += 1
          windowPos += 1
      else:
        if inPos >= len(data):
          raise ValueError("The LZ11 literal is incomplete.")
        out[outPos] = data[inPos]
        outPos += 1
        inPos += 1

  return bytes(out)


def decompressFromFile(filePath: str | os.PathLike[str]) -> bytes:
  """
  Load an LZ11-compressed filesystem file, and decompress it.
  """
  with open(filePath, "rb") as f:
    return decompress(f.read())


def decompressToFile(data: bytes, filePath: str | os.PathLike[str]) -> None:
  """
  Decompress LZ11-compressed data, and save it to a filesystem file.
  """
  d = decompress(data)
  with open(filePath, "wb") as f:
    f.write(d)


def compress(data: bytes) -> bytes:
  """
  Compress data in LZ11 format.
  """
  if len(data) > 0xFFFFFFFF:
    raise ValueError("LZ11 cannot store more than 0xFFFFFFFF bytes.")

  compressed, _, _ = _lzCommon.compress(data, 1, 0x1000, 16, True, False)
  compressed = bytearray(compressed)

  current = 0
  while current < len(compressed):
    flags = compressed[current]
    current += 1
    for i in range(8):
      if current >= len(compressed):
        break
      if flags & (0x80 >> i):
        length = (compressed[current] >> 4) + 3
        compressed[current] = ((length - 1) << 4) | (compressed[current] & 0xF)
        current += 2
      else:
        current += 1

  if 0 < len(data) < 0x1000000:
    header = b"\x11" + len(data).to_bytes(3, "little")
  else:
    header = b"\x11\0\0\0" + struct.pack("<I", len(data))
  compressed[:0] = header
  return bytes(compressed)


def compressFromFile(filePath: str | os.PathLike[str]) -> bytes:
  """
  Load a filesystem file, and compress its data in LZ11 format.
  """
  with open(filePath, "rb") as f:
    return compress(f.read())


def compressToFile(data: bytes, filePath: str | os.PathLike[str]) -> None:
  """
  Compress data in LZ11 format, and save it to a filesystem file.
  """
  d = compress(data)
  with open(filePath, "wb") as f:
    f.write(d)


def main(args: Sequence[str] | None = None) -> None:
  """
  Main function for the CLI.
  """
  parser = argparse.ArgumentParser(
    description="ndspy.lz11 CLI: Compress or decompress files using LZ11."
  )
  subparsers = parser.add_subparsers(
    title="commands", description="(run a command with -h for additional help)"
  )

  def handleCompress(pArgs):
    with open(str(pArgs.input_file), "rb") as f:
      data = f.read()

    outfp = pArgs.output_file
    if outfp is None:
      outfp = pArgs.input_file.with_suffix(".cmp")

    compressToFile(data, outfp)

  parser_compress = subparsers.add_parser(
    "compress", aliases=["c"], help="compress a file"
  )
  parser_compress.add_argument(
    "input_file", type=pathlib.Path, help="input file to compress"
  )
  parser_compress.add_argument(
    "output_file",
    nargs="?",
    type=pathlib.Path,
    help="what to save the compressed file as",
  )
  parser_compress.set_defaults(func=handleCompress)

  def handleDecompress(pArgs):
    data = decompressFromFile(pArgs.input_file)

    outfp = pArgs.output_file
    if outfp is None:
      outfp = pArgs.input_file.with_suffix(".dec")

    with open(str(outfp), "wb") as f:
      f.write(data)

  parser_decompress = subparsers.add_parser(
    "decompress", aliases=["d"], help="decompress a file"
  )
  parser_decompress.add_argument(
    "input_file", type=pathlib.Path, help="input file to decompress"
  )
  parser_decompress.add_argument(
    "output_file",
    nargs="?",
    type=pathlib.Path,
    help="what to save the decompressed file as",
  )
  parser_decompress.set_defaults(func=handleDecompress)

  pArgs = parser.parse_args(args)
  if hasattr(pArgs, "func"):
    pArgs.func(pArgs)
  else:
    parser.print_usage()


if __name__ == "__main__":
  main()
