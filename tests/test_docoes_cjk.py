"""DocOES in Japanese and Chinese: four parser bugs a translated telling met, each in the natural phrasing the
translators first had to avoid (wave 3, lane D1; fixed in fabula round F0)."""

from __future__ import annotations

from enough import docoes as D

EN = """# Guide

## 1. Things

A **volume** is a top-level folder in the store. A **plain volume** holds the text you keep for good.

- **shelf** — where the volumes stand, in rows.

## 2. More

The end.
"""

ZH = """# 指南

## 1. 东西

**卷**是仓库里的一个顶层文件夹。**普通卷**装着你要永远留着的文字。

- **书架** —— 卷站着的地方，一排一排。

## 2. 更多

完。
"""

JA = """# ガイド

## 1. もの

**巻**は保管庫の最上位フォルダです。**素の巻**は、ずっと持っておきたいテキストのためのものです。

- **棚** — 巻が並んで立つ場所。

## 2. もっと

おわり。
"""


def _terms(text: str, lang: str) -> dict:
    cat = D.enumerate_markdown(text, doc_id="doc/guide", lang=lang, source_path=f"guide.{lang}.md",
                               reference_text=EN, version="1")
    return {n["id"]: n for n in cat["nodes"] if n["type"] == "term"}


def test_the_lead_strip_stops_at_the_first_bold_in_unspaced_cjk():
    # "**卷**是……。**普通卷**装着……": the meaning starts right after the first bold, not after the second.
    zh = _terms(ZH, "zh")["T:term/volume"]
    assert zh["atem"].startswith("是仓库里的一个顶层文件夹"), zh["atem"]
    ja = _terms(JA, "ja")["T:term/volume"]
    assert ja["atem"].startswith("は保管庫の最上位フォルダです"), ja["atem"]


def test_the_separator_takes_the_chinese_double_dash_whole():
    # "- **书架** —— …": the summary and the atem must not open with the second half of the dash.
    shelf = _terms(ZH, "zh")["T:term/shelf"]
    assert shelf["summary"].startswith("卷站着的地方"), shelf["summary"]
    assert not shelf["atem"].startswith("—"), shelf["atem"]
    m = D._BULLET_TERM.match("**书架** —— 卷站着的地方。")
    assert m.group("sep") == "——" and m.group("rest") == "卷站着的地方。"


def test_a_japanese_section_reference_links_after_a_particle():
    # "ヘルプセンターのセクション 13.4": の is a word character, and the lookbehind guards the Latin words only.
    assert D._refs_in("全体は、ヘルプセンターのセクション 13.4 にあります。", {}, own_p=False).sections == ["13.4"]
    # The Latin words keep their boundary: "subsection 2" is not "section 2".
    assert D._refs_in("see subsection 2", {}, own_p=False).sections == []


def test_a_japanese_section_list_joined_by_to_links_every_number():
    # "セクション 12.4 と 12.5": と joins two numbers, as "and" does.
    assert D._refs_in("（セクション 12.4 と 12.5）", {}, own_p=False).sections == ["12.4", "12.5"]
    assert D._refs_in("セクション 4 と 5、7", {}, own_p=False).sections == ["4", "5", "7"]
