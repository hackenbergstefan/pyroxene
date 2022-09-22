#include <stddef.h>
#include <stdint.h>

// Generated using: ", ".join((f'"{i:02x}"' for i in range(256)))
static const char *BIN_TO_HEX[256] = {
    "00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "0a", "0b", "0c", "0d", "0e", "0f", "10", "11", "12",
    "13", "14", "15", "16", "17", "18", "19", "1a", "1b", "1c", "1d", "1e", "1f", "20", "21", "22", "23", "24", "25",
    "26", "27", "28", "29", "2a", "2b", "2c", "2d", "2e", "2f", "30", "31", "32", "33", "34", "35", "36", "37", "38",
    "39", "3a", "3b", "3c", "3d", "3e", "3f", "40", "41", "42", "43", "44", "45", "46", "47", "48", "49", "4a", "4b",
    "4c", "4d", "4e", "4f", "50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "5a", "5b", "5c", "5d", "5e",
    "5f", "60", "61", "62", "63", "64", "65", "66", "67", "68", "69", "6a", "6b", "6c", "6d", "6e", "6f", "70", "71",
    "72", "73", "74", "75", "76", "77", "78", "79", "7a", "7b", "7c", "7d", "7e", "7f", "80", "81", "82", "83", "84",
    "85", "86", "87", "88", "89", "8a", "8b", "8c", "8d", "8e", "8f", "90", "91", "92", "93", "94", "95", "96", "97",
    "98", "99", "9a", "9b", "9c", "9d", "9e", "9f", "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "aa",
    "ab", "ac", "ad", "ae", "af", "b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "ba", "bb", "bc", "bd",
    "be", "bf", "c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "ca", "cb", "cc", "cd", "ce", "cf", "d0",
    "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9", "da", "db", "dc", "dd", "de", "df", "e0", "e1", "e2", "e3",
    "e4", "e5", "e6", "e7", "e8", "e9", "ea", "eb", "ec", "ed", "ee", "ef", "f0", "f1", "f2", "f3", "f4", "f5", "f6",
    "f7", "f8", "f9", "fa", "fb", "fc", "fd", "fe", "ff"
};

// Generated using: ", ".join(f"{bytes.fromhex('0'+chr(i))[0]} /* {chr(i)} */" if i in [ord(a) for a in
// "0123456789abcdefABCDEF"] else "0" for i in range(128))
static const uint8_t HEX_TO_BIN[256] = {
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0,          0,          0 /* 0 */,  1 /* 1 */,  2 /* 2 */,  3 /* 3 */,  4 /* 4 */,  5 /* 5 */,
    6 /* 6 */,  7 /* 7 */,  8 /* 8 */,  9 /* 9 */,  0,          0,          0,          0,          0,
    0,          0,          10 /* A */, 11 /* B */, 12 /* C */, 13 /* D */, 14 /* E */, 15 /* F */, 0,
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0,          0,          0,          0,          0,          0,          10 /* a */, 11 /* b */,
    12 /* c */, 13 /* d */, 14 /* e */, 15 /* f */, 0,          0,          0,          0,          0,
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0,          0,          0,          0,          0,          0,          0,          0,
    0,          0
};

int bin2hex(const uint8_t *binary, size_t binary_length, uint8_t *hexstring, size_t hexstring_length)
{
    if (hexstring_length != 2 * binary_length)
    {
        return -1;
    }

    size_t i = 0;
    for (; i < binary_length; i++)
    {
        const char *converted = BIN_TO_HEX[binary[i]];
        hexstring[2 * i] = converted[0];
        hexstring[2 * i + 1] = converted[1];
    }
    // hexstring[2 * (i + 1)] = '\0';
    return 0;
}

int hex2bin(const uint8_t *hexstring, size_t hexstring_length, uint8_t *binary, size_t binary_length)
{
    if (hexstring_length != 2 * binary_length)
    {
        return -1;
    }

    for (size_t i = 0; i < binary_length; i++)
    {
        binary[i] = HEX_TO_BIN[hexstring[2 * i]] * 16 + HEX_TO_BIN[hexstring[2 * i + 1]];
    }
    return 0;
}
