"""Convert integers to Thai and English words for TTS announcements."""

# Thai number components
_ONES_TH = ["", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_TENS_TH = ["", "สิบ", "ยี่สิบ", "สามสิบ", "สี่สิบ", "ห้าสิบ",
            "หกสิบ", "เจ็ดสิบ", "แปดสิบ", "เก้าสิบ"]

# English number components
_ONES_EN = ["", "one", "two", "three", "four", "five",
            "six", "seven", "eight", "nine", "ten",
            "eleven", "twelve", "thirteen", "fourteen", "fifteen",
            "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS_EN = ["", "", "twenty", "thirty", "forty", "fifty",
            "sixty", "seventy", "eighty", "ninety"]


def to_thai(n: int) -> str:
    """Convert integer (0-999) to Thai words."""
    if n == 0:
        return "ศูนย์"
    if n < 0 or n > 999:
        raise ValueError(f"Number {n} out of supported range (0-999)")

    hundreds = n // 100
    tens = (n % 100) // 10
    ones = n % 10

    result = ""

    if hundreds:
        result += _ONES_TH[hundreds] + "ร้อย"

    if tens:
        result += _TENS_TH[tens]

    if ones:
        # In Thai, 1 in the ones place after a tens digit is spoken as เอ็ด
        if ones == 1 and tens > 0:
            result += "เอ็ด"
        else:
            result += _ONES_TH[ones]

    return result


def to_english(n: int) -> str:
    """Convert integer (0-999) to English words."""
    if n == 0:
        return "zero"
    if n < 0 or n > 999:
        raise ValueError(f"Number {n} out of supported range (0-999)")

    hundreds = n // 100
    remainder = n % 100
    tens = remainder // 10
    ones = remainder % 10

    parts = []

    if hundreds:
        parts.append(f"{_ONES_EN[hundreds]} hundred")

    if remainder:
        if remainder < 20:
            parts.append(_ONES_EN[remainder])
        else:
            word = _TENS_EN[tens]
            if ones:
                word += f" {_ONES_EN[ones]}"
            parts.append(word)

    return " ".join(parts)


def to_tts_text(n: int, language: str = "th") -> str:
    """Return TTS announcement text for a queue number.

    Args:
        n: Queue number (integer value, not padded string)
        language: 'th', 'en', or 'th+en'
    """
    if language == "th":
        return f"หมายเลขคิวที่ {to_thai(n)}"
    elif language == "en":
        return f"Queue number {to_english(n)}"
    elif language == "th+en":
        return f"หมายเลขคิวที่ {to_thai(n)}"  # Edge-tts handles one language per call
    else:
        return f"หมายเลขคิวที่ {to_thai(n)}"
