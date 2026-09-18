import zlib
import numpy as np
from satisfactory_route_tool.heightfield import decode_i16, decode_u8


def encode_i16(a):
    delta=np.diff(a.astype(np.int32),axis=1,prepend=0).astype(np.int16)
    return zlib.compress(delta.tobytes())


def test_i16_roundtrip():
    a=np.array([[1,2,300,-32768],[5,-10,9,100]],dtype=np.int16)
    got=decode_i16(encode_i16(a),2,4)
    assert np.array_equal(a,got)


def test_u8_decode():
    a=np.arange(12,dtype=np.uint8).reshape(3,4)
    got=decode_u8(zlib.compress(a.tobytes()),3,4)
    assert np.array_equal(a,got)
