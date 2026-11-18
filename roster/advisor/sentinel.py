"""Role 25 sports-news sentinel (WP4-D, task 4.7). Standalone: wired into the advisor process later.

Keyword prefilter -> one LLM call per matching item -> CautionSignal pulls on the affected games.
Cautious only: it pulls (shrink_factor 0.0) or resumes (action "none"); it never emits a size or a price.
A pull resumes only on a sharp observation timestamped after the latest pulling news for that game, never on time.
"""
import re
import unicodedata

from advisor.contracts import CautionSignal, Gateway

ROLE = "25-sports-news"
KINDS = ["injury", "suspension", "lineup", "weather", "postponement", "other"]
SCHEMA = {"type": "object", "required": ["material", "team", "kind"],
          "properties": {"material": {"type": "boolean"}, "team": {"type": "string"},
                         "kind": {"type": "string", "enum": KINDS}}}
KEYWORDS = ["out", "injury", "injured", "doubtful", "questionable", "suspended", "ruled out", "scratched", "lineup",
            "line-up", "starting xi", "postponed", "delayed", "weather", "abandoned"]


def norm(text: str) -> str:
    """Case-, accent- and whitespace-insensitive form: 'Atlético  Madrid' -> 'atletico madrid'."""
    s = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()
    return " ".join(s.split())


def _words(phrases) -> re.Pattern:
    alts = sorted({re.escape(norm(p)) for p in phrases if p.strip()}, key=len, reverse=True)
    return re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)")


KEYWORD_RE = _words(KEYWORDS)


class Sentinel:
    def __init__(self, gateway: Gateway, maps: list[dict]):
        """maps: MarketMap records (event_key, home, away, start_ms; optional 'players' list)."""
        self.gateway = gateway
        self.start = {m["event_key"]: m["start_ms"] for m in maps}
        self.names: dict[str, set[str]] = {}            # normalized name -> event_keys
        self.teams: dict[str, set[str]] = {}            # event_key -> display team names (for the prompt)
        for m in maps:
            for n in (m["home"], m["away"], *m.get("players", ())):
                self.names.setdefault(norm(n), set()).add(m["event_key"])
            self.teams.setdefault(m["event_key"], set()).update((m["home"], m["away"]))
        self.name_re = _words(self.names) if self.names else None
        self.active: dict[str, CautionSignal] = {}      # event_key -> pull in force
        self.news_ms: dict[str, int] = {}               # event_key -> latest pulling news time
        self.verdicts: dict[str, dict[str, bool]] = {}  # event_key -> {source_family: material}

    def match(self, item: dict) -> list[str]:
        """Event keys this item names, or [] if it names no tracked team/player or has no keyword."""
        text = norm(item.get("text", ""))
        if self.name_re is None or not KEYWORD_RE.search(text):
            return []
        return sorted({k for n in self.name_re.findall(text) for k in self.names[n]})

    def on_news(self, item: dict) -> list[tuple[CautionSignal, dict]]:
        """item: text, source_family, published_ms, recv_ms, url. Returns (pull, refresh request) per affected game."""
        keys = self.match(item)
        if not keys:
            return []
        teams = sorted({t for k in keys for t in self.teams[k]})
        prompt = ("Sports news item (public text). Candidate teams: " + ", ".join(teams) + ".\n"
                  "Is this material to the match result (key player out, lineup change, suspension, weather or "
                  "postponement)? Answer JSON {material, team, kind}.\n\nNEWS:\n" + item["text"][:2000])
        family = item.get("source_family", "unknown")
        data = self._ask(prompt)
        t = max(item.get("published_ms", 0), item.get("recv_ms", 0))
        out = []
        for k in keys:
            fam = self.verdicts.setdefault(k, {})
            if data is not None:
                fam[family] = fam.get(family, False) or data["material"]  # a family that said material stays so
            disagree = len(set(fam.values())) > 1
            if data is None:
                reason = f"llm-failure, {family}"
            elif data["material"]:
                reason = f"{data['kind']}, {family}"
            elif k in self.active and disagree:  # non-material changes nothing, except flagging the standing pull
                reason = self.active[k].reason.split(";")[0]
            else:
                continue
            if data is None or data["material"]:
                self.news_ms[k] = max(self.news_ms.get(k, t), t)
            if disagree:
                reason += "; sources disagree"
            sig = CautionSignal(role=ROLE, scope=k, action="pull", shrink_factor=0.0, expires_ms=self.start[k],
                                resume_requires_fresh_observation=True, reason=reason)
            self.active[k] = sig
            out.append((sig, {"event_key": k, "priority": "news"}))
        return out

    def on_sharp_observation(self, scope: str, obs_ms: int) -> CautionSignal | None:
        """Resume signal only if `scope` is pulled and obs_ms is strictly after its latest news time."""
        if scope not in self.active or obs_ms <= self.news_ms[scope]:
            return None
        del self.active[scope], self.news_ms[scope]
        self.verdicts.pop(scope, None)
        return CautionSignal(role=ROLE, scope=scope, action="none", shrink_factor=1.0, expires_ms=self.start[scope],
                             resume_requires_fresh_observation=False, reason=f"fresh sharp observation at {obs_ms}")

    def _ask(self, prompt: str) -> dict | None:
        """One vendor; any failure, timeout or schema mismatch -> None (the caller pulls)."""
        try:
            res = self.gateway.complete(ROLE, prompt, SCHEMA, vendors=1)
            d = res[0].data if res and res[0].ok else None
            ok = (isinstance(d, dict) and isinstance(d.get("material"), bool) and isinstance(d.get("team"), str)
                  and d.get("kind") in KINDS)
            return d if ok else None
        except Exception:
            return None
