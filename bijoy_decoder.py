"""Bijoy Classic (SutonnyMJ) to Unicode Bengali decoder — v2.

Core approach: character-by-character with pre-kar reordering.
Conjuncts built algorithmically from hasanta + consonant sequences.
"""

# Single-char Bijoy -> Unicode mapping
_SINGLE = {
    # Independent vowels
    'A': '\u0985', 'B': '\u0987', 'C': '\u0988',
    'D': '\u0989', 'E': '\u098A', 'F': '\u098B',
    'G': '\u098F', 'H': '\u0990', 'I': '\u0993', 'J': '\u0994',
    # Consonants
    'K': '\u0995', 'L': '\u0996', 'M': '\u0997', 'N': '\u0998',
    'O': '\u0999', 'P': '\u099A', 'Q': '\u099B', 'R': '\u099C',
    'S': '\u099D', 'T': '\u099E', 'U': '\u099F', 'V': '\u09A0',
    'W': '\u09A1', 'X': '\u09A2', 'Y': '\u09A3', 'Z': '\u09A4',
    '_': '\u09A5', '`': '\u09A6', 'a': '\u09A7', 'b': '\u09A8',
    'c': '\u09AA', 'd': '\u09AB', 'e': '\u09AC', 'f': '\u09AD',
    'g': '\u09AE', 'h': '\u09AF', 'i': '\u09B0', 'j': '\u09B2',
    'k': '\u09B6', 'l': '\u09B7', 'm': '\u09B8', 'n': '\u09B9',
    # Vowel signs
    'v': '\u09BE', 'w': '\u09BF', 'x': '\u09C0',
    'y': '\u09C1', '~': '\u09C3',
    # Marks
    'r': '\u09CD',  # hasanta
    's': '\u0982',  # anusvara
    't': '\u0983',  # visarga
    'u': '\u0981',  # chandrabindu
    # Digits
    '0': '\u09E6', '1': '\u09E7', '2': '\u09E8', '3': '\u09E9',
    '4': '\u09EA', '5': '\u09EB', '6': '\u09EC', '7': '\u09ED',
    '8': '\u09EE', '9': '\u09EF',
    # Punctuation
    '|': '\u0964',
    # Quoted-printable leftover
    '‡': '',  # placeholder, handled in multi-char
}

# Two-char sequences
_TWO = {
    'Av': '\u0986',  # আ
    '‡v': '\u09CB',  # ো (composed)
    '‡Š': '\u09CC',  # ৌ (composed)
}

