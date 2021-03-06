'''Given a kanji token and its reading, try to split the reading by kanji.

TODO:
    - suport for Unicode composing.
    - we overshoot a bit; okurigana won't filter for kunyomi (so that e.g. にゅうり will match 入り).
    We also don't test the next charager when trying for sokuon, e.g. こく.か → こっか.
'''

import regex as re

from yomisplit.yomi import ONYOMI, KUNYOMI
from yomisplit.joyokanji import JOYO_ONYOMI, JOYO_KUNYOMI

class UnknownKanji(ValueError):
    def __init__(self, kanji):
        self.kanji = kanji
    def __str__(self):
        return("Readings for kanji '%s' are not known to library." % self.kanji)

class UnknownReading(ValueError):
    def __init__(self, kanji, reading):
        self.kanji = kanji
        self.reading = reading
    def __str__(self):
        return("Reading '%s' for kanji '%s' is not known to library." % (self.reading, self.kanji))

"""Equivalence classes of Japanese bound morphemes.

Any way a word may change ortographically at the start.  Include:
    - sequential "voicing" (rendaku), including /h/ → /b/ (か→が、は→ば);
    - /h/ → /p/ (handaku) (は→ぱ)
    - yotsugana homographs: つ → づ → ず, ち → ぢ → じ
"""
DAKUON = {
'か' : '[かが]',
'き' : '[きぎ]',
'く' : '[くぐ]',
'け' : '[けげ]',
'こ' : '[こご]',
'さ' : '[さざ]',
'し' : '[しじ]',
'す' : '[すず]',
'せ' : '[せぜ]',
'そ' : '[そぞ]',
'た' : '[ただ]',
'ち' : '[ちぢじ]',
'つ' : '[つづず]',
'て' : '[てで]',
'と' : '[とど]',
'は' : '[はばぱ]',
'ひ' : '[ひびぴ]',
'ふ' : '[ふぶぷ]',
'へ' : '[へべぺ]',
'ほ' : '[ほぼぽ]',
}

def japanese_matchreg(hiragana):
    '''Builds regexp to match hiragana strings according to Japanese phonology.

    The returned regexp tests whether another hiragana string is 'the same' as
    the one provided, including in this category derivations from Japanese
    morpho-phonological processes: sequential 'voicing' (rendaku) as well as
    gemination (sokuon).
    
    That is, it adds 'dakuten, 'handakuten, and small-tsu', so that:
        (TODO: doctest)

    Note: it doesn't anchor for start and end of string, so unless you do, it
    will match substrings.
        
    '''
    matchreg = ''

    first = hiragana[0]
    if first in DAKUON.keys():
        matchreg += DAKUON[first]
    else:
        matchreg += first

    matchreg += hiragana[1:-1] # skips last

    if len(hiragana) > 1:
        last = hiragana[-1]
        # sokuon processing
        if last in ['つ', 'ち', 'く']:
            matchreg += '[%sっ]?' % last
        else:
            matchreg += last

    return(matchreg)

def japanese_match(hiragana1, hiragana2):
    '''True if the two hiragana strings may be derived by Japanese phonology.

    Tests whether the two hiragana strings are 'the same', including in this
    category derivations from Japanese morpho-phonological processes:
    sequential 'voicing' (rendaku) as well as gemination (sokuon).

    That is, it adds 'dakuten', 'handakuten', and 'small-tsu', so that:
        (TODO: doctest)

    Wrapper on japanese_matchreg.
    '''

    reg = re.compile('^' + japanese_matchreg(hiragana1) + '$')
    return(reg.match(hiragana2))
            

