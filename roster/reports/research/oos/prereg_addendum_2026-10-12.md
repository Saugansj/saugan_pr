# Addendum to prereg_2026-10-12.md (sha256 6b0b8454...), written 2026-10-12 23:55 IST, before any result was computed

While downloading, the pmxt archive turned out to lack the BTC 5m/15m markets on some days (checked: 2026-06-15 and
2026-06-21 have 0 rows for them; 05-17, 05-31, 06-10, 07-05, 07-20 have them). history.pm_fast writes an empty file for
such an hour. Clarification of "a day with missing archive hours is excluded": an hour with zero rows for our markets
counts as missing (research/oos/evaluate.py has_books). Nothing else changes.
