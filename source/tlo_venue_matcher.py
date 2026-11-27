"""Read-only, standard-library venue recognizer. No network or database mutation."""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION
import re
import sqlite3
import unicodedata
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable


def ascii_text(s: str) -> str:
    return unicodedata.normalize('NFKD', s.translate(str.maketrans({'’':"'", '‘':"'", '–':'-', '—':'-', 'ß':'ss', 'ø':'o', 'Ø':'O', 'ł':'l', 'Ł':'L'}))).encode('ascii', 'ignore').decode()


def key(s: str) -> str:
    return re.sub('[^a-z0-9]', '', ascii_text(s).lower())


def exact(s: str) -> str:
    return ' '.join(ascii_text(s).casefold().split())


TOKEN = re.compile(r'[^\W_]+', re.UNICODE)
DATE = re.compile(r'(?<!\w)(?:\d{4}|[xX]{4})[-./](?:\d{2}|[xX]{2})[-./](?:\d{2}|[xX]{2})(?!\w)')
# A hard boundary is not an instruction to delete the rest of the input.
NOISE = re.compile(r'\b(?:\d{2,4}(?:\.\d+)?\s*(?:FM|AM|MHz|kHz)|(?:FM|AM)\s*\d{2,4}(?:\.\d+)?|SBD|AUD|FLAC\d*|SHN|MP3|WAV|24[- ]bit|16[- ]bit|matrix|remaster(?:ed)?|(?:early|late|first|second|third|\d+(?:st|nd|rd|th))\s+(?:show|set)|(?:set|disc|cd|copy|alt|source)\s*\d+|soundboard|soundcheck|rehearsal|interview|(?:live\s+)?broadcast|radio\s+(?:show|special)|(?:live\s+)?concert|featuring|feat\.?|with\s+(?:special\s+)?guest|opening\s+act|unknown|unidentified|possibly|tour|anniversary|annual|benefit|tribute|festival|band|quartet|quintet|trio|orchestra|ensemble|session[s]?|\d{1,2}:\d{2}\s*(?:am|pm)?)\b', re.I)
ROOM = frozenset('auditorium theater theatre ballroom lounge pavilion amphitheater amphitheatre arena stadium studio studios soundstage room chapel stage salon hall basement gym gymnasium fieldhouse cafe club tavern pub bar restaurant bandshell quad'.split())
GENERIC = ROOM | frozenset('the a an main big small indoor outdoor student music concert performing arts center centre activity activities athletic recreation community civic municipal city town local national state university college school sports field house cultural dining memorial general reception event events campus union building facility complex auditorium theater theatre park gardens fairgrounds'.split())
STOP = frozenset('and or but for from with featuring live show recording presents featuring by of in on at near via artist band group orchestra quartet trio ensemble unknown various'.split())
SEPARATOR = re.compile(r'[,;|@/\\\[\](){}]|\s[-–—]\s')
STRENGTH = {'context_required': 0, 'provisional': 1, 'supported': 2, 'strong': 3}


@dataclass(frozen=True)
class Candidate:
    venue: str                 # display name, never silently modernized
    anchor: str                # reference family, not necessarily display name
    start: int
    end: int
    matched: str
    strength: str
    reason: str
    score: int
    institution: str = ''
    ambiguous: bool = False
    inferred: bool = False
    source: str = ''


