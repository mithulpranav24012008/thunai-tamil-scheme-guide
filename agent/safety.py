"""SAFETY: what must stop the agents and hand off to a human. Code owns this; the model cannot change it.

red_flags(text) returns the names of the dangers it found, or [] when there are none.

People don't type the textbook phrase. They write spoken Tamil (நெஞ்சு வலிக்குது, not மார்பு வலி),
Tamil in English letters (nenju vali, moochu vida mudiyala), and English idioms (my chest is killing
me). So each danger is a set of patterns in three scripts, not one phrase. A missed emergency is
worse than a false alarm, so the patterns lean wide, but a few words that are dangerous only in
context ("stroke", "dying", "heart attack") must be happening now, not a past event or a figure of speech.

Tamil script is matched as stems inside the text, because Tamil joins endings onto words
(வலிக்குது, வலிக்கிறது, வலி). English and Tanglish are matched on word boundaries.
"""
from __future__ import annotations

import re

# ── Tamil script: stems, spoken and written forms ──────────────────────────
TAMIL = {
    "chest pain": ["மார்பு வலி", "மார்புவலி", "நெஞ்சு வலி", "நெஞ்சுவலி", "நெஞ்சு வலிக்"],
    "can't breathe": ["மூச்சு விட முடிய", "மூச்சு வாங்கு", "மூச்சு திண", "மூச்சுத் திண", "மூச்சு இல்ல", "மூச்சு விட கஷ்ட"],
    "suicide or self-harm": ["தற்கொலை", "சாகணும்", "சாக வேண்டும்", "சாகப் போற", "சாகப்போற", "செத்துடலாம்", "செத்துடுவேன்",
                             "செத்துப் போகணும்", "செத்துருவேன்", "வாழ பிடிக்கல", "வாழ விரும்பவில்லை", "உயிரை மாய்", "முடிச்சுக்கணும்"],
    "overdose": ["தூக்க மாத்திரை", "நிறைய மாத்திரை", "மாத்திரை நிறைய", "அதிக மாத்திரை", "மாத்திரை முழுங்கி"],
    "unconscious": ["மயக்க", "மயங்கி", "நினைவில்லை", "நினைவு இல்ல", "பேச்சு மூச்சு இல்ல"],
    "severe bleeding": ["ரத்தம் வருகிறது", "ரத்தம் நிக்கல", "ரத்தம் நிற்கவில்லை", "ரத்தம் கொட்டு", "ரத்தம் வாந்தி", "ரத்த வாந்தி"],
    "poisoning or bite": ["விஷம்", "பாம்பு கடி"],
    "dying": ["இறக்கிறேன்"],
    "vomiting": ["வாந்தி எடுக்கிறது"],
    "medicine change": ["மருந்து மாற்ற", "இரட்டிப்பு", "மாத்திரையை நிறுத்த"],
}

# ── Tanglish: Tamil typed in English letters, with the spellings people use ───
TANGLISH = {
    "chest pain": [r"\bnenju ?vali", r"\bmaarbu ?vali", r"\bmarbu ?vali"],
    "can't breathe": [r"\bmoo?chu (vida|vida) mudiy", r"\bmoo?chu (vaang|vang|thinar|thenar|thinar)", r"\bmoo?chu illa"],
    "suicide or self-harm": [r"\bsaa?ga?(num|nam|poren|poga)\b", r"\bseth(u|th)?(dalam|udalam|uralam|ralam|uruven|ruven|uduven)\b",
                             r"\bth?a[rt]+ ?kolai\b", r"\bvaazha? pidikkala"],
    "overdose": [r"\b(thookka|thooka|thukka|tukka) ?(mathirai|maathirai|matharai)", r"\bniraya (mathirai|maathirai|tablets?|pills)",
                 r"\b(mathirai|maathirai) niraya"],
    "unconscious": [r"\bmayang", r"\bmayakkam"],
    "severe bleeding": [r"\b(ratham|raththam|rattham) (nikkala|nikala|nikkavillai|kottu|varuthu|vanthi)"],
    "poisoning or bite": [r"\b(paambu|pambu) ?kadi", r"\bvisham"],
}

