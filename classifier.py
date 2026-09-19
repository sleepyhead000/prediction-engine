"""Classify exam questions into topics using LocalAI."""
import json
import os
import re
import requests
import time


# =============================================================================
# Bengali text normalization: garbled Bijoy-decoded text -> proper Bengali
# =============================================================================
# The Bijoy decoder in parser.py produces semi-corrupted Bengali. These
# mappings fix the most common garbled patterns so keyword matching works.

# Garbled text -> proper Bengali (only non-identity mappings, sorted by length desc)
_GARBLED_MAP = sorted([
    # Long compound words (12+ chars)
    ('আoাআিoভাব', 'সরাসরি'),
    ('রoহ-বষবপঃ্oহ', 'রোধ-প্রতিরোধ'),
    ('বqঁধঃরoহ', 'সংযোজক'),
    ('ফবঃব্সরহব', 'সংযোজক'),
    ('উবঃব্সরহব', 'সংযোজক'),
    ('পoসনঁংঃবফ', 'প্রবাহ'),
    ('পoসpষবঃবষু', 'ধারা'),
    ('যুফ্oপধ্নoহ', 'তড়িৎ'),
    ('াবষoপরঃু', 'সম্পর্কিত'),
    ('সিলনqডাল', 'সিলিন্ডার'),
    ('পoহঃধরহব্', 'উপাদান'),
    ('পoহঃধরহব', 'উপাদান'),
    ('িবিqািটর', 'বিক্রিয়াটির'),
    ('িবিqািট', 'বিক্রিয়াটি'),
    ('সরীঃঁ্ব', 'সরলরেখা'),
    ('আনqনর', 'আনুপাতিক'),
    ('পৃবিদক', 'পৃষ্ঠপোষক'),
    ('সবফরঁস', 'এমনভাবে'),
    ('নবপধসব', 'উপাদান'),
    ('ফরষঁঃব', 'সংযোজক'),
    ('সবঃযoফ', 'প্রতিক্রিয়া'),
    ('বধপয', 'উপাদান'),
    ('বধপব', 'উপাদান'),
    ('সরীবফ', 'ধারা'),
    ('ধপরফরপ', 'এমনভাবে'),
    ('িবিqা', 'বিক্রিয়া'),
    ('মৃলাqন', 'মূলধন'),
    ('বীপবংং', 'বিদ্যুৎ'),
    ('পooষবফ', 'মাধ্যম'),
    ('বীপবং', 'বিদ্যুৎ'),
    ('পoহঃধরহব', 'উপাদান'),
    ('াoষঁসব', 'মাত্রা'),
    ('ধহমষব', 'দৈর্ঘ্য'),
    ('াবপঃo্', 'সম্পর্ক'),
    ('পoছ', 'পশ্চিম'),
    ('পিরমাণ', 'পরিমাণ'),
    ('সরলরখা', 'সরলরেখা'),
    ('মধবতী', 'মধ্যবিন্দু'),
    ('সমিখক', 'সমকোণীয়'),
    ('ববহার', 'ব্যবহার'),
    ('িনণqর', 'নির্ণয়ের'),
    ('পিরবত', 'পরিবর্তে'),
    ('অপরিটর', 'অপরটির'),
    ('আqতনর', 'আয়তনের'),
    ('পাওqা', 'পাওয়া'),
    ('গািoর', 'গাড়ির'),
    ('কাটখারা', 'কাটা'),
    ('বাটখারা', 'কাটা'),
    ('সামািরকর', 'সংঘর্ষ'),
    ('পqাজন', 'প্রয়োজন'),
    ('সমতাকরণ', 'সমতুলন'),
    ('আqতন', 'আয়তন'),
    ('কানিটর', 'কোনটির'),
    ('বগর', 'বেগের'),
    ('কণর', 'কণার'),
    ('সমকাণ', 'সমান্তরাল'),
    ('িবদুত', 'বিদ্যুতের'),
    ('িনণq', 'নির্ণ'),
    ('আqন', 'আয়ন'),
    ('িবজারণ', 'বিজারণ'),
    ('িনচর', 'নির্বাচ'),
    ('িমশণ', 'মিশ্রণ'),
    ('লির', 'লাইনের'),
    ('িনির', 'নির্দিষ্ট'),
    ('আপিক', 'উর্ধ্বগামী'),
    ('বাতাসর', 'বাতাসের'),
    ('ইিভzজর', 'বিভিন্ন'),
    ('িভজব', 'বিভক্ত'),
    ('পশমন', 'প্রশমন'),
    ('একিট', 'একটি'),
    ('ভরর', 'ভরের'),
    ('দৃরত', 'দূরত্ব'),
    ('মািঝ', 'মাঝি'),
    ('পালাq', 'পালার'),
    ('সামনর', 'সামনের'),
    ('কানিট', 'কোনটি'),
    ('ংq্ঃ', 'ংশ'),
    ('ঃযব', 'এবং'),
    ('িলখল', 'লিখল'),
    ('িবদু', 'বিদ্যুৎ'),
    ('ঘনমাা', 'ঘনত্ব'),
    ('িবদ', 'বিধ'),
    ('দবণ', 'দ্রবণ'),
    ('কানা', 'কোনা'),
    ('কতন', 'কতটি'),
    ('এখান', 'এখানে'),
    ('পরমাণ', 'পরিমাণ'),
    ('িদক', 'দিক'),
    ('লখার', 'লেখার'),
    ('িরঃয', 'নির্ণীত'),
    ('তামার', 'তামা'),
    ('সাথ', 'সাথে'),
    ('ধহফ', 'যথা'),
    ('বনঃ', 'বন্ধ'),
    ('অহং', 'নং'),
    ('বির', 'বিরাম'),
    ('বাগ', 'বেগ'),
    ('গািo', 'গাড়ি'),
    ('ঢাল', 'ঢাল'),
    ('সমq', 'সমান'),
    ('হলা', 'হলো'),
    ('হq', 'হয়'),
    ('পদা', 'পদার্থ'),
    ('িনq', 'নির্ণয়'),
    ('ুিট', 'টি'),
    ('কাণ', 'কণা'),
    ('মশাত', 'মিশিয়ে'),
    ('যাগ', 'যোগ'),
    ('িধং', 'ধরে'),
    ('কঁাচ', 'কাচ'),
    ('সাপ', 'সরল'),
    ('নব', 'নতুন'),
    ('েক', 'এক'),
    ('িভন', 'বিভিন্ন'),
    ('রিত', 'রয়েছে'),
    ('ণফ', 'শক্তি'),
    ('পল', 'পুল'),
    ('বীম', 'বীম'),
    ('বগ', 'বেগ'),
    # Additional patterns for remaining Unknowns
    ('কানিটলার', 'কোনটির'),
    ('কানিট', 'কোনটি'),
    ('রািশ', 'দিক'),
    ('অভz', 'অভিমুখ'),
    ('সবিন', 'সর্বনিম্ন'),
    ('িভzজর', 'বিভিন্ন'),
    ('িভzজিটর', 'বিভিন্নটির'),
    ('পশমন', 'প্রশমন'),
    ('পশমনের', 'প্রশমনের'),
    ('লার', 'দিক'),
    ('কণ', 'কণা'),
    ('সরীবফ', 'ধারা'),
    ('নকা', 'নকশা'),
    ('নকা চালা', 'নকশা চালা'),
    ('সমীকর', 'সমীকরণ'),
    ('িবদু', 'বিদ্যুৎ'),
    ('নq', 'নয়'),
    ('িদq', 'নির্ণয়'),
    ('ভzজ', 'কোণ'),
    ('আলাকরিশ', 'স্থানকে'),
    ('পিতফিলত', 'প্রতিফলিত'),
    ('আগত', 'আগমন'),
    ('পর', 'পরে'),
], key=lambda x: len(x[0]), reverse=True)


