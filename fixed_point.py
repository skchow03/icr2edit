"""Conversions for values stored in signed 16.16 fixed-point format."""

import struct
from decimal import Decimal, ROUND_HALF_UP


FRACTION_BITS = 16
SCALE = 1 << FRACTION_BITS
RAW_MIN = -(1 << 31)
RAW_MAX = (1 << 31) - 1
VALUE_MIN = RAW_MIN / SCALE
VALUE_MAX = RAW_MAX / SCALE


def encode_fixed_16_16(value):
    """Convert a numeric value to its signed 32-bit 16.16 representation."""
    scaled = (Decimal(str(value)) * SCALE).to_integral_value(rounding=ROUND_HALF_UP)
    raw_value = int(scaled)
    if not RAW_MIN <= raw_value <= RAW_MAX:
        raise ValueError(f"16.16 value out of range: {value}")
    return raw_value


def decode_fixed_16_16(raw_value):
    """Convert a signed 32-bit 16.16 representation to a display value."""
    if not RAW_MIN <= raw_value <= RAW_MAX:
        raise ValueError(f"16.16 raw value out of range: {raw_value}")
    return raw_value / SCALE


def pack_fixed_16_16(value):
    """Encode a value as exactly four little-endian 16.16 bytes."""
    return struct.pack("<i", encode_fixed_16_16(value))


def unpack_fixed_16_16(data):
    """Decode exactly four little-endian 16.16 bytes."""
    if len(data) != 4:
        raise ValueError("A 16.16 value must contain exactly 4 bytes")
    return decode_fixed_16_16(struct.unpack("<i", data)[0])
