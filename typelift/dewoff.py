import struct
import zlib
from cStringIO import StringIO


def read_woff_header(f):
    """
    Read the WOFF header from a file-like object, consuming the file up to the
    end of the header.

    Reference here: http://www.w3.org/TR/WOFF/#WOFFHeader
    """
    fmt = '>IIIHHIHHIIIII'
    buf = f.read(struct.calcsize(fmt))
    header = struct.unpack(fmt, buf)
    return dict(signature=header[0],
                flavor=header[1],
                length=header[2],
                numTables=header[3],
                reserved=header[4],
                totalSfontSize=header[5],
                majorVersion=header[6],
                minorVersion=header[7],
                metaOffset=header[8],
                metaLength=header[9],
                metaOrigLength=header[10],
                privOffset=header[11],
                privLength=header[12])


def read_woff_table_directory(f, num_tables):
    """
    Return an iterator over table directory entries in a file-like object,
    consuming the file progressively.
    """
    fmt = '>IIIII'
    entries = []
    for ii in range(num_tables):
        buf = f.read(struct.calcsize(fmt))
        entry = struct.unpack(fmt, buf)
        entries.append(dict(tag=entry[0],
                            offset=entry[1],
                            compLength=entry[2],
                            origLength=entry[3],
                            origChecksum=entry[4]))
    return entries


def read_font_table(f, entry):
    f.seek(entry['offset'])
    data = f.read(entry['compLength'])
    if entry['compLength'] != entry['origLength']:
        data = zlib.decompress(data)
    return data


def read_woff(f):
    """
    Parse a WOFF file from a file-like object.
    """
    header = read_woff_header(f)
    entries = read_woff_table_directory(f, header['numTables'])
    font_tables = []
    for entry in entries:
        font_tables.append(read_font_table(f, entry))
    return dict(header=header,
                entries=entries,
                font_tables=font_tables)


def write_otf_header(f, in_header):
    """
    Write an OTF header to a file-like object, given data supplied from a WOFF
    header.
    """
    num_tables = in_header['numTables']

    entrySelector = 0
    searchRange = 0
    for ii in range(64):
        sq = ii ** 2
        if sq < num_tables:
            entrySelector = ii
            searchRange = sq * 16

    rangeShift = (num_tables * 16) - searchRange

    out_header = struct.pack('>IHHHH',
                             in_header['flavor'],
                             in_header['numTables'],
                             searchRange,
                             entrySelector,
                             rangeShift)
    f.write(out_header)


def write_otf_table_directory_entry(f, entry, offset):
    """
    Write an OTF font table directory entry, specifying an offset for the font
    table.

    Return the length of this entry's font table, padded to a word boundary as
    per OTF spec.
    """
    l = entry['origLength']
    f.write(struct.pack('>IIII',
                        entry['tag'],
                        entry['origChecksum'],
                        offset,
                        l))
    if (l % 4) != 0:
        l += 4 - (l % 4)
    return l


def write_otf_font_table(f, entry, font_table, offset):
    """
    Write an OTF font table.
    """
    f.seek(offset)
    f.write(font_table)
    offset += entry['origLength']
    if (offset % 4) != 0:
        f.write('\0' * (4 - (offset % 4)))


def write_otf(f, data):
    """
    Write an OTF file to a file-like object, using data as supplied from
    read_woff().
    """
    write_otf_header(f, data['header'])

    offset = f.tell() + (16 * len(data['entries']))
    table_offsets = []
    for entry in data['entries']:
        table_offsets.append(offset)
        l = write_otf_table_directory_entry(f, entry, offset)
        offset += l

    for entry, font_table, offset in zip(data['entries'],
                                         data['font_tables'],
                                         table_offsets):
        write_otf_font_table(f, entry, font_table, offset)


def woff_to_otf(font_data):
    """
    Translate a string containing WOFF data to a string containing OTF data.
    """
    inf = StringIO(font_data)
    outf = StringIO()
    write_otf(outf, read_woff(inf))
    return outf.getvalue()


if __name__ == '__main__':
    import sys
    _, a, b = sys.argv
    with open(a, 'rb') as inf:
        data = read_woff(inf)
        with open(b, 'wb') as outf:
            write_otf(outf, data)