# Common conjuncts (Bijoy sequence -> Unicode string)
_CONJUNCTS = {
    '°': '\u0995\u09CD\u0995',    # ক্ক
    '±': '\u0995\u09CD\u099F',    # ক্ট
    '³': '\u0995\u09CD\u09A4',    # ক্ত
    'µ': '\u0995\u09CD\u09B0',    # ক্র
    'K\u00A1': '\u0995\u09CD\u09B7',  # ক্ষ
    'K\u00AC': '\u0995\u09CD\u09B2',  # ক্ল
    '\u00B6': '\u0995\u09CD\u09B8',   # ক্স
    '\u00B8': '\u0997\u09C1',         # গু
    '\u00BB': '\u0997\u09CD\u09A7',   # গ্ধ
    'M\u0153': '\u0997\u09CD\u09A8',  # গ্ন
    'M\u00A5': '\u0997\u09CD\u09AE',  # গ্ম
    'M\u00AD': '\u0997\u09CD\u09B2',  # গ্ল
    '\u00BC': '\u0999\u09CD\u0995',   # ঙ্ক
    '\u00BD': '\u0999\u09CD\u0997',   # ঙ্গ
    '"P': '\u099A\u09CD\u099A',       # চ্চ
    '"Q': '\u099A\u09CD\u099B',       # চ্ছ
    '"T': '\u099A\u09CD\u099E',       # চ্ঞ
    '\u00BF': '\u099C\u09CD\u099C',   # জ্জ
    '\u00C0': '\u099C\u09CD\u099D',   # জ্ঝ
    '\u00C1': '\u099C\u09CD\u099E',   # জ্ঞ
    'R\u00A1': '\u099C\u09CD\u09AC',  # জ্ব
    '\u00C2': '\u099E\u09CD\u099A',   # ঞ্চ
    '\u00C3': '\u099E\u09CD\u099B',   # ঞ্ছ
    '\u00C4': '\u099E\u09CD\u099C',   # ঞ্জ
    '\u00C5': '\u099E\u09CD\u099D',   # ঞ্ঝ
    '\u00C6': '\u099F\u09CD\u099F',   # ট্ট
    'U\u00A1': '\u099F\u09CD\u09AC',  # ট্ব
    'U\u00A5': '\u099F\u09CD\u09AE',  # ট্ম
    '\u00C7': '\u09A1\u09CD\u09A1',   # ড্ড
    '\u00C8': '\u09A3\u09CD\u099F',   # ণ্ট
    '\u00C9': '\u09A3\u09CD\u09A0',   # ণ্ঠ
    '\u00CA': '\u09A3\u09CD\u09A1',   # ণ্ড
    '\u00CB': '\u09A4\u09CD\u09A4',   # ত্ত
    '\u00CC': '\u09A4\u09CD\u09A8',   # ত্ন
    'Z\u0153': '\u09A4\u09CD\u09AE',  # ত্ম
    '_\u00A1': '\u09A5\u09CD\u09AC',  # থ্ব
    '\u00CF': '\u09A6\u09CD\u09A7',   # দ্ধ
    '\u00D0': '\u09A6\u09CD\u09AC',   # দ্ব
    '\u00D5': '\u09A6\u09CD\u09AE',   # দ্ম
    'a\u00DF': '\u09A7\u09CD\u09AC',  # ধ্ব
    'a\u00A5': '\u09A7\u09CD\u09AE',  # ধ্ম
    '\u00DA': '\u09A8\u09CD\u09A4',   # ন্ত
    'b\u0153': '\u09A8\u09CD\u09A8',  # ন্ন
    'b\u00A5': '\u09A8\u09CD\u09AE',  # ন্ম
    '\u00DE': '\u09AA\u09CD\u099F',   # প্ট
    '\u00DF': '\u09AA\u09CD\u09A4',   # প্ত
    'c\u0153': '\u09AA\u09CD\u09AA',  # প্প
    'c\u00AD': '\u09AA\u09CD\u09B2',  # প্ল
    'd\u00AC': '\u09AC\u09CD\u099C',  # ব্জ
    '\u00E2': '\u09AC\u09CD\u09A6',   # ব্দ
    '\u00E3': '\u09AC\u09CD\u09A7',   # ব্ধ
    'e\u00DF': '\u09AC\u09CD\u09AC',  # ব্ব
    'e\u00AD': '\u09AC\u09CD\u09B2',  # ব্ল
    '\u00E5': '\u09AE\u09CD\u09A8',   # ম্ন
    'g\u0153': '\u09AE\u09CD\u09AA',  # ম্প
    '\u00E4\u00BA': '\u09AE\u09CD\u09AB',  # ম্ফ
    '\u00E4^': '\u09AE\u09CD\u09AC',  # ম্ব
    '\u00E4\u00A2': '\u09AE\u09CD\u09AD',  # ম্ভ
    '\u00E4\u00A7': '\u09AE\u09CD\u09AE',  # ম্ম
    '\u00E4\u00AD': '\u09AE\u09CD\u09B2',  # ম্ল
    'i"': '\u09B0\u09C1',             # রু
    'i\u0192': '\u09B0\u09C2',        # রূ
    '\u00E9': '\u09B2\u09CD\u0995',   # ল্ক
    '\u00EA': '\u09B2\u09CD\u0997',   # ল্গ
    '\u00ED': '\u09B2\u09CD\u09AA',   # ল্প
    '\u00EB': '\u09B2\u09CD\u099F',   # ল্ট
    '\u00EC': '\u09B2\u09CD\u09A1',   # ল্ড
    '\u00EE': '\u09B2\u09CD\u09AB',   # ল্ফ
    'j\u00A6': '\u09B2\u09CD\u09AE',  # ল্ম
    'j\u00A5': '\u09B2\u09CD\u09B2',  # ল্ল
    'j\u00F8': '\u09B6\u09C1',        # শু
    '\u00EF': '\u09B6\u09CD\u099A',   # শ্চ
    '\u00F0': '\u09B6\u09CD\u09A8',   # শ্ন
    'k\u0153': '\u09B6\u09CD\u09AC',  # শ্ব
    'k\u00A6': '\u09B6\u09CD\u09AE',  # শ্ম
    'k\u00A5': '\u09B6\u09CD\u09B2',  # শ্ল
    'k\u00F8': '\u09B7\u09CD\u0995',  # ষ্ক
    '\u00F3': '\u09B7\u09CD\u099F',   # ষ্ট
    '\u00F4': '\u09B7\u09CD\u09A0',   # ষ্ঠ
    '\u00F2': '\u09B7\u09CD\u09A3',   # ষ্ণ
    '\u00F5': '\u09B7\u09CD\u09AE',   # ষ্ম
    '\u00A7\u00A7': '\u09B8\u09CD\u0995',  # স্ক
    '\u00AF\u2039': '\u09B8\u09CD\u099F',  # স্ট
    '\u00F7': '\u09B8\u09CD\u0996',   # স্খ
    '\u00F6': '\u09B8\u09CD\u09A4',   # স্ত
    'm\u0153': '\u09B8\u09CD\u09AA',  # স্প
    '\u00F9': '\u09B8\u09CD\u09AC',   # স্ব
    '\u00AF\u00A7': '\u09B8\u09CD\u09AE',  # স্ম
    '\u00AF\u00AD': '\u09B8\u09CD\u09B2',  # স্ল
    '\u00FB': '\u09B9\u09C1',         # হু
    'n\u00E8': '\u09B9\u09CD\u09A3',  # হ্ণ
    '\u00FD': '\u09B9\u09CD\u09A8',   # হ্ন
    '\u00FE': '\u09B9\u09CD\u09AE',   # হ্ম
    'n\u00AC': '\u09B9\u09C3',        # হৃ
    '\u00FC': '\u09B9\u09CD\u09B2',   # হ্ল
    # Common pre-kar sequences (e before consonant)
    'KG': '\u0995\u09C7',  # কে
    'LG': '\u0996\u09C7',  # খে
    'MG': '\u0997\u09C7',  # গে
    'NG': '\u0998\u09C7',  # ঘে
    'OG': '\u0999\u09C7',  # ঙে
    'PG': '\u099A\u09C7',  # চে
    'QG': '\u099B\u09C7',  # ছে
    'RG': '\u099C\u09C7',  # জে
    'SG': '\u099D\u09C7',  # ঝে
    'TG': '\u099E\u09C7',  # ঞে
    'UG': '\u099F\u09C7',  # টে
    'VG': '\u09A0\u09C7',  # ঠে
    'WG': '\u09A1\u09C7',  # ডে
    'XG': '\u09A2\u09C7',  # ঢে
    'YG': '\u09A3\u09C7',  # ণে
    'ZG': '\u09A4\u09C7',  # তে
    '_G': '\u09A5\u09C7',  # থে
    '`G': '\u09A6\u09C7',  # দে
    'aG': '\u09A7\u09C7',  # ধে
    'bG': '\u09A8\u09C7',  # নে
    'cG': '\u09AA\u09C7',  # পে
    'dG': '\u09AB\u09C7',  # ফে
    'eG': '\u09AC\u09C7',  # বে
    'fG': '\u09AD\u09C7',  # ভে
    'gG': '\u09AE\u09C7',  # মে
    'hG': '\u09AF\u09C7',  # যে
    'iG': '\u09B0\u09C7',  # রে
    'jG': '\u09B2\u09C7',  # লে
    'kG': '\u09B6\u09C7',  # শে
    'lG': '\u09B7\u09C7',  # ষে
    'mG': '\u09B8\u09C7',  # সে
    'nG': '\u09B9\u09C7',  # হে
    # Pre-kar ai (e + H)
    'KH': '\u0995\u09C8',  # কৈ
    'LH': '\u0996\u09C8',  # খৈ
    'MH': '\u0997\u09C8',  # গৈ
    'NH': '\u0998\u09C8',  # ঘৈ
    'OH': '\u0999\u09C8',  # ঙৈ
    'PH': '\u099A\u09C8',  # চৈ
    'QH': '\u099B\u09C8',  # ছৈ
    'RH': '\u099C\u09C8',  # জৈ
    'SH': '\u099D\u09C8',  # ঝৈ
    'TH': '\u099E\u09C8',  # ঞৈ
    'UH': '\u099F\u09C8',  # টৈ
    'VH': '\u09A0\u09C8',  # ঠৈ
    'WH': '\u09A1\u09C8',  # ডৈ
    'XH': '\u09A2\u09C8',  # ঢৈ
    'YH': '\u09A3\u09C8',  # ণৈ
    'ZH': '\u09A4\u09C8',  # তৈ
    '_H': '\u09A5\u09C8',  # থৈ
    '`H': '\u09A6\u09C8',  # দৈ
    'aH': '\u09A7\u09C8',  # ধৈ
    'bH': '\u09A8\u09C8',  # নৈ
    'cH': '\u09AA\u09C8',  # পৈ
    'dH': '\u09AB\u09C8',  # ফৈ
    'eH': '\u09AC\u09C8',  # বৈ
    'fH': '\u09AD\u09C8',  # ভৈ
    'gH': '\u09AE\u09C8',  # মৈ
    'hH': '\u09AF\u09C8',  # যৈ
    'iH': '\u09B0\u09C8',  # রৈ
    'jH': '\u09B2\u09C8',  # লৈ
    'kH': '\u09B6\u09C8',  # শৈ
    'lH': '\u09B7\u09C8',  # ষৈ
    'mH': '\u09B8\u09C8',  # সৈ
    'nH': '\u09B9\u09C8',  # হৈ
}