class VenueMatcher:
    """Load immutable indexes once per inventory worker/process; safe for concurrent reads."""
    def __init__(self, database: str | Path):
        uri = Path(database).resolve().as_uri() + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True)) as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version != 1:
                raise ValueError(f'Unsupported venues.sqlite schema {version}')
            rows = db.execute('SELECT spelling, normalized_key, display_name, anchor, strength, kind, institution FROM names').fetchall()
            self.locations = defaultdict(set)
            for k, city, state, display in db.execute('SELECT normalized_key, city_key, state_key, display_name FROM locations'):
                if not k.isdigit() and not key(display).isdigit():
                    self.locations[k, city, state].add(display)
        self.index = defaultdict(list)
        for row in rows:
            if not any(key(v).isdigit() for v in row[:4]):
                self.index[row[1]].append(row)
        self.prefixes = {k[:i] for k in self.index for i in range(1, len(k)+1)}
        self.max_key = max(map(len, self.index), default=0)

    @staticmethod
    def _spans(text, terms):
        for term in terms:
            if term and term.strip():
                # Accept punctuation/spacing variants; caller supplies known artist/city names.
                pieces = TOKEN.findall(term)
                if pieces:
                    pat = r'(?<!\w)' + r'[\W_]+'.join(map(re.escape, pieces)) + r'(?!\w)'
                    yield from (m.span() for m in re.finditer(pat, text, re.I))

    def candidates(self, text: str, *, city: str = '', state: str = '', artist: str = '',
                   boundaries: Iterable[str] = (), explicit: bool = False,
                   source: str = '', corroboration: Iterable[str] = ()) -> list[Candidate]:
        """Pass venue-bearing text, not an entire multi-line setlist or filesystem path.
        For folder descriptions with a date, search after the last recognized date.
        boundaries: caller-identified artists, geographic phrases, tags, etc.
        explicit: text is an explicit venue field rather than free text.
        """
        if not text or not text.strip():
            return []
        # Preserve character offsets in the original input; fold token-by-token.
        dates = list(DATE.finditer(text))
        lo = dates[-1].end() if dates and not explicit else 0
        toks = [m for m in TOKEN.finditer(text, lo)]
        if not toks:
            return []
        blocked = list(self._spans(text, [artist, *boundaries]))
        geographic = list(self._spans(text, [city, state]))
        # Only trailing geography is a hard boundary. A venue can itself contain a city/state.
        for a,b in geographic:
            if a >= lo and (not text[b:].strip(' ,.-()[]') or any(x <= a and y >= a for x,y in blocked)
                or (city and state and key(text[a:]).startswith(key(city)+key(state)))
                or (not text[b:].strip(' ,.-()[]') or NOISE.match(text[b:].lstrip(' ,.-()[]')))):
                blocked.append((a,b))
        # The common trailing City ST followed by recording info case.
        if city and state:
            blocked += list(self._spans(text, [city+' '+state]))
        noise = [m.span() for m in NOISE.finditer(text,lo)]
        confirm = {key(x) for x in corroboration if x}
        def overlaps(a,b,spans): return any(a<y and b>x for x,y in spans)
        def edge(s): return s.strip(' \t\r\n,;:@|/\\-–—()[]{}')
        def clean_edge(a,b):
            return not edge(text[lo:a]) and not edge(text[b:])
        result = []
        for i,t in enumerate(toks):
            k = ''
            for j in range(i,len(toks)):
                u=toks[j]
                if j>i:
                    gap=text[toks[j-1].end():u.start()]
                    if re.search(r'[;|/\\\n\r]',gap) and not (gap=='/' and toks[j-1].group().isdigit() and u.group().isdigit()): break
                k += key(u.group())
                if not k or k not in self.prefixes: break
                if k not in self.index: continue
                a,b=t.start(),u.end()
                if overlaps(a,b,blocked): continue
                raw=text[a:b]
                # A venue-looking substring immediately followed by an artist-group suffix is not an anchor.
                if not explicit and re.match(r'\s+(?:(?:jazz|blues|rock|string)\s+)?(?:band|quartet|quintet|trio|orchestra|ensemble|group)\b',text[b:],re.I): continue
                records=self.index[k]
                # Exact spacing/punctuation before compact key; canonical matching can span a hyphen.
                matches=[r for r in records if exact(r[0])==exact(raw)]
                # Preserve genuine leading/trailing apostrophes when part of a recognized spelling.
                if not matches:
                    aa=a-1 if a>lo and text[a-1] in "'’" else a
                    bb=b+1 if b<len(text) and text[b] in "'’" else b
                    matches=[r for r in records if exact(r[0])==exact(text[aa:bb])]
                    if matches: a,b,raw=aa,bb,text[aa:bb]
                chosen=matches or records
                loc=self.locations.get((k,key(city),key(state)),set()) if city and state else set()
                # Location resolves spelling collisions only; it must not replace a historical display name.
                if len({r[2] for r in chosen})>1 and loc:
                    local=[r for r in chosen if r[2] in loc]
                    if local: chosen=local
                displays={r[2] for r in chosen}
                ambiguous=len(displays)>1
                for spelling,_,display,anchor,strength,kind,inst in chosen:
                    if kind=='legacy_compact' and (not explicit and not clean_edge(a,b)): continue
                    # Known legitimate names may contain an otherwise blocked word (e.g. Festival Hall).
                    # Do not accept a noisy match merely because the dirty source was in the database.
                    if overlaps(a,b,noise) and kind not in ('master','alias','historical','room','room_full'): continue
                    full=clean_edge(a,b)
                    structural=bool(set(TOKEN.findall(raw.lower())) & ROOM)
                    if strength=='context_required' and not (explicit or full or loc or k in confirm or inst or structural or (city and state and not edge(text[lo:a]) and any(x>=b for x,y in blocked))): continue
                    if ambiguous: continue
                    if all(w.lower() in GENERIC for w in TOKEN.findall(raw)) and not (explicit and strength=='strong'): continue
                    score=30+min(50,len(k))+STRENGTH.get(strength,1)*4+(12 if matches else 0)+(12 if full else 0)+(8 if explicit else 0)+(18 if k in confirm else 0)+(7 if loc else 0)+(8 if kind=='room_full' else 0)
                    result.append(Candidate(display,anchor,a,b,raw,strength,kind,score,inst,False,False,source))
        # Controlled bidirectional expansion. Only one adjacent bounded room phrase; never cross noise/location.
        # An independently recognized room may be combined with a campus anchor, without changing either spelling.
        expanded=[]
        for c in result:
            if c.reason in {'room_full','room'}: continue
            # Limit inferred expansion to institutions, strong/supported anchors, or corroborated compound text.
            for side in (-1,1):
                adjacent=[m for m in toks if (m.end()<=c.start if side<0 else m.start()>=c.end)]
                adjacent=adjacent[-4:] if side<0 else adjacent[:4]
                for n in range(1,len(adjacent)+1):
                    part=adjacent[-n:] if side<0 else adjacent[:n]
                    a,b=(part[0].start(),c.end) if side<0 else (c.start,part[-1].end())
                    pa,pb=part[0].start(),part[-1].end()
                    if overlaps(pa,pb,blocked+noise): continue
                    gap=text[pb:c.start] if side<0 else text[c.end:pa]
                    if re.search(r'[;|/\\\r\n]',gap) or SEPARATOR.search(text[pa:pb]): continue
                    words=[key(m.group()) for m in part]
                    if any(w in STOP for w in words): continue
                    phrase=text[pa:pb]
                    if re.match(r'\s+(?:(?:jazz|blues|rock|string)\s+)?(?:band|quartet|quintet|trio|orchestra|ensemble|group)\b',text[b:],re.I): continue
                    # Named room suffix or numbered room/studio/stage; generic 'main hall' alone is insufficient.
                    numbered=(len(words)==2 and words[0] in {'room','studio','stage','hall'} and bool(re.fullmatch(r'\d{1,4}[a-z]?',words[1])))
                    named=(len(words)>=2 and words[-1] in ROOM and any(w not in GENERIC and not w.isdigit() for w in words[:-1]))
                    qualified=(len(words)==2 and words[0] in {'outdoor','indoor'} and words[1] in {'amphitheater','amphitheatre','arena','stage'})
                    corroborated=key(text[a:b]) in confirm
                    if not (corroborated or ((c.institution or c.strength in {'strong','supported'}) and (named or numbered or qualified))): continue
                    # Avoid absorbing a longer unexplained prefix; only consider a bounded phrase.
                    outer=text[lo:pa] if side<0 else text[pb:]
                    outerspan=(lo,pa) if side<0 else (pb,len(text))
                    if edge(outer) and not (overlaps(*outerspan,blocked+noise) or SEPARATOR.search(outer) or corroborated): continue
                    # Do not extend across a separately recognized unrelated room unless it is adjacent and same campus.
                    nearby=[q for q in result if q.start>=pa and q.end<=pb and q.institution and q.institution!=c.institution]
                    if nearby: continue
                    room_matches=[q for q in result if q.start==pa and q.end==pb and q.reason=='room' and (not c.institution or q.institution==c.institution)]
                    room_display=room_matches[0].venue if room_matches else phrase
                    display=(room_display+' '+c.venue if side<0 else c.venue+' '+room_display)
                    expanded.append(replace(c,venue=display,start=a,end=b,matched=text[a:b],reason='corroborated_expansion' if corroborated else 'structural_expansion',score=c.score+min(25,len(key(phrase)))+10,inferred=not corroborated))
        result+=expanded
        # Deduplicate candidates; retain scores and offsets for caller diagnostics.
        unique={}
        for c in result:
            k=(c.start,c.end,c.venue)
            if k not in unique or c.score>unique[k].score: unique[k]=c
        return sorted(unique.values(),key=lambda c:(-c.score,-(c.end-c.start),c.start,c.venue.casefold()))

    def match(self,text: str, **kwargs) -> Candidate | None:
        found=self.candidates(text,**kwargs)
        if not found: return None
        best=found[0]
        # A score tie for different names must not be broken alphabetically.
        if any(x.score==best.score and x.venue!=best.venue for x in found[1:]): return None
        return best

    def match_sources(self, sources: Iterable[tuple[str,str,bool]], **kwargs) -> Candidate | None:
        """Sources are (label, text, explicit_venue_field). Input order is source precedence.
        A later source may extend a compatible earlier candidate, never silently modernize it.
        Caller retains its existing fallback when this returns None.
        """
        rows=list(sources)
        found=[]
        for label,text,explicit in rows:
            hints=[t for l,t,e in rows if e and l!=label]
            c=self.match(text,source=label,explicit=explicit,corroboration=hints,**kwargs)
            if c: found.append(c)
        if not found: return None
        best=found[0]
        for c in found[1:]:
            if key(c.venue)==key(best.venue): continue
            # Only strictly compatible expansions; a shared reference family is NOT compatibility.
            if best.institution and c.institution==best.institution and key(best.venue) in key(c.venue) and len(key(c.venue))>len(key(best.venue)):
                best=c
        return best