# ── English ────────────────────────────────────────────────────────────────
ENGLISH = {
    "chest pain": [r"\bchest (pains?|is (killing|hurting)|hurts|tightness|is tight)"],
    "can't breathe": [r"\b(can't|cannot|can not|unable to|struggling to|hard to) (breathe|catch (my|his|her|their) breath)",
                      r"\bnot breathing\b", r"\bshort(ness)? of breath\b", r"\bgasping\b"],
    "suicide or self-harm": [r"\bsuicid", r"\bkill (myself|himself|herself)\b", r"\bwant to die\b", r"\bend (it all|my life)\b",
                             r"\bdon't want to live\b", r"\btake my (own )?life\b", r"\bhurt myself\b"],
    "overdose": [r"\boverdos", r"\btoo many (pills|tablets)\b", r"\btook (a lot of|lots of|all (my|the)) (pills|tablets|medicine)"],
    "unconscious": [r"\bunconscious\b", r"\bpassed out\b", r"\bnot responding\b", r"\bfainted\b"],
    "severe bleeding": [r"\b(severe|heavy) bleeding\b", r"\bbleeding (heavily|badly|a lot)\b", r"\b(won't|will not) stop bleeding\b",
                        r"\bbleeding (won't|will not) stop\b"],
    "poisoning or bite": [r"\bpoison", r"\bdrank (pesticide|kerosene|acid)\b", r"\bsnake ?bite\b", r"\bbitten by a snake\b"],
    "stroke": [r"\b(having|is having|has) a stroke\b", r"\bstroke (right )?now\b", r"\bface is drooping\b", r"\bface drooping\b",
               r"\bslurred speech\b"],
    "medicine change": [r"\bshould i (take|stop) (this |these |my |the )?(\w+ )?(medicine|medication|tablets?|pills?|dose|drug)",
                        r"\bwhat medicine should i take\b", r"\b(change|double|skip) (my |the )?dose\b", r"\bextra dose\b",
                        r"\bstop taking (my |the )?(\w+ ){0,3}(medicine|medication|tablets?|pills?)"],
    "diagnosis": [r"\bdiagnose (me|my)\b", r"\bis this cancer\b"],
}

# Dangerous only when happening now: these patterns are skipped if the text says it was in the past.
NOW_ONLY = {
    "heart attack": [r"\bheart attack\b"],
    "seizure": [r"\bseizures?\b", r"\bhaving fits\b"],
}
PAST = re.compile(r"\b(last (year|month|week)|years? ago|months? ago|weeks? ago|ago|history of|in (19|20)\d\d|previously|survived)\b")

# "dying" is a figure of speech as often as not: "dying to get a scholarship", "my phone is dying".
# \b before "dying" so that "studying" is not read as dying.
DYING = re.compile(r"((?:[\w']+\s+){0,3})\bdying\b(?!\s+(?:to|for|of laughter)\b)")
NOT_ALIVE = re.compile(r"\b(phone|battery|laptop|plant|plants|car|bike|light|business|shop|crops?)\b")


def normalise(text: str) -> str:
    t = str(text or "").lower()
    t = t.replace("’", "'").replace("‘", "'").replace("`", "'")
    t = re.sub(r"\bcant\b", "can't", t)
    t = re.sub(r"\bwont\b", "won't", t)
    t = re.sub(r"\bdont\b", "don't", t)
    return re.sub(r"\s+", " ", t).strip()


def red_flags(text: str) -> list[str]:
    t = normalise(text)
    found: list[str] = []

    def hit(name):
        if name not in found:
            found.append(name)

    for name, stems in TAMIL.items():
        if any(s in t for s in stems):
            hit(name)
    for table in (TANGLISH, ENGLISH):
        for name, patterns in table.items():
            if any(re.search(p, t) for p in patterns):
                hit(name)
    if not PAST.search(t):
        for name, patterns in NOW_ONLY.items():
            if any(re.search(p, t) for p in patterns):
                hit(name)
    for m in DYING.finditer(t):
        if not NOT_ALIVE.search(m.group(1)):
            hit("dying")
            break
    return found