# Consonant set
_CONSONANTS = set('KLMNOPQRSTUVWXYZ_`abcdefghijklmnopqrstn')
_VOWEL_SIGNS = set('vwx~y')


def decode_bijoy(text):
    """Convert Bijoy Classic (SutonnyMJ) text to Unicode Bengali."""
    if not text:
        return ""

    # Step 1: Normalize quoted-printable artifacts
    text = text.replace('=\n', '')
    text = text.replace('=3D', '=')
    text = text.replace('=E2=80=A0', '')  # dagger
    text = text.replace('=E2=80=99', "'")
    text = text.replace('=C2=', '')
    text = text.replace('=C3=', '')
    text = text.replace('=A0', '')
    text = text.replace('=B6', '\u00B6')
    text = text.replace('=A1', '\u00A1')
    text = text.replace('=A5', '\u00A5')
    text = text.replace('=AD', '\u00AD')
    text = text.replace('=A7', '\u00A7')
    text = text.replace('=A6', '\u00A6')
    text = text.replace('=A4', '\u00A4')
    text = text.replace('=A2', '\u00A2')
    text = text.replace('=A3', '\u00A3')
    text = text.replace('=BA', '\u00BA')
    text = text.replace('=BC', '\u00BC')
    text = text.replace('=BD', '\u00BD')
    text = text.replace('=BE', '\u00BE')
    text = text.replace('=BF', '\u00BF')
    text = text.replace('=C0', '\u00C0')
    text = text.replace('=C1', '\u00C1')
    text = text.replace('=C2', '\u00C2')
    text = text.replace('=C4', '\u00C4')
    text = text.replace('=C5', '\u00C5')
    text = text.replace('=C6', '\u00C6')
    text = text.replace('=C7', '\u00C7')
    text = text.replace('=C8', '\u00C8')
    text = text.replace('=C9', '\u00C9')
    text = text.replace('=CA', '\u00CA')
    text = text.replace('=CB', '\u00CB')
    text = text.replace('=CC', '\u00CC')
    text = text.replace('=CD', '\u00CD')
    text = text.replace('=CF', '\u00CF')
    text = text.replace('=D0', '\u00D0')
    text = text.replace('=D2', '\u00D2')
    text = text.replace('=D5', '\u00D5')
    text = text.replace('=DA', '\u00DA')
    text = text.replace('=DE', '\u00DE')
    text = text.replace('=DF', '\u00DF')
    text = text.replace('=E0', '\u00E0')
    text = text.replace('=E1', '\u00E1')
    text = text.replace('=E2', '\u00E2')
    text = text.replace('=E3', '\u00E3')
    text = text.replace('=E4', '\u00E4')
    text = text.replace('=E5', '\u00E5')
    text = text.replace('=E6', '\u00E6')
    text = text.replace('=E7', '\u00E7')
    text = text.replace('=E8', '\u00E8')
    text = text.replace('=E9', '\u00E9')
    text = text.replace('=EA', '\u00EA')
    text = text.replace('=EB', '\u00EB')
    text = text.replace('=EC', '\u00EC')
    text = text.replace('=ED', '\u00ED')
    text = text.replace('=EE', '\u00EE')
    text = text.replace('=EF', '\u00EF')
    text = text.replace('=F0', '\u00F0')
    text = text.replace('=F1', '\u00F1')
    text = text.replace('=F2', '\u00F2')
    text = text.replace('=F3', '\u00F3')
    text = text.replace('=F4', '\u00F4')
    text = text.replace('=F5', '\u00F5')
    text = text.replace('=F6', '\u00F6')
    text = text.replace('=F7', '\u00F7')
    text = text.replace('=F8', '\u00F8')
    text = text.replace('=F9', '\u00F9')
    text = text.replace('=FA', '\u00FA')
    text = text.replace('=FB', '\u00FB')
    text = text.replace('=FC', '\u00FC')
    text = text.replace('=FD', '\u00FD')
    text = text.replace('=FE', '\u00FE')
    text = text.replace('=FF', '\u00FF')

    # Step 2: Character-by-character decoding with longest match
    result = []
    i = 0
    n = len(text)

    while i < n:
        matched = False

        # Try 3-char match
        if i + 2 < n:
            chunk3 = text[i:i+3]
            if chunk3 in _CONJUNCTS:
                result.append(_CONJUNCTS[chunk3])
                i += 3
                matched = True

        # Try 2-char match
        if not matched and i + 1 < n:
            chunk2 = text[i:i+2]
            if chunk2 in _TWO:
                result.append(_TWO[chunk2])
                i += 2
                matched = True
            elif chunk2 in _CONJUNCTS:
                result.append(_CONJUNCTS[chunk2])
                i += 2
                matched = True

        # Single char
        if not matched:
            ch = text[i]
            if ch in _SINGLE:
                result.append(_SINGLE[ch])
            else:
                result.append(ch)
            i += 1

    return ''.join(result)


if __name__ == '__main__':
    import sys

    test_cases = [
        'Ges',           # এক
        'Gi gvb KZ?',    # এর মান কত?
        'KvbwU',         # বিষয়
        'GKwU',          # একটি
        'b`xi',          # দশ
        'cïLGi',         # ?
    ]

    for t in test_cases:
        decoded = decode_bijoy(t)
        sys.stdout.buffer.write(f"{t} -> {decoded}\n".encode('utf-8'))