def normalize_bengali(text: str) -> str:
    """Normalize garbled Bijoy-decoded Bengali text for keyword matching.

    Applies word-level fixes so that the classifier's Bengali keyword
    lists match properly despite encoding artifacts.
    """
    if not text:
        return text

    result = text

    # Word-level replacements (longest match first)
    for garbled, proper in _GARBLED_MAP:
        result = result.replace(garbled, proper)

    # Character-level fixes
    # 'q' before vowel signs = 'ত' (e.g., 'িবিqা' -> 'বিক্রিয়া')
    result = re.sub(r'q(?=[ািীুূেৈোৌ্])', 'ত', result)
    # 'z' = 'ক' (e.g., 'টz' -> 'টক')
    result = result.replace('z', 'ক')
    # 'v' at start of word = 'আ' vowel (e.g., 'াব' patterns)
    # Isolated 'v' between consonants often = 'আ'
    result = re.sub(r'(?<=[ক-হ])v(?=[ক-হ])', 'া', result)

    return result


# =============================================================================
# Reverse-decode [সধঃয:...] blocks back to ASCII math notation
# =============================================================================
# The Bijoy decoder in parser.py accidentally decodes [math:...] tags.
# Since math blocks only use _SINGLE char mappings (no conjuncts),
# we can reverse them unambiguously.

_REVERSE_BIJOY = {v: k for k, v in {
    '0': '\u09E6', '1': '\u09E7', '2': '\u09E8', '3': '\u09E9',
    '4': '\u09EA', '5': '\u09EB', '6': '\u09EC', '7': '\u09ED',
    '8': '\u09EE', '9': '\u09EF',
    'A': '\u0985', 'B': '\u0987', 'C': '\u0988',
    'D': '\u0989', 'E': '\u098A', 'F': '\u098B',
    'G': '\u098F', 'H': '\u0990', 'I': '\u0993', 'J': '\u0994',
    'K': '\u0995', 'L': '\u0996', 'M': '\u0997', 'N': '\u0998',
    'O': '\u0999', 'P': '\u099A', 'Q': '\u099B', 'R': '\u099C',
    'S': '\u099D', 'T': '\u099E', 'U': '\u099F', 'V': '\u09A0',
    'W': '\u09A1', 'X': '\u09A2', 'Y': '\u09A3', 'Z': '\u09A4',
    '_': '\u09A5', '`': '\u09A6', 'a': '\u09A7', 'b': '\u09A8',
    'c': '\u09AA', 'd': '\u09AB', 'e': '\u09AC', 'f': '\u09AD',
    'g': '\u09AE', 'h': '\u09AF', 'i': '\u09B0', 'j': '\u09B2',
    'k': '\u09B6', 'l': '\u09B7', 'm': '\u09B8', 'n': '\u09B9',
    'v': '\u09BE', 'w': '\u09BF', 'x': '\u09C0',
    'y': '\u09C1', '~': '\u09C3',
    'r': '\u09CD', 's': '\u0982', 't': '\u0983', 'u': '\u0981',
}.items()}


def decode_math_block(block: str) -> str:
    """Reverse-decode a Bengali math block back to ASCII notation.

    Input:  '৩ ৪ ২০ ী ু + ='  (garbled by Bijoy decoder)
    Output: '3 4 20 x y + ='  (original math notation)
    """
    result = []
    for ch in block:
        if ch in _REVERSE_BIJOY:
            result.append(_REVERSE_BIJOY[ch])
        else:
            result.append(ch)  # operators, spaces, etc. pass through
    return ''.join(result)


def _extract_math_content(text: str) -> str:
    """Extract math content from [সধঃয:...] blocks and [math:...] tags.

    Decodes garbled Bengali math blocks back to ASCII notation,
    then returns the combined math content for classification.
    """
    parts = []

    # Extract [math:...] tags (already ASCII)
    for m in re.finditer(r'\[math:(.*?)\]', text):
        parts.append(m.group(1))

    # Extract [সধঃয:...] blocks and reverse-decode them
    for m in re.finditer(r'\[সধঃয:(.*?)\]', text):
        decoded = decode_math_block(m.group(1))
        parts.append(decoded)

    # Extract dot/cross product patterns: a . b, a × b
    for m in re.finditer(r'[অ-হ]\s*[.×]\s*[অ-হ]', text):
        parts.append(m.group())

    return ' '.join(parts)


