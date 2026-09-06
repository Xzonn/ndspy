..
    Copyright 2024-2026 Xzonn

    This file is part of ndspy.

``ndspy.nftr``: NFTR (bitmap fonts)
====================================

.. py:module:: ndspy.nftr

The ``ndspy.nftr`` module loads, edits, and saves Nintendo DS NFTR bitmap fonts. It supports FINF font metadata, CGLP glyph bitmaps, linked CWDH width tables, and all three standard CMAP mapping types.

Examples
--------

Load a font, inspect its mappings, edit a glyph, and save it:

.. code-block:: python

    import ndspy.nftr

    font = ndspy.nftr.NFTR.fromFile('font.nftr')
    glyph_index = font.characterMap[ord('A')]
    glyph = font.glyphs[glyph_index]
    pixels = glyph.getPixels()
    glyph.setPixels(pixels)
    font.saveToFile('font-edited.nftr')

Pillow is optional. If installed, ``Glyph.renderAsImage()`` and ``Glyph.setImage()`` can be used to exchange glyphs with grayscale images.

API
---

.. py:class:: NFTR([data])

    An NFTR bitmap font. Pass file bytes to load an existing font, or use :py:meth:`fromFile`.

    .. py:attribute:: glyphs

        The font's list of :py:class:`Glyph` objects.

    .. py:attribute:: widthBlocks

        The linked CWDH tables as :py:class:`WidthBlock` objects.

    .. py:attribute:: mappingBlocks

        The linked CMAP tables as :py:class:`MappingBlock` objects.

    .. py:attribute:: characterMap

        A read-only merged ``character code -> glyph index`` dictionary.

    .. py:function:: save()

        Generate the NFTR file data.

    .. py:classmethod:: fromFile(filePath)

        Load an NFTR from a filesystem file.

    .. py:function:: saveToFile(filePath)

        Save the NFTR to a filesystem file.

.. py:class:: Glyph(width, height, bpp, data)

    A glyph bitmap. Use :py:meth:`getPixels` and :py:meth:`setPixels` for dependency-free row-major integer pixels, or :py:meth:`renderAsImage` and :py:meth:`setImage` when Pillow is installed.

.. py:class:: CharacterWidth([left=0[, glyphWidth=0[, charWidth=0]]])

    One glyph's signed left bearing, bitmap width, and advance width.

.. py:class:: WidthBlock([firstGlyphIndex=0[, widths]])

    A CWDH width table for a consecutive range of glyph indices.

.. py:class:: MappingBlock([firstCharacterCode=0[, lastCharacterCode=0[, type=2[, characterToGlyph]]]], *, [unknown=0])

    A CMAP character-to-glyph mapping block. Mapping types 0, 1, and 2 are supported.
