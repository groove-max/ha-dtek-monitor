"""Operator announcements are independent of publication and physical power.

Only the known announcement container is read. FAQ text, hidden address hints,
precautionary advice and uncertain territorial matches never suspend an address.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import re
import time

from .schedule import KYIV_TZ

NOTICE_STATES = ('none', 'emergency', 'stabilization', 'mixed', 'notice')
MAX_AGE = timedelta(minutes=10)


class _Announcement(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.containers = self.texts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        parent = self.stack[-1] if self.stack else ('', False, False, False)
        modal = attrs.get('id') == 'modal-attention'
        text = 'm-attention__text' in attrs.get('class', '').split() and (modal or parent[1])
        self.containers += int(modal)
        self.texts += int(text)
        state = (tag, modal or parent[1], text or parent[2], parent[3] or tag in ('script', 'style'))
        if state[2] and tag in ('p', 'br', 'li', 'div'):
            self.parts.append('\n')
        if tag not in ('br', 'hr', 'img', 'input', 'meta', 'link', 'wbr', 'source', 'area', 'embed'):
            self.stack.append(state)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                if self.stack[i][2] and tag in ('p', 'li', 'div'):
                    self.parts.append('\n')
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][2] and not self.stack[-1][3]:
            self.parts.append(data)


def extract_announcement(html):
    parser = _Announcement()
    parser.feed(html)
    # An absent/changed selector or challenge page is not proof of no notice.
    if parser.containers != 1 or parser.texts != 1:
        raise ValueError('Announcement container could not be verified')
    text = '\n'.join(' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip())
    if len(text) > 8000:
        raise ValueError('Announcement exceeds supported size')
    return text


def _normalize(text):
    return ' '.join(text.lower().replace('ʼ', "'").replace('’', "'").split())


def _clauses(text):
    # Keep date dots intact and retain explicit paragraph/line boundaries.
    return [s.strip() for s in re.split(r'\n|(?<!м\.)(?<!с\.)(?<=[.!?;])\s+', text) if s.strip()]


def _kind(sentence):
    s = _normalize(sentence)
    if re.search(r'уникну|можлив|можуть|будь ласка|не (?:діють|застосовуються|введено) (?:екстрен|аварійн)|скасован|відмінено|скасовано|діяли|вчора|раніше|планується|очікується', s):
        return None
    if re.search(r'графік(?:и)?\s+не\s+(?:ді[єю]|застосов)', s):
        return 'emergency'
    active = re.search(r'діють|введен|запроваджен|застосован|застосовують|тривають|продовжуються', s)
    if re.search(r'(?:екстрен|аварійн)\w*\s+відключен', s) and (active or re.search(r'\s[-–—]\s', s)):
        return 'emergency'
    if active and re.search(r'стабілізаційн\w*\s+відключен', s):
        return 'stabilization'
    if re.search(r'фіксуються відключення|відсутнє (?:світло|електропостачання)', s):
        return 'local'
    return None


def _city_match(sentence, city):
    if re.search(r'частин|окрем|крім|деяк|район|громад', _normalize(sentence)):
        return False
    name = re.sub(r'^(?:м\.?|місто|с\.?|село|смт\.?)\s+', '', _normalize(city or ''))
    aliases = {'дніпро': ('дніпрі',), 'київ': ('києві',), 'одеса': ('одесі',)}
    forms = (name, *aliases.get(name, ())) if name else ()
    return any(re.search(r'(?:^|[;,:]\s*)(?:у|в)\s+(?:м\.\s*|місті\s+)?'+re.escape(form)+r'(?=\s|[,;:–—-]|$)', _normalize(sentence)) for form in forms)


def _global(sentence):
    s = _normalize(sentence)
    if re.search(r'частин|окрем|деяк|район|громад|міст|населен|решт|крім|винят', s):
        return False
    if re.search(r'(?:всій|усій|вс[іь]ому|ус[іь]ому)\s+(?:території\s+)?(?:област|регіон|києв)', s):
        return True
    # Only unqualified declarations; unknown place names are never global.
    s = re.sub(r'^за (?:наказом|командою|розпорядженням) нек укренерго\s+', '', s)
    s = re.sub(r'^(?:сьогодні|завтра|\d{1,2}\.\d{1,2}(?:\.\d{4})?)[,\s]+', '', s)
    s = re.sub(r'^з 00:00 до 24:00\s+', '', s)
    return bool(re.match(r'(?:діють|введено|запроваджено|застосовуються|тривають|графік)', s)) and not re.search(r'\b(?:у|в|на|для)\s+(?!області\b)', s)


def _date_matches(sentence, day, checked):
    s = _normalize(sentence)
    times = re.findall(r'(?<!\d)\d{1,2}:\d{2}', s)
    if times and times != ['00:00', '24:00']:
        return False  # Partial-day windows need explicit intervals, not a daily guess.
    if re.search(r'вчора|післязавтра|до завершення|від .* до ', s):
        return False
    dates = re.findall(r'(?<!\d)(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?(?!\d)', s)
    if dates:
        # Multiple dates/ranges are deliberately not guessed.
        return len(dates) == 1 and tuple(map(int, dates[0][:2])) == (day.day, day.month) and (not dates[0][2] or int(dates[0][2]) == day.year)
    if 'завтра' in s:
        return day == checked.date()+timedelta(days=1)
    return day == checked.date()


@dataclass(frozen=True)
class ProviderNotice:
    text: str
    checked_at: datetime | None
    source_url: str
    error: str | None = None

    @property
    def state(self):
        if self.error or self.checked_at is None:
            return None
        if not self.text:
            return 'none'
        kinds = {_kind(s) for s in _clauses(self.text)} - {None}
        if len(kinds) > 1:
            return 'mixed'
        return next(iter(kinds)) if kinds and 'local' not in kinds else 'notice'

    @property
    def revision(self):
        return hashlib.sha256((self.text+'|'+str(self.error)).encode()).hexdigest()

    def attributes(self, city, now=None, *, day_offset=0):
        now = now or datetime.now(timezone.utc)
        fresh = self.checked_at is not None and -5 <= (now-self.checked_at).total_seconds() < MAX_AGE.total_seconds() and not self.error
        fresh = fresh and self.checked_at.astimezone(KYIV_TZ).date() == now.astimezone(KYIV_TZ).date()
        day = now.astimezone(KYIV_TZ).date()+timedelta(days=day_offset)
        applies, scope = None, 'unverified'
        if fresh:
            if not self.text:
                # Silence is not an official confirmation that a timetable applies.
                scope = 'no_notice'
            else:
                rows = [(s, _kind(s)) for s in _clauses(self.text)]
                relevant = [(s,k) for s,k in rows if k and _date_matches(s,day,self.checked_at.astimezone(KYIV_TZ))]
                # A date/exception in a separate heading may qualify the next
                # sentence. Never silently discard it and assume "today/all".
                if any(not k and re.search(
                    r'\d{1,2}\.\d{1,2}|\d{1,2}:\d{2}|сьогодні|завтра|вчора|крім|винят|частин|район|громад',
                    _normalize(s),
                ) for s,k in rows):
                    relevant = []
                local = [(s,k) for s,k in relevant if _city_match(s, city)]
                if local and {k for _,k in local} == {'emergency'}:
                    applies, scope = False, 'city'
                elif any(k == 'emergency' and _global(s) for s,k in relevant) and not any(k == 'local' or (k and not _global(s)) for s,k in relevant):
                    applies, scope = False, 'operator'
                elif any(k == 'stabilization' and _global(s) for s,k in relevant) and not any(k in ('emergency','local') for _,k in rows):
                    applies, scope = True, 'operator'
        return {
            'provider_notice_state': self.state if fresh else 'unavailable',
            'provider_notice_text': self.text,
            'provider_notice_valid_until': (min(self.checked_at + MAX_AGE, (self.checked_at.astimezone(KYIV_TZ) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)).isoformat() if self.checked_at else None),
            'provider_notice_checked_at': self.checked_at.isoformat() if self.checked_at else None,
            'provider_notice_source': self.source_url,
            'provider_notice_error': self.error,
            'provider_notice_scope': scope,
            'provider_notice_interpretation': 'text_rules',
            'provider_notice_revision': self.revision,
            'schedule_applies': applies,
            'schedule_applicability_date': day.isoformat(),
        }


class NoticeCache:
    """HA/operator-scoped, bounded polling; missing data never means all-clear."""
    def __init__(self, url, *, clock=time.monotonic):
        self.url, self.clock = url, clock
        self.value = ProviderNotice('', None, url, 'not_checked')
        self.next_check = 0.0
        self.lock = asyncio.Lock()

    def capture(self, html):
        try:
            self.value = ProviderNotice(extract_announcement(html), datetime.now(timezone.utc), self.url)
        except ValueError:
            self.value = ProviderNotice(self.value.text, self.value.checked_at, self.url, 'unsupported_notice_format')
        self.next_check = self.clock()+300

    async def get(self, refresh):
        async with self.lock:
            if self.clock() < self.next_check:
                return self.value
            try:
                async with asyncio.timeout(20):
                    await refresh()
            except Exception:
                self.value = ProviderNotice(self.value.text, self.value.checked_at, self.url, 'notice_request_failed')
                self.next_check = self.clock()+60
            return self.value


def notice_attributes(coordinator, now=None, *, day_offset=0):
    notice = getattr(coordinator, 'provider_notice', None)
    if not isinstance(notice, ProviderNotice):
        return {}  # Backward-compatible providers/test doubles do not advertise this contract.
    attrs = notice.attributes(coordinator.address.city, now, day_offset=day_offset)
    attrs['schedule_applicability_days'] = {
        a['schedule_applicability_date']: a['schedule_applies']
        for offset in (0, 1)
        for a in [notice.attributes(coordinator.address.city, now, day_offset=offset)]
    }
    return attrs