def yomi_matchreg(kanjistring):
    """Builds regexp that matches possible known readings of kanjistring.

    Use the regexp to match a reading later, in hiragana.  The resulting match
    will be separated by match groups, one for each source character.  So, for
    example, to find which part of the reading correspond to the second
    character in '断定', see the match_obj.group(2) (or, equivalently,
    .groups()[1]).

    The groups will also be named, so you can use .groups('定') or
    .groupdict().  If any character is repeated, the group name will be ch +
    '2', ch + '3' etc.

    TODO: docs

    """
    matchreg = ''

    # used to handle repetition character, '々'
    prevch = None
    prevreg = None

    count = {}

    for ch in kanjistring:

        yomis = []
        yomis = []

        if ch in ONYOMI.keys():
            yomis += ONYOMI[ch]

        if ch in KUNYOMI.keys():
            yomis += KUNYOMI[ch]

        if yomis:
            # heuristic to prefer longer matches
            yomis.sort(key=len, reverse=True)
            yomis = [japanese_matchreg(y) for y in yomis]
            reg = '|'.join(yomis)
        elif ch == '々':
            if prevch:
                reg = prevreg
            else:
                raise(ValueError('Repetition character 々 following nothing'))
        else:
            # assumes character is okurigana or punct; must match as-is
            reg = re.escape(ch)
            # raise(UnknownKanji(ch))

        if ch in count.keys():
            count[ch] = count[ch] + 1
            groupname = ch + repr(count[ch])
        else:
            count[ch] = 1
            groupname = ch

        if re.match("(\W|\d)$", ch):
            # non-'alphabetic' chars (i.e. punctuation, digits) can't be groupname
            matchreg += '(%s)' % reg
        else:
            # matches kanji, kana
            matchreg += '(?P<%s>%s)' % (groupname, reg)

        prevch = ch
        prevreg = reg

    matchreg += '$'
    return(re.compile(matchreg))

def canonical_reading(kanji, foundreading):
    """From a found reading for a kanji, find its canonical form and type.

    E.g.:
        >>> canonical_reading('花', 'ばな')
        ('はな', 'Kun')
    """


    if kanji in ONYOMI.keys():
        for creading in ONYOMI[kanji]:
            if japanese_match(creading, foundreading):
                return(creading, 'On')
    if kanji in KUNYOMI.keys():
        for creading in KUNYOMI[kanji]:
            if japanese_match(creading, foundreading):
                return(creading, 'Kun')
    else:
        raise(UnknownKanji(kanji))

    raise(UnknownReading(kanji, foundreading))


def yomidict(kanji, reading):
    m = re.match(yomi_matchreg(kanji), reading)
    if (not m):
        raise(UnknownReading(kanji, reading))
    return(m.groupdict())

i_to_u = {
    'い': 'う',
    'き': 'く',
    'し': 'す',
    'ち': 'つ',
    'に': 'ぬ',
    'ひ': 'ふ',
    'み': 'む',
    'り': 'る',
}
# returns True if reading is found in joyo tables
def is_joyo(kanji, reading):
    if kanji in JOYO_ONYOMI:
        if reading in JOYO_ONYOMI[kanji]:
            return True
    if kanji in JOYO_KUNYOMI:
        if reading in JOYO_KUNYOMI[kanji]:
            return True
        else:
            if len(reading) > 1 and reading[-1] in 'いきしちにひみり':
                ureading = reading[:-1] + i_to_u[reading[-1]]
                if ureading in JOYO_KUNYOMI[kanji]:
                    return True

            # needed because joyo table has no information about okurigana
            # boundaries
            for kun in JOYO_KUNYOMI[kanji]:
                if kun.startswith(reading):
                    return(True)

    return False

kanji_re = re.compile("\p{Han}")
def guess_split(majiribun, reading):
    kanjis=[]
    matchreg_greedy=''
    matchreg_nongreedy=''
    for char in majiribun:
        if kanji_re.match(char):
            kanjis.append(char)
            matchreg_greedy += "(\p{Hiragana}+)"
            matchreg_nongreedy += "(\p{Hiragana}+?)"
        else:
            matchreg_greedy += re.escape(char)
            matchreg_nongreedy += re.escape(char)

    m = re.match(matchreg_greedy + '$', reading)
    if m:
        yomis = m.groups()

        yomis_nongreedy = re.match(matchreg_nongreedy + '$', reading).groups()
        if yomis != yomis_nongreedy:
            # Ambiguous!
            return None
        d = {}
        for idx in range(0, len(kanjis)):
            d[kanjis[idx]] = yomis[idx]
        return(d)

def yomisplit(kanjiword, reading):
    pass
