import unittest

from fixed_point import (
    VALUE_MAX,
    VALUE_MIN,
    decode_fixed_16_16,
    encode_fixed_16_16,
    pack_fixed_16_16,
    unpack_fixed_16_16,
)


class FixedPointTests(unittest.TestCase):
    def test_known_value_is_written_as_four_little_endian_bytes(self):
        self.assertEqual(pack_fixed_16_16(150.0), b"\x00\x00\x96\x00")
        self.assertEqual(len(pack_fixed_16_16(150.0)), 4)

    def test_fractional_and_negative_values_round_trip(self):
        for value in (1.5, -2.25, VALUE_MIN, VALUE_MAX):
            self.assertEqual(unpack_fixed_16_16(pack_fixed_16_16(value)), value)

    def test_half_a_unit_is_rounded_away_from_zero(self):
        self.assertEqual(encode_fixed_16_16(0.5 / 65536), 1)
        self.assertEqual(encode_fixed_16_16(-0.5 / 65536), -1)

    def test_raw_conversion(self):
        self.assertEqual(decode_fixed_16_16(0x00018000), 1.5)

    def test_out_of_range_values_are_rejected(self):
        with self.assertRaises(ValueError):
            pack_fixed_16_16(32768)
        with self.assertRaises(ValueError):
            pack_fixed_16_16(-32768.00001)

    def test_unpack_requires_four_bytes(self):
        with self.assertRaises(ValueError):
            unpack_fixed_16_16(b"\x00\x00")


if __name__ == "__main__":
    unittest.main()