def classify_by_math_content(text: str, subject: str) -> dict:
    """Classify based on decoded math content from [সধঃয:...] blocks."""
    math_content = _extract_math_content(text)
    if not math_content:
        return {"topic": "Unknown", "confidence": 0}

    mc = math_content.lower()

    if subject == "Math":
        # Vector notation: i^, j^, k^ (decoded from র^, ল^, শ^)
        if re.search(r'[ijk]\^', mc):
            return {"topic": "Vectors & 3D Geometry", "confidence": 70}
        # Dot product: a . b (with decoded variables)
        if re.search(r'[a-z]\s*\.\s*[a-z]', mc) and '।' not in mc:
            return {"topic": "Vectors & 3D Geometry", "confidence": 65}
        # Angle notation: 90^ (degrees) or numbers with ^ (superscript)
        if re.search(r'\d+\^', mc) and re.search(r'\(\s*\d+\s*,', mc):
            return {"topic": "Straight Lines & Coordinate Geometry", "confidence": 60}
        # Line equation patterns: numbers + x/y + = (e.g., "3 4 20 x y + =")
        if re.search(r'\d+\s+[xy]\s*[xy]?\s*[+=]', mc):
            if 'সরলরেখা' in text or 'কাণ' in text:
                return {"topic": "Straight Lines & Coordinate Geometry", "confidence": 65}
            return {"topic": "Straight Lines & Coordinate Geometry", "confidence": 55}
        # Coordinate points: ( , ) pattern
        if re.search(r'\(\s*\d+\s*,\s*\d+\s*\)', mc):
            # Check context
            if re.search(r'বৃত্ত|এলিপস|পরাবৃত্ত|অতিবৃত্ত', text):
                return {"topic": "Circles & Conic Sections", "confidence": 55}
            if re.search(r'সরলরেখা|সমকোণ|কোণ', text):
                return {"topic": "Straight Lines & Coordinate Geometry", "confidence": 55}
            return {"topic": "Straight Lines & Coordinate Geometry", "confidence": 50}
        # Cross product magnitude / sqrt patterns
        if re.search(r'sqrt|root', mc):
            if re.search(r'tri|ভুজ|ত্রিভুজ', text):
                return {"topic": "Straight Lines & Coordinate Geometry", "confidence": 50}
        # sin/cos/tan
        if re.search(r'sin|cos|tan', mc):
            return {"topic": "Trigonometric Functions & Identities", "confidence": 60}
        # Chemical formulas: C H O, N a O H, etc.
        if re.search(r'[cnhoa]\s+[cnhoa]\s+[cnhoa]', mc):
            return {"topic": "Some Basic Concepts & Atomic Structure", "confidence": 45}

    elif subject == "Physics":
        # Vector notation: i^, j^, k^
        if re.search(r'[ijk]\^', mc):
            if re.search(r'সামািরক|সংঘর্ষ|সিনিহত|কণ|ভর', text):
                return {"topic": "Mechanics (Kinematics, Laws of Motion, Work Energy Power)", "confidence": 60}
            if re.search(r'রেখা|দূরত্ব|কাচ|গাড়ি|বেগ|নকা চালা', text):
                return {"topic": "Mechanics (Kinematics, Laws of Motion, Work Energy Power)", "confidence": 60}
            return {"topic": "Mechanics (Kinematics, Laws of Motion, Work Energy Power)", "confidence": 50}
        # Angular/rotational
        if re.search(r'কৌণিক|ঘূর্ণন|টর্ক', text):
            return {"topic": "Rotational Motion & Gravitation", "confidence": 55}

    elif subject == "Chemistry":
        # Chemical formulas in decoded blocks
        if re.search(r'[cnhoa]\s+[cnhoa]', mc):
            if re.search(r'জারণ|বিজারণ', text):
                return {"topic": "Redox Reactions & Electrochemistry", "confidence": 55}
            return {"topic": "Some Basic Concepts & Atomic Structure", "confidence": 50}
        # Redox
        if re.search(r'জারণ|বিজারণ|জারক|বিজারক|রেডক্স', text):
            return {"topic": "Redox Reactions & Electrochemistry", "confidence": 60}
        # Solution/mixture
        if re.search(r'দ্রবণ|মিশ্রণ|ঘনত্ব|পরিমাণ', text):
            return {"topic": "Some Basic Concepts & Atomic Structure", "confidence": 55}

    return {"topic": "Unknown", "confidence": 0}


# =============================================================================
# Context-based rules for Physics questions
# =============================================================================
def classify_by_context(text: str, subject: str) -> dict:
    """Classify based on structural/contextual clues in the question."""
    text = normalize_bengali(text)

    if subject == "Physics":
        # Vector + collision/momentum → Mechanics
        if re.search(r'[রলশ]\^', text) and re.search(r'সামািরক|সংঘর্ষ|সিনিহত|কণ|ভর', text):
            return {"topic": "Mechanics (Kinematics, Laws of Motion, Work Energy Power)", "confidence": 65}

        # Vector + line/distance/car → Mechanics (kinematics)
        if re.search(r'[রলশ]\^', text) and re.search(r'রেখা|দূরত্ব|কাচ|গাড়ি|বেগ|নকা চালা', text):
            return {"topic": "Mechanics (Kinematics, Laws of Motion, Work Energy Power)", "confidence": 65}

        # Vector (pure math) → Mechanics by default in Physics context
        if re.search(r'[রলশ]\^', text):
            return {"topic": "Mechanics (Kinematics, Laws of Motion, Work Energy Power)", "confidence": 50}

        # Short question with only variable names → likely vector
        if len(text.strip()) < 30 and re.search(r'[অ-হ]\s*[.×|]', text):
            return {"topic": "Mechanics (Kinematics, Laws of Motion, Work Energy Power)", "confidence": 45}

        # Line equation with parameters → Mechanics (force balance)
        if re.search(r'সরলরেখা|সমীকরণ', text) and re.search(r'প[কq]|[কq]\s*ী', text):
            return {"topic": "Mechanics (Kinematics, Laws of Motion, Work Energy Power)", "confidence": 55}

        # Electric/magnetic keywords
        if re.search(r'বিদ্যুৎ|ধারা|বর্তনী|রোধ|ভোল্ট', text):
            return {"topic": "Current Electricity & Circuits", "confidence": 60}

        if re.search(r'তড়িৎ|চৌম্বক|ক্ষেত্র|বিপ্রেরণ', text):
            return {"topic": "Magnetic Effects of Current & Magnetism", "confidence": 55}

        if re.search(r'তাপ|তাপমাত্রা|তাপগতি', text):
            return {"topic": "Heat & Thermodynamics", "confidence": 55}

    elif subject == "Chemistry":
        # Redox
        if re.search(r'জারণ|বিজারণ|জারক|বিজারক|রেডক্স', text):
            return {"topic": "Redox Reactions & Electrochemistry", "confidence": 60}
        # Solution/mixture
        if re.search(r'দ্রবণ|মিশ্রণ|ঘনত্ব|পরিমাণ', text):
            return {"topic": "Some Basic Concepts & Atomic Structure", "confidence": 55}
        # Reaction
        if re.search(r'বিক্রিয়া|হার|ক্যাটালিস্ট', text):
            return {"topic": "Chemical Kinetics & Catalysis", "confidence": 55}
        # Gas
        if re.search(r'গ্যাস|চাপ|আয়তন|তাপমাত্রা', text):
            return {"topic": "States of Matter & Gas Laws", "confidence": 55}
        # Mole/atomic
        if re.search(r'মোল|পরমাণু|অণু|সংখ্যা', text):
            return {"topic": "Some Basic Concepts & Atomic Structure", "confidence": 50}

    elif subject == "Math":
        # Vector notation
        if re.search(r'[রলশ]\^|ভেক্টর|সমতল', text):
            return {"topic": "Vectors & 3D Geometry", "confidence": 60}
        # Line equation
        if re.search(r'সরলরেখা|সরলরখা|সমীকরণ', text):
            return {"topic": "Straight Lines & Coordinate Geometry", "confidence": 55}
        # Dot product
        if re.search(r'[অ-হ]\s*\.\s*[অ-হ]', text):
            return {"topic": "Vectors & 3D Geometry", "confidence": 60}
        # Magnitude
        if re.search(r'।\s*[অ-হ]', text):
            return {"topic": "Vectors & 3D Geometry", "confidence": 55}

    return {"topic": "Unknown", "confidence": 0}


