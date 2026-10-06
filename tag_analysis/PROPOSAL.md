# Project Proposal

## 1. A tentative topic of your presentation

**Listening to the Long Now: Chinese Chart-Listener Behaviour Across Years**

This project uses publicly retrievable toplist metadata from QQ
Music (seven weekly charts, ~340 weekly issues, ~137 000 song-week
rows) and three cross-region current snapshots (NetEase, Apple
Music CN, Apple Music US) to ask how Chinese mainstream-music
chart behaviour drifted across the late-2010s and early-2020s, and
whether that drift is detectable from chart-history features alone.
We focus on chart-listener behaviour (rotation speed, new-entry
rate, star concentration, "old catalogue" share, version-normalised
track-id flow) rather than audio content itself. The headline
result is a set of three statistically significant changepoints
(2019, 2020, 2022, p < 0.001, piecewise-linear BIC + permutation
test) that line up with documented structural shifts in Chinese
music consumption: the Douyin takeover, the COVID-19
stay-at-home period, and the post-2022 platform / genre
ecosystem split.

## 2. One to two data science questions you are going to answer

**Q1.** Across 2018-2024, do QQ Music's seven public weekly
toplists show systematic, statistically significant regime shifts
in chart behaviour (rotation speed, weekly unique-song count,
cross-chart correlation structure), and if so, which years mark
those shifts?

**Q2.** Do the catalogue-freshness and star-concentration
profiles of QQ, NetEase, Apple Music CN, and Apple Music US, on
the same day, diverge in a way that helps interpret QQ's
changepoints as platform-conditional vs. market-wide?

## 3. A description of your proposed project (within 300 words)

We study whether Chinese mainstream-music chart behaviour shows
measurable regime shifts between 2018 and 2024, using publicly
retrievable metadata from QQ Music's seven weekly toplists
(`u.y.qq.com/cgi-bin/musicu.fcg`, no login, ~340 weekly issues,
~137 000 song-week rows). The dataset covers the Hot Songs, Online
Songs, Mainland, Rap, EDM, Guofeng, and Douyin Hit charts.

**Why important.** Chinese streaming is the world's largest
music market, yet year-over-year *audience-behaviour* drift has
rarely been quantified at the chart-history level. Three
real-world events (Douyin's rise in 2019, COVID-19 nationwide
stay-at-home in 2020, and the post-2022 ecosystem split) should
each leave a structural fingerprint on charts; we ask whether that
fingerprint is detectable.

**Difficulties.** QQ's public API clamps `period` outside 2018W30-
2024W52; per-song play-counts require login (`code=500003`).
Weekly-history cross-platform validation is impossible because
every comparable platform (NetEase, Spotify Charts, Apple Music,
Kugou, Douyin, Bilibili, Last.fm) either lacks a public historical
endpoint or requires login. We therefore (a) anchor findings in
QQ's rich weekly series, and (b) use current snapshots from three
other platforms for cross-region structural comparison only.

**Existing works.** Western-music chart-evolution studies
(Serra 2012; Mauch 2015) use audio features; Chinese-music studies
emphasise metadata, lyrics, and recommendation systems. We combine
these perspectives on Chinese data.

**Data available.** QQ Music public toplist (137K rows);
NetEase, Apple Music CN/US current snapshots (~550 rows). All
publicly retrievable, no login, no audio download.