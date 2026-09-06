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
Support for NFTR fonts.
"""

from __future__ import annotations

import os
import struct
from typing import TYPE_CHECKING

from . import _common

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Literal


class Glyph:
    """
    A single bitmap glyph from an NFTR CGLP block.

    Pixel values range from zero through ``(1 << bpp) - 1`` and are stored
    from left to right, top to bottom. NFTR stores the values most-significant
    bit first.
    """

    width: int
    height: int
    bpp: int
    data: bytes

    def __init__(self, width: int, height: int, bpp: int, data: bytes):
        if width <= 0 or height <= 0:
            raise ValueError('Glyph dimensions must be positive')
        if bpp not in (1, 2, 3, 4):
            raise ValueError(f'Unsupported NFTR glyph bit depth: {bpp}')

        minimumLength = (width * height * bpp + 7) // 8
        if len(data) < minimumLength:
            raise ValueError(
                f'NFTR glyph data is {len(data)} bytes long, but at least '
                f'{minimumLength} bytes are required')

        self.width = width
        self.height = height
        self.bpp = bpp
        self.data = bytes(data)


    def getPixels(self) -> list[int]:
        """
        Decode this glyph into row-major integer pixel values.
        """
        mask = (1 << self.bpp) - 1
        pixels = []
        bitBuffer = 0
        bitsAvailable = 0

        for byte in self.data:
            bitBuffer = (bitBuffer << 8) | byte
            bitsAvailable += 8
            while bitsAvailable >= self.bpp and len(pixels) < self.width * self.height:
                bitsAvailable -= self.bpp
                pixels.append((bitBuffer >> bitsAvailable) & mask)
                bitBuffer &= (1 << bitsAvailable) - 1

            if len(pixels) == self.width * self.height:
                break

        return pixels


    def setPixels(self, pixels: Iterable[int]) -> None:
        """
        Replace this glyph's bitmap using row-major integer pixel values.
        """
        pixels = list(pixels)
        expectedCount = self.width * self.height
        if len(pixels) != expectedCount:
            raise ValueError(
                f'Expected {expectedCount} NFTR glyph pixels, got {len(pixels)}')

        mask = (1 << self.bpp) - 1
        output = bytearray()
        bitBuffer = 0
        bitsUsed = 0
        for pixel in pixels:
            if not isinstance(pixel, int) or not 0 <= pixel <= mask:
                raise ValueError(
                    f'NFTR {self.bpp}-bpp pixel values must be integers from '
                    f'0 through {mask}, got {pixel!r}')
            bitBuffer = (bitBuffer << self.bpp) | pixel
            bitsUsed += self.bpp
            while bitsUsed >= 8:
                bitsUsed -= 8
                output.append((bitBuffer >> bitsUsed) & 0xFF)
                bitBuffer &= (1 << bitsUsed) - 1

        if bitsUsed:
            output.append((bitBuffer << (8 - bitsUsed)) & 0xFF)

        # Some fonts use a cell length larger than the packed bitmap. Keep
        # any per-glyph trailing bytes rather than silently changing them.
        output.extend(self.data[len(output):])
        self.data = bytes(output)


    def renderAsImage(self):
        """
        Render this glyph as an 8-bit grayscale Pillow image.

        Zero is white and the maximum pixel value is black. Pillow is an
        optional dependency and is required only when this method is called.
        """
        _common.ensurePIL()
        import PIL.Image

        mask = (1 << self.bpp) - 1
        grayscale = bytes(255 - pixel * 255 // mask for pixel in self.getPixels())
        return PIL.Image.frombytes('L', (self.width, self.height), grayscale)


    def setImage(self, image) -> None:
        """
        Quantize a Pillow image and use it as this glyph's bitmap.
        """
        _common.ensurePIL()
        if image.size != (self.width, self.height):
            raise ValueError(
                f'NFTR glyph image should be {self.width} by {self.height} '
                f'pixels, not {image.size[0]} by {image.size[1]}')

        image = image.convert('L')
        mask = (1 << self.bpp) - 1
        self.setPixels(round((255 - value) * mask / 255) for value in image.getdata())


    def __repr__(self) -> str:
        return (f'{type(self).__name__}({self.width!r}, {self.height!r}, '
                f'{self.bpp!r}, {_common.shortBytesRepr(self.data)})')


class CharacterWidth:
    """
    The left bearing, bitmap width, and advance width of one glyph.
    """

    left: int
    glyphWidth: int
    charWidth: int

    def __init__(self, left: int = 0, glyphWidth: int = 0, charWidth: int = 0):
        self.left = left
        self.glyphWidth = glyphWidth
        self.charWidth = charWidth


    def __repr__(self) -> str:
        return (f'{type(self).__name__}({self.left!r}, '
                f'{self.glyphWidth!r}, {self.charWidth!r})')


class WidthBlock:
    """
    A CWDH block containing metrics for a consecutive range of glyphs.
    """

    firstGlyphIndex: int
    widths: list[CharacterWidth]

    def __init__(
        self,
        firstGlyphIndex: int = 0,
        widths: Iterable[CharacterWidth] | None = None,
    ):
        self.firstGlyphIndex = firstGlyphIndex
        self.widths = [] if widths is None else list(widths)


    @property
    def lastGlyphIndex(self) -> int:
        return self.firstGlyphIndex + len(self.widths) - 1


    def __repr__(self) -> str:
        return (f'{type(self).__name__}({self.firstGlyphIndex!r}, '
                f'{self.widths!r})')


class MappingBlock:
    """
    A CMAP block mapping character codes to glyph indices.

    ``type`` is 0 for a consecutive mapping, 1 for a full table, and 2 for
    explicit character/glyph pairs.
    """

    firstCharacterCode: int
    lastCharacterCode: int
    type: int
    unknown: int
    characterToGlyph: dict[int, int]

    def __init__(
        self,
        firstCharacterCode: int = 0,
        lastCharacterCode: int = 0,
        type: int = 2,
        characterToGlyph: dict[int, int] | None = None,
        *,
        unknown: int = 0,
    ):
        if type not in (0, 1, 2):
            raise ValueError(f'Unsupported NFTR CMAP type: {type}')
        self.firstCharacterCode = firstCharacterCode
        self.lastCharacterCode = lastCharacterCode
        self.type = type
        self.unknown = unknown
        self.characterToGlyph = {} if characterToGlyph is None else dict(characterToGlyph)


    def __repr__(self) -> str:
        return (f'{type(self).__name__}({self.firstCharacterCode!r}, '
                f'{self.lastCharacterCode!r}, {self.type!r}, '
                f'{self.characterToGlyph!r}, unknown={self.unknown!r})')


def _readBlockHeader(
    data: bytes,
    offset: int,
    endianness: Literal['<', '>'],
    magic: bytes,
    reversedMagic: bool,
) -> tuple[int, int]:
    if offset < 0 or offset + 8 > len(data):
        raise ValueError(f'NFTR block offset {offset:#x} is out of range')
    actualMagic, size = struct.unpack_from(endianness + '4sI', data, offset)
    expectedMagic = magic[::-1] if reversedMagic else magic
    if actualMagic != expectedMagic:
        raise ValueError(
            f'Expected NFTR block {expectedMagic!r} at {offset:#x}, '
            f'found {actualMagic!r}')
    if size < 8 or offset + size > len(data):
        raise ValueError(
            f'NFTR block at {offset:#x} has invalid size {size:#x}')
    return size, offset + size


class NFTR:
    """
    A Nintendo DS NFTR bitmap font.
    """

    version: int
    endianness: Literal['<', '>']
    reversedMagic: bool

    fontType: int
    lineFeed: int
    alterCharIndex: int
    defaultWidth: CharacterWidth
    encoding: int
    fontHeight: int | None
    fontWidth: int | None
    bearingY: int | None
    bearingX: int | None

    glyphWidth: int
    glyphHeight: int
    glyphDataLength: int
    cglpUnknown: int
    bpp: int
    rotation: int
    glyphs: list[Glyph]
    widthBlocks: list[WidthBlock]
    mappingBlocks: list[MappingBlock]

    def __init__(self, data: bytes | None = None):
        self.version = 0x0102
        self.endianness = '<'
        self.reversedMagic = True

        self.fontType = 0
        self.lineFeed = 0
        self.alterCharIndex = 0
        self.defaultWidth = CharacterWidth()
        self.encoding = 0
        self.fontHeight = None
        self.fontWidth = None
        self.bearingY = None
        self.bearingX = None

        self.glyphWidth = 8
        self.glyphHeight = 8
        self.glyphDataLength = 8
        self.cglpUnknown = 0
        self.bpp = 1
        self.rotation = 0
        self.glyphs = []
        self.widthBlocks = []
        self.mappingBlocks = []

        if data is not None:
            self._initFromData(data)


    def _initFromData(self, data: bytes) -> None:
        if len(data) < 0x10:
            raise ValueError('NFTR data is too short for a file header')

        magic = data[:4]
        if magic == b'RTFN':
            self.reversedMagic = True
        elif magic == b'NFTR':
            self.reversedMagic = False
        else:
            raise ValueError(f'Not an NFTR file (magic is {magic!r})')

        bomBytes = data[4:6]
        if bomBytes == b'\xFF\xFE':
            self.endianness = '<'
        elif bomBytes == b'\xFE\xFF':
            self.endianness = '>'
        else:
            raise ValueError(f'Unknown NFTR byte-order mark: {bomBytes.hex()}')
        se = self.endianness

        _, bom, self.version, fileSize, headerSize, blockCount = \
            struct.unpack_from(se + '4sHHIHH', data, 0)
        if bom != 0xFEFF:
            raise ValueError(f'Invalid NFTR byte-order mark value: {bom:#x}')
        if headerSize != 0x10:
            raise ValueError(f'Unsupported NFTR header size: {headerSize:#x}')
        if fileSize != len(data):
            raise ValueError(
                f'NFTR header declares {fileSize} bytes, but input has '
                f'{len(data)} bytes')

        finfSize, _ = _readBlockHeader(
            data, headerSize, se, b'FINF', self.reversedMagic)
        if finfSize not in (0x1C, 0x20):
            raise ValueError(f'Unsupported NFTR FINF size: {finfSize:#x}')

        (
            self.fontType,
            self.lineFeed,
            self.alterCharIndex,
            defaultLeft,
            defaultGlyphWidth,
            defaultCharWidth,
            self.encoding,
            cglpDataOffset,
            cwdhDataOffset,
            cmapDataOffset,
        ) = struct.unpack_from(se + 'BBHbBBBIII', data, headerSize + 8)
        self.defaultWidth = CharacterWidth(
            defaultLeft, defaultGlyphWidth, defaultCharWidth)

        if finfSize == 0x20:
            (
                self.fontHeight,
                self.fontWidth,
                self.bearingY,
                self.bearingX,
            ) = struct.unpack_from('4B', data, headerSize + 0x1C)
        else:
            self.fontHeight = None
            self.fontWidth = None
            self.bearingY = None
            self.bearingX = None

        cglpOffset = cglpDataOffset - 8
        cglpSize, _ = _readBlockHeader(
            data, cglpOffset, se, b'CGLP', self.reversedMagic)
        (
            self.glyphWidth,
            self.glyphHeight,
            self.glyphDataLength,
            self.cglpUnknown,
            self.bpp,
            self.rotation,
        ) = struct.unpack_from(se + 'BBHHBB', data, cglpOffset + 8)

        if self.bpp not in (1, 2, 3, 4):
            raise ValueError(f'Unsupported NFTR glyph bit depth: {self.bpp}')
        minimumGlyphLength = (
            self.glyphWidth * self.glyphHeight * self.bpp + 7) // 8
        if self.glyphDataLength < minimumGlyphLength:
            raise ValueError(
                f'NFTR CGLP cell length {self.glyphDataLength} is too small '
                f'for {self.glyphWidth}x{self.glyphHeight} '
                f'{self.bpp}-bpp glyphs')
        if self.glyphDataLength == 0:
            raise ValueError('NFTR CGLP cell length cannot be zero')

        glyphData = data[cglpOffset + 0x10:cglpOffset + cglpSize]
        glyphCount, trailingLength = divmod(len(glyphData), self.glyphDataLength)
        if trailingLength > 3 or (
                trailingLength and any(glyphData[-trailingLength:])):
            raise ValueError('NFTR CGLP data has invalid trailing bytes')
        self.glyphs = []
        for index in range(glyphCount):
            start = index * self.glyphDataLength
            self.glyphs.append(Glyph(
                self.glyphWidth,
                self.glyphHeight,
                self.bpp,
                glyphData[start:start + self.glyphDataLength],
            ))

        self.widthBlocks = []
        seenOffsets = set()
        nextDataOffset = cwdhDataOffset
        while nextDataOffset:
            if nextDataOffset in seenOffsets:
                raise ValueError('Cycle found in NFTR CWDH block chain')
            seenOffsets.add(nextDataOffset)
            offset = nextDataOffset - 8
            size, _ = _readBlockHeader(
                data, offset, se, b'CWDH', self.reversedMagic)
            firstIndex, lastIndex, nextDataOffset = struct.unpack_from(
                se + 'HHI', data, offset + 8)
            if lastIndex < firstIndex:
                raise ValueError('NFTR CWDH glyph range is reversed')
            count = lastIndex - firstIndex + 1
            if 0x10 + count * 3 > size:
                raise ValueError('NFTR CWDH block is too short for its glyph range')
            widths = []
            for index in range(count):
                left, glyphWidth, charWidth = struct.unpack_from(
                    se + 'bBB', data, offset + 0x10 + index * 3)
                widths.append(CharacterWidth(left, glyphWidth, charWidth))
            padding = data[offset + 0x10 + count * 3:offset + size]
            if len(padding) > 3 or any(padding):
                raise ValueError('NFTR CWDH block has invalid trailing bytes')
            self.widthBlocks.append(WidthBlock(firstIndex, widths))

        self.mappingBlocks = []
        seenOffsets.clear()
        nextDataOffset = cmapDataOffset
        while nextDataOffset:
            if nextDataOffset in seenOffsets:
                raise ValueError('Cycle found in NFTR CMAP block chain')
            seenOffsets.add(nextDataOffset)
            offset = nextDataOffset - 8
            size, _ = _readBlockHeader(
                data, offset, se, b'CMAP', self.reversedMagic)
            firstCode, lastCode, mappingType, unknown, nextDataOffset = \
                struct.unpack_from(se + 'HHHHI', data, offset + 8)
            mapping = {}
            bodyOffset = offset + 0x14

            if mappingType == 0:
                if bodyOffset + 2 > offset + size:
                    raise ValueError('NFTR type-0 CMAP block is truncated')
                firstGlyph, = struct.unpack_from(se + 'H', data, bodyOffset)
                for characterCode in range(firstCode, lastCode + 1):
                    mapping[characterCode] = firstGlyph + characterCode - firstCode
                usedLength = 2
            elif mappingType == 1:
                count = lastCode - firstCode + 1
                if bodyOffset + count * 2 > offset + size:
                    raise ValueError('NFTR type-1 CMAP block is truncated')
                for index in range(count):
                    glyphIndex, = struct.unpack_from(
                        se + 'H', data, bodyOffset + index * 2)
                    if glyphIndex != 0xFFFF:
                        mapping[firstCode + index] = glyphIndex
                usedLength = count * 2
            elif mappingType == 2:
                if bodyOffset + 2 > offset + size:
                    raise ValueError('NFTR type-2 CMAP block is truncated')
                count, = struct.unpack_from(se + 'H', data, bodyOffset)
                if bodyOffset + 2 + count * 4 > offset + size:
                    raise ValueError('NFTR type-2 CMAP block is truncated')
                for index in range(count):
                    characterCode, glyphIndex = struct.unpack_from(
                        se + 'HH', data, bodyOffset + 2 + index * 4)
                    if characterCode in mapping:
                        raise ValueError(
                            f'Duplicate character code {characterCode:#x} '
                            f'in NFTR type-2 CMAP block')
                    mapping[characterCode] = glyphIndex
                usedLength = 2 + count * 4
            else:
                raise ValueError(f'Unsupported NFTR CMAP type: {mappingType}')

            padding = data[bodyOffset + usedLength:offset + size]
            if len(padding) > 3 or any(padding):
                raise ValueError('NFTR CMAP block has invalid trailing bytes')
            self.mappingBlocks.append(MappingBlock(
                firstCode,
                lastCode,
                mappingType,
                mapping,
                unknown=unknown,
            ))

        expectedBlockCount = 2 + len(self.widthBlocks) + len(self.mappingBlocks)
        if blockCount != expectedBlockCount:
            raise ValueError(
                f'NFTR header declares {blockCount} blocks, but '
                f'{expectedBlockCount} linked blocks were found')

        # The CGLP block has no explicit glyph count. Its block size is
        # four-byte aligned, so for short cells the alignment bytes can look
        # like complete extra glyphs. CWDH is the authoritative glyph range
        # when present and lets us distinguish those bytes from real cells.
        if self.widthBlocks:
            declaredGlyphCount = max(
                block.lastGlyphIndex for block in self.widthBlocks) + 1
            glyphBytesLength = declaredGlyphCount * self.glyphDataLength
            if glyphBytesLength > len(glyphData):
                raise ValueError(
                    'NFTR CWDH tables reference more glyphs than CGLP contains')
            padding = glyphData[glyphBytesLength:]
            if len(padding) > 3 or any(padding):
                raise ValueError(
                    'NFTR CGLP size does not match the CWDH glyph ranges')
            self.glyphs = self.glyphs[:declaredGlyphCount]

        glyphCount = len(self.glyphs)
        for block in self.mappingBlocks:
            for characterCode, glyphIndex in block.characterToGlyph.items():
                if glyphIndex >= glyphCount:
                    raise ValueError(
                        f'NFTR character code {characterCode:#x} maps to '
                        f'out-of-range glyph {glyphIndex}')


    @property
    def characterMap(self) -> dict[int, int]:
        """
        Return all CMAP entries as ``character code -> glyph index``.
        """
        output = {}
        for block in self.mappingBlocks:
            output.update(block.characterToGlyph)
        return output


    @property
    def widths(self) -> dict[int, CharacterWidth]:
        """
        Return all CWDH entries as ``glyph index -> CharacterWidth``.
        """
        output = {}
        for block in self.widthBlocks:
            for index, width in enumerate(block.widths, block.firstGlyphIndex):
                output[index] = width
        return output


    @classmethod
    def fromFile(cls, filePath: str | os.PathLike[str]) -> NFTR:
        """
        Load an NFTR from a filesystem file.
        """
        with open(filePath, 'rb') as f:
            return cls(f.read())


    def _saveCGLP(self) -> bytes:
        se = self.endianness
        magic = b'PLGC' if self.reversedMagic else b'CGLP'
        if self.bpp not in (1, 2, 3, 4):
            raise ValueError(f'Unsupported NFTR glyph bit depth: {self.bpp}')
        minimumLength = self.glyphWidth * self.glyphHeight * self.bpp
        minimumLength = (minimumLength + 7) // 8
        if self.glyphDataLength < minimumLength:
            raise ValueError('NFTR glyph data length is too small')

        data = bytearray(0x10)
        for glyph in self.glyphs:
            if (glyph.width, glyph.height, glyph.bpp) != (
                    self.glyphWidth, self.glyphHeight, self.bpp):
                raise ValueError('NFTR contains inconsistent glyph dimensions or bit depths')
            if len(glyph.data) != self.glyphDataLength:
                raise ValueError('NFTR contains inconsistent glyph data lengths')
            data.extend(glyph.data)
        while len(data) % 4:
            data.append(0)
        struct.pack_into(
            se + '4sIBBHHBB',
            data,
            0,
            magic,
            len(data),
            self.glyphWidth,
            self.glyphHeight,
            self.glyphDataLength,
            self.cglpUnknown,
            self.bpp,
            self.rotation,
        )
        return bytes(data)


    def _saveCWDH(self, block: WidthBlock, nextDataOffset: int) -> bytes:
        if not block.widths:
            raise ValueError('NFTR CWDH blocks cannot be empty')
        se = self.endianness
        magic = b'HDWC' if self.reversedMagic else b'CWDH'
        data = bytearray(0x10)
        for width in block.widths:
            try:
                data.extend(struct.pack(
                    se + 'bBB', width.left, width.glyphWidth, width.charWidth))
            except struct.error as exc:
                raise ValueError(f'Invalid NFTR character width: {width!r}') from exc
        while len(data) % 4:
            data.append(0)
        struct.pack_into(
            se + '4sIHHI',
            data,
            0,
            magic,
            len(data),
            block.firstGlyphIndex,
            block.lastGlyphIndex,
            nextDataOffset,
        )
        return bytes(data)


    def _saveCMAP(self, block: MappingBlock, nextDataOffset: int) -> bytes:
        se = self.endianness
        magic = b'PAMC' if self.reversedMagic else b'CMAP'
        data = bytearray(0x14)

        if block.type == 0:
            count = block.lastCharacterCode - block.firstCharacterCode + 1
            if count <= 0:
                raise ValueError('NFTR type-0 CMAP range is empty')
            try:
                firstGlyph = block.characterToGlyph[block.firstCharacterCode]
            except KeyError as exc:
                raise ValueError('NFTR type-0 CMAP is missing its first entry') from exc
            expected = {
                block.firstCharacterCode + index: firstGlyph + index
                for index in range(count)
            }
            if block.characterToGlyph != expected:
                raise ValueError('NFTR type-0 CMAP entries are not consecutive')
            data.extend(struct.pack(se + 'H', firstGlyph))
        elif block.type == 1:
            count = block.lastCharacterCode - block.firstCharacterCode + 1
            if count <= 0:
                raise ValueError('NFTR type-1 CMAP range is empty')
            if any(not block.firstCharacterCode <= code <= block.lastCharacterCode
                   for code in block.characterToGlyph):
                raise ValueError('NFTR type-1 CMAP contains an out-of-range character')
            for characterCode in range(
                    block.firstCharacterCode, block.lastCharacterCode + 1):
                data.extend(struct.pack(
                    se + 'H', block.characterToGlyph.get(characterCode, 0xFFFF)))
        elif block.type == 2:
            if len(block.characterToGlyph) > 0xFFFF:
                raise ValueError('NFTR type-2 CMAP contains too many entries')
            data.extend(struct.pack(se + 'H', len(block.characterToGlyph)))
            for characterCode, glyphIndex in block.characterToGlyph.items():
                data.extend(struct.pack(se + 'HH', characterCode, glyphIndex))
        else:
            raise ValueError(f'Unsupported NFTR CMAP type: {block.type}')

        while len(data) % 4:
            data.append(0)
        struct.pack_into(
            se + '4sIHHHHI',
            data,
            0,
            magic,
            len(data),
            block.firstCharacterCode,
            block.lastCharacterCode,
            block.type,
            block.unknown,
            nextDataOffset,
        )
        return bytes(data)


    def save(self) -> bytes:
        """
        Generate file data representing this NFTR.
        """
        if self.endianness not in ('<', '>'):
            raise ValueError(f'Invalid NFTR endianness: {self.endianness!r}')
        se = self.endianness

        extendedMetrics = (
            self.fontHeight,
            self.fontWidth,
            self.bearingY,
            self.bearingX,
        )
        if any(value is None for value in extendedMetrics):
            if not all(value is None for value in extendedMetrics):
                raise ValueError('NFTR extended FINF metrics must be all present or all absent')
            finfSize = 0x1C
        else:
            finfSize = 0x20

        cglp = self._saveCGLP()
        cglpOffset = 0x10 + finfSize

        cwdhSizes = []
        for block in self.widthBlocks:
            if not block.widths:
                raise ValueError('NFTR CWDH blocks cannot be empty')
            size = 0x10 + len(block.widths) * 3
            cwdhSizes.append((size + 3) & ~3)
        firstCWDHOffset = cglpOffset + len(cglp)

        cmapSizes = []
        for block in self.mappingBlocks:
            if block.type == 0:
                bodySize = 2
            elif block.type == 1:
                count = block.lastCharacterCode - block.firstCharacterCode + 1
                if count <= 0:
                    raise ValueError('NFTR type-1 CMAP range is empty')
                bodySize = count * 2
            elif block.type == 2:
                bodySize = 2 + len(block.characterToGlyph) * 4
            else:
                raise ValueError(f'Unsupported NFTR CMAP type: {block.type}')
            cmapSizes.append((0x14 + bodySize + 3) & ~3)
        firstCMAPOffset = firstCWDHOffset + sum(cwdhSizes)

        cwdhs = []
        offset = firstCWDHOffset
        for index, block in enumerate(self.widthBlocks):
            nextOffset = offset + cwdhSizes[index]
            if index + 1 == len(self.widthBlocks):
                nextDataOffset = 0
            else:
                nextDataOffset = nextOffset + 8
            cwdhs.append(self._saveCWDH(block, nextDataOffset))
            offset = nextOffset

        cmaps = []
        offset = firstCMAPOffset
        for index, block in enumerate(self.mappingBlocks):
            nextOffset = offset + cmapSizes[index]
            if index + 1 == len(self.mappingBlocks):
                nextDataOffset = 0
            else:
                nextDataOffset = nextOffset + 8
            cmaps.append(self._saveCMAP(block, nextDataOffset))
            offset = nextOffset

        finfMagic = b'FNIF' if self.reversedMagic else b'FINF'
        finf = bytearray(finfSize)
        struct.pack_into(
            se + '4sIBBHbBBBIII',
            finf,
            0,
            finfMagic,
            finfSize,
            self.fontType,
            self.lineFeed,
            self.alterCharIndex,
            self.defaultWidth.left,
            self.defaultWidth.glyphWidth,
            self.defaultWidth.charWidth,
            self.encoding,
            cglpOffset + 8,
            firstCWDHOffset + 8 if self.widthBlocks else 0,
            firstCMAPOffset + 8 if self.mappingBlocks else 0,
        )
        if finfSize == 0x20:
            try:
                struct.pack_into('4B', finf, 0x1C, *extendedMetrics)
            except struct.error as exc:
                raise ValueError('Invalid NFTR extended FINF metrics') from exc

        body = bytes(finf) + cglp + b''.join(cwdhs) + b''.join(cmaps)
        magic = b'RTFN' if self.reversedMagic else b'NFTR'
        blockCount = 2 + len(cwdhs) + len(cmaps)
        header = struct.pack(
            se + '4sHHIHH',
            magic,
            0xFEFF,
            self.version,
            0x10 + len(body),
            0x10,
            blockCount,
        )
        return header + body


    def saveToFile(self, filePath: str | os.PathLike[str]) -> None:
        """
        Generate NFTR data and save it to a filesystem file.
        """
        with open(filePath, 'wb') as f:
            f.write(self.save())


    def __str__(self) -> str:
        return (f'<nftr {self.glyphWidth}x{self.glyphHeight} '
                f'{self.bpp}-bpp ({len(self.glyphs)} glyphs, '
                f'{len(self.characterMap)} characters)>')
