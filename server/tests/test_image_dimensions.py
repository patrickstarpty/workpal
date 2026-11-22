import struct
import zlib
import pytest


def png_chunk(kind,payload):
    return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))


def png(width=80,height=40,depth=8,color=2):
    return b'\x89PNG\r\n\x1a\n'+png_chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,depth,color,0,0,0))


def jpeg_segment(marker,payload):return bytes([255,marker])+struct.pack('>H',len(payload)+2)+payload


def jpeg(width=80,height=40,jfif=True):
    sof=struct.pack('>BHHB',8,height,width,1)+bytes([1,0x11,0])
    return b'\xff\xd8'+(jpeg_segment(0xe0,b'JFIF\0') if jfif else b'')+jpeg_segment(0xc0,sof)


def exif(orientation,order='little'):
    end='<' if order=='little' else '>'
    return b'Exif\0\0'+(b'II' if order=='little' else b'MM')+struct.pack(end+'HIHHHIH',42,8,1,0x112,3,1,orientation)+b'\0'*6


@pytest.mark.parametrize(('body','expected'),[
    (png(),(80,40)),(png(100000,50000),(100000,50000)),
    (png(0,10),None),(png(1<<31,10),None),(png((1<<31)-1,(1<<31)-1),None),
    (png()[:-1]+b'\0',None),(png(color=3),None),
    (png(color=3)+png_chunk(b'PLTE',b'\0'*3)+b'\0\0\0\0IDAT',(80,40)),
    (b'GIF89a'+struct.pack('<HHBBB',80,40,0,0,0),(80,40)),
    (b'GIF87a'+struct.pack('<HHBBB',80,40,0x80,0,0),None),
    (b'GIF87a'+struct.pack('<HHBBB',80,40,0x80,0,0)+b'\0'*6,(80,40)),
    (jpeg(),(80,40)),(jpeg(jfif=False),None),
    (jpeg(jfif=False)+b'\xff\xda\0\x02',(80,40)),
    (jpeg(jfif=False)+b'\xff\xd9',None),
    (b'not an image',None),
])
def test_dimensions_only_reads_supported_config(body,expected):
    from workpal_backend.files.image_dimensions import dimensions
    assert dimensions(body)==expected


@pytest.mark.parametrize('orientation',range(1,10))
@pytest.mark.parametrize('order',['little','big'])
def test_jpeg_exif_display_orientation(orientation,order):
    from workpal_backend.files.image_dimensions import dimensions
    raw=jpeg()
    body=raw[:2]+jpeg_segment(0xe1,exif(orientation,order))+raw[2:]
    assert dimensions(body)==((40,80) if 5<=orientation<=8 else (80,40))