# Topic taxonomy for each subject
TOPICS = {
    "Physics": [
        "Mechanics (Kinematics, Laws of Motion, Work Energy Power)",
        "Rotational Motion & Gravitation",
        "Properties of Matter & Elasticity",
        "Heat & Thermodynamics",
        "Oscillations & Waves",
        "Electrostatics & Coulombs Law",
        "Current Electricity & Circuits",
        "Magnetic Effects of Current & Magnetism",
        "Electromagnetic Induction & AC",
        "Ray Optics & Wave Optics",
        "Modern Physics (Photoelectric, Atoms, Nuclei)",
        "Semiconductor Electronics & Communication",
    ],
    "Chemistry": [
        "Some Basic Concepts & Atomic Structure",
        "Classification of Elements & Periodicity",
        "Chemical Bonding & Molecular Structure",
        "States of Matter & Gas Laws",
        "Thermodynamics & Thermochemistry",
        "Equilibrium & Ionic Equilibrium",
        "Redox Reactions & Electrochemistry",
        "Chemical Kinetics & Catalysis",
        "Surface Chemistry & Colloids",
        "s-Block & p-Block Elements",
        "d-Block & f-Block Elements (Coordination Chemistry)",
        "Organic Chemistry Basics (Hydrocarbons, Haloalkanes)",
        "Organic Chemistry (Alcohols, Aldehydes, Ketones, Carboxylic Acids)",
        "Organic Chemistry (Amines, Polymers, Biomolecules)",
        "Environmental Chemistry & Chemistry in Everyday Life",
    ],
    "Math": [
        "Sets, Relations & Functions",
        "Trigonometric Functions & Identities",
        "Complex Numbers & Quadratic Equations",
        "Linear Inequalities & Linear Programming",
        "Permutations, Combinations & Binomial Theorem",
        "Sequences & Series",
        "Straight Lines & Coordinate Geometry",
        "Circles & Conic Sections",
        "Limits, Continuity & Differentiability",
        "Differentiation & Its Applications",
        "Integration & Its Applications",
        "Differential Equations",
        "Vectors & 3D Geometry",
        "Statistics & Probability",
        "Mathematical Reasoning",
    ],
}

LOCALAI_URL = os.getenv("LOCALAI_URL", "http://localhost:8000/v1/chat/completions")
LOCALAI_MODEL = os.getenv("LOCALAI_MODEL", "gpt-4o")


def classify_question(question_text: str, subject: str, options: list[dict] = None) -> dict:
    """Classify a single question into a topic using LocalAI."""
    topics = TOPICS.get(subject, [])
    if not topics:
        return {"topic": "Unknown", "confidence": 0}

    options_text = ""
    if options:
        options_text = "\nOptions: " + ", ".join(
            f"{o['letter']}) {o['text'][:50]}" for o in options
        )

    prompt = f"""Classify this {subject} exam question into exactly ONE topic from the list below.
Return ONLY a JSON object with "topic" (the exact topic string) and "confidence" (0-100).

Topics:
{chr(10).join(f"- {t}" for t in topics)}

Question: {question_text[:500]}{options_text}

Return JSON:"""

    try:
        resp = requests.post(
            LOCALAI_URL,
            json={
                "model": LOCALAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 200,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Extract JSON from response
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # Validate topic is in our list
            topic = result.get("topic", "Unknown")
            if topic not in topics:
                # Fuzzy match
                for t in topics:
                    if any(word.lower() in topic.lower() for word in t.split() if len(word) > 3):
                        topic = t
                        break
            return {"topic": topic, "confidence": result.get("confidence", 50)}
    except Exception as e:
        pass

    # Fallback: keyword-based classification
    return classify_by_keywords(question_text, subject)


def classify_by_math_patterns(text: str, subject: str) -> dict:
    """Classify based on math symbols and patterns in the question."""
    # Normalize garbled Bengali so patterns match
    text = normalize_bengali(text)
    # Math pattern heuristics
    patterns = {
        "Physics": {
            "Mechanics (Kinematics, Laws of Motion, Work Energy Power)": [
                r"mv\b", r"½.*mv", r"force.*mass.*accel", r"velocity", r"displacement",
                r"work.*energy", r"power.*time", r"F\s*=", r"a\s*=", r"v\s*=",
                r"বল", r"বেগ", r"ত্বরণ", r"শক্তি", r"ক্ষমতা", r"�র", r"ত্বরিত",
            ],
            "Electrostatics & Coulombs Law": [
                r"q[₁₁₂]", r"charge", r"Coulomb", r"kq", r"electric.*field",
                r"E\s*=", r"F\s*=.*q",
            ],
            "Current Electricity & Circuits": [
                r"ohm", r"resist", r"current", r"V\s*=\s*IR", r"R\s*=",
                r"circuit", r"voltmeter", r"ammeter",
                r"ধারা", r"বর্তনী", r"রোধ", r"ভোল্ট", r"অ্যামিটার",
            ],
            "Magnetic Effects of Current & Magnetism": [
                r"magnetic", r"B\s*=", r"flux", r"mu", r"solenoid",
                r"toroid", r"field.*current",
                r"চৌম্বক", r"তড়িৎ", r"ক্ষেত্র",
            ],
            "Electromagnetic Induction & AC": [
                r"induction", r"faraday", r"emf", r"AC", r"frequency",
                r"inductance", r"capacitance.*AC", r"reactance",
                r"প্রেরণ", r"তড়িৎ",
            ],
            "Ray Optics & Wave Optics": [
                r"mirror", r"lens", r"refract", r"reflect", r"angle.*incidence",
                r"critical.*angle", r"dispersion", r"interference",
                r"আয়না", r"লেন্স", r"প্রতিফলন", r"বক্রতা",
            ],
            "Modern Physics (Photoelectric, Atoms, Nuclei)": [
                r"photon", r"photoelectric", r"bohr", r"atom", r"nucle",
                r"decay", r"radioactive", r"de\s*broglie", r"wavelength.*photon",
                r"পরমাণু", r"নিউক্লিয়াস", r"কোয়ান্টাম",
            ],
        },
        "Chemistry": {
            "Chemical Bonding & Molecular Structure": [
                r"bond", r"orbital", r"hybrid", r"covalent", r"ionic",
                r"VSEPR", r"lone\s*pair",
                r"বন্ধন", r"কোভ্যালেন্ট", r"আয়নিক",
            ],
            "States of Matter & Gas Laws": [
                r"PV\s*=", r"pressure.*volume", r"ideal\s*gas", r"temperature",
                r"moles?", r"STP",
                r"গ্যাস", r"তাপমাত্রা", r"চাপ",
            ],
            "Thermodynamics & Thermochemistry": [
                r"enthalpy", r"entropy", r"delta\s*H", r"ΔH", r"heat.*reaction",
                r"Hess", r"thermodynamic",
                r"এনথালপি", r"এন্ট্রপি", r"তাপ",
            ],
            "Equilibrium & Ionic Equilibrium": [
                r"equilibrium", r"Keq", r"pH", r"buffer", r"solubility",
                r"Ksp", r"ionic.*product",
                r"সাম্যাবস্থা", r"আয়নিক",
            ],
            "Redox Reactions & Electrochemistry": [
                r"oxidation", r"reduction", r"redox", r"electrode", r"cell.*potential",
                r"E\s*=", r"electrolysis",
                r"জারণ", r"বিজারণ", r"ইলেক্ট্রোড",
            ],
            "Chemical Kinetics & Catalysis": [
                r"rate", r"order.*reaction", r"half.life", r"activation.*energy",
                r"catalyst", r"k\s*=",
                r"বিক্রিয়ার", r"হার", r"ক্যাটালিস্ট",
            ],
            "s-Block & p-Block Elements": [
                r"Na\b", r"K\b", r"Ca\b", r"group.*1", r"alkali", r"alkaline",
                r"p.block", r"periodic",
                r"মৌল", r"পর্যায়",
            ],
            "Organic Chemistry Basics (Hydrocarbons, Haloalkanes)": [
                r"CH[₂₃₄]", r"alkane", r"alkene", r"alkyne", r"halo",
                r"isomer", r"iupac", r"substitut",
                r"কার্বনিক", r"হাইড্রোকার্বন",
            ],
        },
        "Math": {
            "Trigonometric Functions & Identities": [
                r"sin", r"cos", r"tan", r"θ", r"angle", r"triangle",
                r"trigonometr", r"identity",
                r"ত্রিকোণমিতি", r"সূচক", r"কোণ",
            ],
            "Complex Numbers & Quadratic Equations": [
                r"z\s*=", r"i\s*=", r"√-1", r"complex", r"quadratic",
                r"discriminant", r"modulus",
                r"জটিল", r"সংখ্যা", r"সমীকরণ",
            ],
            "Permutations, Combinations & Binomial Theorem": [
                r"nPr", r"nCr", r"factorial", r"permut", r"combin",
                r"binomial", r"coefficient",
                r"বিন্যাস", r"সমাবেশ", r"বহুপদী",
            ],
            "Sequences & Series": [
                r"aₙ", r"Sn", r"arithmetic", r"geometric", r"series",
                r"sequence", r"common\s*diff", r"common\s*ratio",
                r"ধারা", r"শ্রেণী", r"সমান্তর", r"গাণিতিক",
            ],
            "Limits, Continuity & Differentiability": [
                r"lim", r"limit", r"→", r"∞", r"continu", r"differ",
                r"derivative", r"f'(x)",
                r"সীমা", r"ধারাবাহিকতা", r"অবকলন",
            ],
            "Differentiation & Its Applications": [
                r"dy/dx", r"∂", r"derivative", r"tangent.*line",
                r"maxima", r"minima", r"rate.*change",
                r"অবকলন", r"স্পর্শক",
            ],
            "Integration & Its Applications": [
                r"∫", r"integral", r"antideriv", r"area.*under",
                r"definite.*integral", r"dx",
                r"যোগজীকরণ", r"সমাকলন",
            ],
            "Vectors & 3D Geometry": [
                r"vec", r"→", r"\.", r"×", r"i\s*\+\s*j", r"3[dD]",
                r"direction.*cosine", r"plane", r"cross.*product",
                r"ভেক্টর", r"তল", r"দিক",
            ],
            "Statistics & Probability": [
                r"P\(", r"probability", r"mean", r"variance", r"σ", r"μ",
                r"standard.*deviation", r"Bayes",
                r"পরিসংখ্যান", r"সম্ভাবনা", r"গড়",
            ],
        },
    }

    subject_patterns = patterns.get(subject, {})
    for topic, pats in subject_patterns.items():
        for pat in pats:
            if re.search(pat, text, re.IGNORECASE):
                return {"topic": topic, "confidence": 60}

    return {"topic": "Unknown", "confidence": 0}


def classify_by_keywords(text: str, subject: str) -> dict:
    """Fallback keyword-based classification when AI is unavailable."""
    # Normalize garbled Bengali so keywords match
    text = normalize_bengali(text)
    text_lower = text.lower()

    # Also check math patterns in the text
    math_hints = classify_by_math_patterns(text, subject)
    if math_hints["confidence"] > 0:
        return math_hints

    keyword_map = {
        "Physics": {
            "Mechanics (Kinematics, Laws of Motion, Work Energy Power)": [
                "velocity", "acceleration", "force", "momentum", "kinetic energy",
                "potential energy", "work", "power", "newton", "displacement",
                "বেগ", "ত্বরণ", "বল", "গতিশক্তি", "ক্ষমতা", "কাজ",
                "ভর", "ত্বরিত", "মুহূর্ত", "স্থিতিশক্তি", "কার্য",
                "mv", "F=ma", "½mv", "ω", "α",
                "দিক", "নকশা", "কোনটি", "কোনটির", "নয়",
                "আগমন", "প্রতিফলিত", "সরণি", "পথ",
            ],
            "Rotational Motion & Gravitation": [
                "rotational", "torque", "angular", "moment of inertia", "gravity",
                "gravitational", "satellite", "orbital",
                "ঘূর্ণন", "টর্ক", "কৌণিক", "মুহূর্ত", "মাধ্যাকর্ষণ",
                "কক্ষীয়", "उपग্রহ",
            ],
            "Heat & Thermodynamics": [
                "heat", "temperature", "thermodynamics", "entropy", "enthalpy",
                "ideal gas", "kinetic theory", "calorimetry", "thermal",
                "তাপ", "তাপমাত্রা", "তাপগতিবিদ্যা", "এন্ট্রপি",
                "PV=nRT", "γ", "Cv", "Cp",
            ],
            "Electrostatics & Coulombs Law": [
                "electric charge", "coulomb", "electric field", "electric potential",
                "capacitor", "dielectric", "electrostatic",
                "বৈদ্যুতিক", "চার্জ", "কুলম্ব", "ক্যাপাসিটর",
                "q₁", "q₂", "kq",
            ],
            "Current Electricity & Circuits": [
                "current", "resistance", "voltage", "circuit", "ohm",
                "kirchhoff", "bridge", "wheatstone", "potentiometer",
                "ধারা", "প্রতিরোধ", "ভোল্টেজ", "বর্তনী", "ওহম",
                "V=IR", "R=", "I=",
            ],
            "Magnetic Effects of Current & Magnetism": [
                "magnetic", "magnetism", "solenoid", "toroid", "biot",
                "savart", "ampere", "magnetic moment",
                "চৌম্বক", "সলেনয়েড", "অ্যাম্পিয়ার",
                "B=", "μ₀",
            ],
            "Electromagnetic Induction & AC": [
                "electromagnetic induction", "faraday", "inductance", "ac",
                "alternating", "transformer", "reactance", "impedance",
                "ইলেক্ট্রোম্যাগনেটিক", "ইন্ডাকশন", "ফ্যারাডে",
                "emf", "XL", "XC",
            ],
            "Ray Optics & Wave Optics": [
                "mirror", "lens", "refraction", "reflection", "dispersion",
                "interference", "diffraction", "polarization", "optics",
                "আয়না", "লেন্স", "প্রতিসরণ", "প্রতিফলন",
                "μ=", "sin i", "sin r",
            ],
            "Modern Physics (Photoelectric, Atoms, Nuclei)": [
                "photoelectric", "photon", "bohr", "atom", "nucleus",
                "radioactive", "decay", "binding energy", "de broglie",
                "ফোটন", "পরমাণু", "নিউক্লিয়াস", "তেজস্ক্রিয়",
                "λ=", "E=hf", "λ=h/mv",
            ],
            "Semiconductor Electronics & Communication": [
                "semiconductor", "diode", "transistor", "logic gate",
                "p-n junction", "rectifier", "amplifier",
                "সেমিকন্ডাক্টর", "ডায়োড", "ট্রানজিস্টর",
            ],
        },
        "Chemistry": {
            "Some Basic Concepts & Atomic Structure": [
                "mole", "atomic", "structure", "avogadro", "stoichiometry",
                "empirical", "molecular formula",
                "মোল", "পরমাণু", "গঠন", "অ্যাভোগাড্রো",
                "দ্রবণ", "ঘনত্ব", "গ্যাস", "অণু",
                "আয়তন", "পরিমাণ",
            ],
            "Chemical Bonding & Molecular Structure": [
                "bond", "bonding", "covalent", "ionic", "hybridization",
                "vsepr", "molecular orbital", "lone pair",
                "বন্ধন", "সহস্যবন্ধন", "আয়নিক", "হাইব্রিডাইজেশন",
            ],
            "States of Matter & Gas Laws": [
                "gas", "pressure", "boyle", "charles", "ideal gas",
                "van der waals", "liquid", "solid", "crystal",
                "গ্যাস", "চাপ", "তরল", "কঠিন", "ক্রিস্টাল",
                "আয়তন", "তাপমাত্রা", "পরিমাণ",
            ],
            "Thermodynamics & Thermochemistry": [
                "thermodynamics", "enthalpy", "entropy", "gibbs",
                "heat of reaction", "hess law", "calorimetry",
                "তাপগতিবিদ্যা", "এনথালপি", "এন্ট্রপি",
                "দহন", "তাপ", "শক্তি",
            ],
            "Equilibrium & Ionic Equilibrium": [
                "equilibrium", "le chatelier", "ionic", "ph", "buffer",
                "solubility product", "hydrolysis",
                "সাম্যাবস্থা", "আয়নিক", "পিএইচ",
                "সমতা", "ক্ষরণ",
            ],
            "Redox Reactions & Electrochemistry": [
                "redox", "oxidation", "reduction", "electrochemistry",
                "electrode", "cell", "nernst", "electrolysis",
                "রেডক্স", "জারণ", "বিজারণ", "ইলেক্ট্রোকেমিস্ট্রি",
                "জারক", "বিজারক",
            ],
            "Chemical Kinetics & Catalysis": [
                "kinetics", "rate", "activation energy", "catalyst",
                "order of reaction", "half-life",
                "গতিবিদ্যা", "হার", "ক্যাটালিস্ট",
                "বিক্রিয়ার হার",
            ],
            "Surface Chemistry & Colloids": [
                "surface", "colloid", "adsorption", "emulsion",
                "পৃষ্ঠ", "কলয়েড", "শোষণ",
            ],
            "s-Block & p-Block Elements": [
                "s-block", "p-block", "alkali", "alkaline",
                "গ্রুপ 1", "গ্রুপ 2", "পিরিয়ডিক",
                "ধাতু", "মৌল",
            ],
            "Organic Chemistry Basics (Hydrocarbons, Haloalkanes)": [
                "hydrocarbon", "alkane", "alkene", "alkyne", "haloalkane",
                "isomerism", "iupac", "organic",
                "হাইড্রোকার্বন", "অ্যালকেন", "অ্যালকিন", "জৈব",
                "কার্বনিক",
            ],
            "Organic Chemistry (Alcohols, Aldehydes, Ketones, Carboxylic Acids)": [
                "alcohol", "aldehyde", "ketone", "carboxylic acid",
                "ester", "ether", "phenol",
                "মদ্য", "অ্যালডিহাইড", "কিটোন", "কার্বক্সিলিক",
            ],
        },
        "Math": {
            "Trigonometric Functions & Identities": [
                "trigonometric", "trigonometry", "sin", "cos", "tan",
                "identity", "angle", "triangle",
                "ত্রিকোণমিতি", "কোণ", "ত্রিভুজ",
                "θ", "sin²", "cos²", "tan²", "sec", "cosec", "cot",
            ],
            "Complex Numbers & Quadratic Equations": [
                "complex number", "quadratic", "discriminant", "imaginary",
                "modulus", "argument",
                "জটিল সংখ্যা", "দ্বিঘাত", "কাল্পনিক",
                "z=", "i=", "√-1", "a+bi", "re", "im",
            ],
            "Permutations, Combinations & Binomial Theorem": [
                "permutation", "combination", "binomial", "factorial",
                "arrangement", "selection",
                "বিন্যাস", "সমাবেশ", "বিনময়", "গুণিতক",
                "nPr", "nCr", "n!", "nC",
            ],
            "Sequences & Series": [
                "sequence", "series", "arithmetic", "geometric",
                "progression", "sum", "term",
                "ধারা", "ধারা", "সমান্তর", "গাণিতিক",
                "Sn", "an", "r=", "d=",
            ],
            "Straight Lines & Coordinate Geometry": [
                "straight line", "slope", "coordinate", "distance",
                "section formula", "collinear",
                "সরলরেখা", "স্থানাঙ্ক", "দূরত্ব",
                "y=mx+c", "ax+by+c", "বিন্দু",
            ],
            "Circles & Conic Sections": [
                "circle", "ellipse", "parabola", "hyperbola",
                "tangent", "normal", "chord",
                "বৃত্ত", "উপবৃত্ত", "পরাবৃত্ত", "অতিবৃত্ত",
                "x²+y²", "r²", "center",
            ],
            "Limits, Continuity & Differentiability": [
                "limit", "continuity", "differentiability", "derivative",
                "lhopital", "indeterminate",
                "সীমা", "ধারাবাহিক", "অবকলন",
                "lim", "→", "∞", "f'(x)",
            ],
            "Differentiation & Its Applications": [
                "derivative", "differentiation", "rate of change",
                "maxima", "minima", "tangent", "normal",
                "অবকলজ", "অবকলন", "সর্বোচ্চ", "সর্বনিম্ন",
                "dy/dx", "∂", "f'(x)",
            ],
            "Integration & Its Applications": [
                "integral", "integration", "antiderivative", "area",
                "definite integral", "substitution",
                "ইন্টিগ্রেল", "যোগজীকরণ", "ক্ষেত্রফল",
                "∫", "dx", "∫dx",
            ],
            "Differential Equations": [
                "differential equation", "ode", "pde",
                "সমকলীকরণ", "অংশিক",
                "dy/dx", "y'", "y''",
            ],
            "Vectors & 3D Geometry": [
                "vector", "dot product", "cross product", "3d",
                "direction cosine", "plane", "line in 3d",
                "ভেক্টর", "সমতল", "ত্রিমাত্রিক",
                "i^", "j^", "k^", "→", "a.b", "a×b",
            ],
            "Statistics & Probability": [
                "probability", "statistics", "mean", "variance",
                "standard deviation", "bayes", "conditional",
                "সম্ভাবনা", "পরিসংখ্যান", "গড়", "পরিবর্তনশীলতা",
                "P(", "σ²", "μ", "E(X)",
            ],
        },
    }

    topics = keyword_map.get(subject, {})
    best_topic = "Unknown"
    best_score = 0

    for topic, keywords in topics.items():
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            # Exact match
            if kw_lower in text_lower:
                score += 2
            # Partial match for garbled text (at least 4 chars)
            elif len(kw_lower) >= 4:
                # Check if first 4 chars match
                if kw_lower[:4] in text_lower:
                    score += 1
                # Check if any 3-char substring matches
                for i in range(len(kw_lower) - 2):
                    if kw_lower[i:i+3] in text_lower:
                        score += 0.5
                        break
        if score > best_score:
            best_score = score
            best_topic = topic

    confidence = min(best_score * 15, 100) if best_score > 0 else 0
    if confidence > 0:
        return {"topic": best_topic, "confidence": confidence}

    # Fallback: math content extraction (vectors, formulas)
    math_result = classify_by_math_content(text, subject)
    if math_result["confidence"] > 0:
        return math_result

    # Fallback: context-based rules
    ctx_result = classify_by_context(text, subject)
    if ctx_result["confidence"] > 0:
        return ctx_result

    return {"topic": "Unknown", "confidence": 0}


def classify_batch(questions: list[dict], subject: str) -> list[dict]:
    """Classify a batch of questions in a single API call."""
    topics = TOPICS.get(subject, [])
    if not topics or not questions:
        return [{"topic": "Unknown", "confidence": 0}] * len(questions)

    # Build numbered question list
    q_lines = []
    for i, q in enumerate(questions):
        text = q.get("question_text", "")[:300]
        opts = q.get("options", [])
        if opts:
            opts_str = " | ".join(f"{o['letter']}){o['text'][:30]}" for o in opts)
            text += f" [{opts_str}]"
        q_lines.append(f"{i+1}. {text}")

    prompt = (
        "Classify each {subject} exam question into exactly ONE topic from the list.\n"
        "Questions may be in Bengali (বাংলা) or English — classify based on the topic, not the language.\n"
        "Return a JSON array of objects with: index (1-based), topic (exact string), confidence (0-100).\n"
        "\n"
        "Topics:\n{topics}\n"
        "\n"
        "Questions:\n{questions}\n"
        "\n"
        "Return JSON array:"
    ).format(
        subject=subject,
        topics="\n".join(f"- {t}" for t in topics),
        questions="\n".join(q_lines),
    )

    try:
        resp = requests.post(
            LOCALAI_URL,
            json={
                "model": LOCALAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 1500,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Extract JSON array - handle markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", content, re.DOTALL)
        if not json_match:
            json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1) if json_match.lastindex else json_match.group()
            results = json.loads(json_str)
            out = []
            for r in results:
                topic = r.get("topic", "Unknown")
                # Check if topic is in list, otherwise try fuzzy match
                if topic not in topics:
                    matched = False
                    for t in topics:
                        # Check if any significant word matches
                        topic_words = set(w.lower() for w in topic.split() if len(w) > 3)
                        t_words = set(w.lower() for w in t.split() if len(w) > 3)
                        if topic_words & t_words:
                            topic = t
                            matched = True
                            break
                    if not matched:
                        topic = "Unknown"
                out.append({"topic": topic, "confidence": r.get("confidence", 50)})
            # Pad if AI returned fewer results
            while len(out) < len(questions):
                out.append({"topic": "Unknown", "confidence": 0})
            return out[:len(questions)]
    except Exception as e:
        # Debug: print error
        import sys
        print(f"  AI error: {e}", file=sys.stderr)

    # Fallback: keyword classification
    return [classify_by_keywords(q.get("question_text", ""), subject) for q in questions]


def classify_all_questions(parsed_data: list[dict], use_ai: bool = True, batch_size: int = 5) -> list[dict]:
    """Classify all questions in parsed data. Keywords first, AI for leftovers."""
    import time

    # First pass: detect subject for Unknown questions
    for file_data in parsed_data:
        file_subject = file_data.get("subject", "Unknown")
        for q in file_data.get("questions", []):
            if q.get("subject") == "Unknown":
                text = q.get("question_text", "")
                normalized = normalize_bengali(text)
                detected = _detect_subject_from_text(normalized)
                if detected != "Unknown":
                    q["subject"] = detected
                elif file_subject != "Unknown":
                    # Fallback to file-level subject
                    q["subject"] = file_subject

    # Second pass: keyword classification for all
    unclassified = []
    for fi, file_data in enumerate(parsed_data):
        for qi, q in enumerate(file_data.get("questions", [])):
            text = q.get("question_text", "")
            subject = q.get("subject", "Unknown")
            result = classify_by_keywords(text, subject)
            q["topic"] = result["topic"]
            q["confidence"] = result["confidence"]
            if result["topic"] == "Unknown" and subject != "Unknown":
                unclassified.append((fi, qi, q))

    # Second pass (enhanced): try math content + context for remaining Unknowns
    still_unclassified = []
    for fi, qi, q in unclassified:
        text = q.get("question_text", "")
        subject = q.get("subject", "Unknown")
        # Try math content classification (uses decoded [সধঃয:] blocks)
        result = classify_by_math_content(text, subject)
        if result["topic"] != "Unknown":
            q["topic"] = result["topic"]
            q["confidence"] = result["confidence"]
            continue
        # Try context rules
        result = classify_by_context(text, subject)
        if result["topic"] != "Unknown":
            q["topic"] = result["topic"]
            q["confidence"] = result["confidence"]
            continue
        still_unclassified.append((fi, qi, q))

    # Third pass: AI classification for unclassified (one at a time with retries)
    if use_ai and still_unclassified:
        print(f"  {len(still_unclassified)} questions unclassified, trying AI...")
        for fi, qi, q in still_unclassified:
            text = q.get("question_text", "")
            subject = q.get("subject", "Unknown")
            result = classify_single_ai(text, subject)
            if result["topic"] != "Unknown":
                q["topic"] = result["topic"]
                q["confidence"] = result["confidence"]
            time.sleep(0.5)  # Rate limit

    return parsed_data


def classify_single_ai(text: str, subject: str) -> dict:
    """Classify a single question using AI."""
    topics = TOPICS.get(subject, [])
    if not topics:
        return {"topic": "Unknown", "confidence": 0}

    prompt = f"""Classify this {subject} question into ONE topic.
Return ONLY JSON: {{"topic": "...", "confidence": 0-100}}

Topics: {', '.join(topics)}

Question: {text[:400]}

JSON:"""

    for attempt in range(3):
        try:
            resp = requests.post(
                LOCALAI_URL,
                json={
                    "model": LOCALAI_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 200,
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            # Extract JSON object
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                topic = result.get("topic", "Unknown")
                if topic not in topics:
                    # Fuzzy match
                    for t in topics:
                        if any(w.lower() in topic.lower() for w in t.split() if len(w) > 3):
                            topic = t
                            break
                return {"topic": topic, "confidence": result.get("confidence", 50)}
        except Exception:
            time.sleep(2)

    return {"topic": "Unknown", "confidence": 0}


def _detect_subject_from_text(text: str) -> str:
    """Detect subject from question text using Bengali + English keywords."""
    text_lower = text.lower()

    # Math patterns - check first (most distinctive)
    math_patterns = [
        r'\(\s*\d',                # Coordinates (x, y) - starts with digit
        r'\d+\s*\)',               # Ends with digit)
        r'সরলরখা',                 # Straight line
        r'সমতল',                   # Plane
        r'বিন্দু',                 # Point
        r'ভেক্টর',                 # Vector
        r'ডাইভারজ',               # Divergence
        r'কর্ণ',                   # Diagonal
        r'sin|cos|tan',            # Trig
        r'∫|∫dx|dy/dx',           # Calculus
        r'x²|y²|r²',              # Algebra
        r'সমীকরণ',                 # Equation
        r'ফাংশন',                  # Function
        r'শ্রেণী',                  # Series
        r'ধারা',                   # Sequence
        r'বৃত্ত',                   # Circle
        r'পরাবৃত্ত',                # Parabola
        r'উপবৃত্ত',                # Ellipse
        r'ল\^',                    # Vector notation (garbled)
        r'সমিখক',                  # Direction cosine (garbled)
        r'পাদ',                    # Foot of perpendicular
        r'সরল',                    # Straight (partial)
        r'সধঃয',                   # Coordinate (garbled)
        r'র\^',                    # Vector r-hat (garbled)
        r'ল\^',                    # Vector l-hat (garbled)
        r'শ\^',                    # Vector s-hat (garbled)
        r'কণ',                     # Particle
        r'কণা',                    # Particle (alternate)
        r'সামািরক',                 # Cross product (garbled)
        r'অভীক',                    # Direction (garbled)
        r'পিত',                     # Point (garbled)
        r'গাম',                     # Line (garbled)
        r'ফল',                      # Product/Result
        r'ভর',                      # Mass (Math context: weight)
        r'কাণ',                     # Distance (garbled)
        r'দূর',                     # Distance
        r'সমান',                    # Equal
        r'লি',                      # Line (garbled)
        r'ই',                       # Vector i (garbled)
        r'অ',                       # Vector a (garbled)
        r'মান',                     # Value
        r'মধকার',                   # Between (garbled)
        r'মধবতী',                   # Midpoint (garbled)
    ]

    # Physics patterns
    physics_patterns = [
        r'বল',                     # Force
        r'ভর',                     # Mass
        r'বেগ',                    # Velocity
        r'ত্বরণ',                  # Acceleration
        r'শক্তি',                  # Energy
        r'ক্ষমতা',                 # Power
        r'মুহূর্ত',                # Moment
        r'কর্ণ',                   # (can be both - check context)
        r'পল',                     # Pulley
        r'বীম',                    # Beam
        r'রাইডার',                 # Rider
        r'বাল',                    # Ball
        r'তল',                     # Surface
        r'ঘর্ষণ',                  # Friction
        r'মাধ্যাকর্ষণ',            # Gravity
        r'তাপ',                    # Heat
        r'তাপমাত্রা',              # Temperature
        r'দিক',                    # Direction
        r'সরণি',                   # Path
        r'নকা চালা',               # Motion (garbled)
        r'নকশা',                   # Motion (garbled)
        r'আগত',                    # Moving
        r'পিতফিল',                 # Reflected (garbled)
        r'কাট',                    # Cut
        r'টর্ক',                    # Torque
        r'কৌণিক',                  # Angular
        r'ঘূর্ণন',                  # Rotation
        r'বাতাস',                   # Wind
        r'সিনিহ',                   # Collision (garbled)
        r'সংঘর্ষ',                  # Collision
        r'সামািরক',                 # Cross product (garbled)
        r'বিদ্যুৎ',                 # Electricity
        r'বিদু',                    # Electricity (garbled)
        r'িবদু',                    # Electricity (garbled)
        r'চৌম্বক',                  # Magnetic
    ]

    # Chemistry patterns
    chemistry_patterns = [
        r'মোল',                    # Mole
        r'বন্ধন',                  # Bond
        r'বিক্রিয়া',              # Reaction
        r'সাম্যাবস্থা',            # Equilibrium
        r'অম্ল',                   # Acid
        r'ক্ষার',                  # Base
        r'জারণ',                   # Oxidation
        r'বিজারণ',                 # Reduction
        r'গ্যাস',                  # Gas
        r'দ্রবণ',                  # Solution
        r'ইলেক্ট্রোড',            # Electrode
        r'দবণ',                    # Solution (garbled)
        r'মিশ্ৰণ',                 # Mixture (garbled)
        r'ঘনমাা',                  # Concentration (garbled)
        r'লাব',                    # Lab (garbled)
    ]

    scores = {'Math': 0, 'Physics': 0, 'Chemistry': 0}

    for pat in math_patterns:
        if re.search(pat, text_lower):
            scores['Math'] += 2

    for pat in physics_patterns:
        if re.search(pat, text_lower):
            scores['Physics'] += 1

    for pat in chemistry_patterns:
        if re.search(pat, text_lower):
            scores['Chemistry'] += 1

    best = max(scores, key=scores.get)
    if scores[best] >= 1:
        return best
    return 'Unknown'


if __name__ == "__main__":
    import sys

    # Parse args: skip flags like --no-ai
    input_file = "parsed_questions.json"
    use_ai = "--no-ai" not in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            input_file = arg
            break

    print(f"Loading questions from: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Classifying {sum(f.get('question_count', 0) for f in data)} questions (AI={'on' if use_ai else 'off'})...")
    data = classify_all_questions(data, use_ai=use_ai)

    output_file = "classified_questions.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved to: {output_file}")
