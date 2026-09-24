import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.domain.xhs_note_parse import parse_note_html
from src.services.monitor_accounts import list_accounts, sync_goofish_files, upsert_account
from src.services.xhs_note_storage import add_note, collect_notes, list_notes
from src.services.xhs_storage import add_product
from src.xhs_note_collector import NoteFetch


def test_existing_state_files_register_as_goofish(tmp_path, offline_db):
    state = tmp_path / "state"
    state.mkdir()
    (state / "shop-a.json").write_text("{}", encoding="utf-8")
    (state / "xhs").mkdir()
    (state / "xhs" / "main.json").write_text("{}", encoding="utf-8")
    sync_goofish_files(str(state))
    upsert_account("xhs", "main", "xhs/main.json")
    goofish = list_accounts("goofish")
    xhs = list_accounts("xhs")
    assert [row["name"] for row in goofish] == ["shop-a"]
    assert [row["name"] for row in xhs] == ["main"]
    assert "main" not in {row["name"] for row in goofish}


def test_note_link_cannot_enter_product_table(offline_db):
    try:
        add_product("https://www.xiaohongshu.com/discovery/item/6921871c000000001e034287")
    except ValueError as exc:
        assert "笔记" in str(exc)
    else:
        raise AssertionError("note link was stored as a product")


def test_same_day_overwrites_and_keeps_missing_fields(offline_db, tmp_path):
    state = tmp_path / "state"
    (state / "xhs").mkdir(parents=True)
    (state / "xhs" / "main.json").write_text(json.dumps({"cookies": []}), encoding="utf-8")
    upsert_account("xhs", "main", "xhs/main.json")
    note = add_note("https://www.xiaohongshu.com/explore/6921871c000000001e034287")
    moment = datetime(2026, 9, 24, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    def opener(_path, _url):
        html = '"likedCount": 3, "collectedCount": 2, "commentCount": 1, "title": "标题"'
        return NoteFetch(200, _url, html)

    calls = {"count": 0}

    def counting(_path, url):
        calls["count"] += 1
        return opener(_path, url)

    first = collect_notes(note["id"], state_dir=str(state), opener=counting, gap_seconds=0, now=moment)
    assert first["saved"] == 1

    def partial(_path, url):
        return NoteFetch(200, url, '"likedCount": 8, "title": "标题"')

    second = collect_notes(note["id"], state_dir=str(state), opener=partial, gap_seconds=0, now=moment)
    assert second["saved"] == 1
    listed = list_notes()
    assert len(listed) == 1
    assert listed[0]["metrics"]["liked_count"] == 8
    assert listed[0]["metrics"]["collected_count"] == 2
    assert listed[0]["metrics"]["view_count"] is None
    assert listed[0]["deltas"]["liked_count"] is None


def test_missing_xhs_account_does_not_open_browser(offline_db):
    add_note("https://www.xiaohongshu.com/explore/6921871c000000001e034287")
    called = {"count": 0}

    def opener(_path, _url):
        called["count"] += 1
        return NoteFetch(200, _url, '"likedCount": 1')

    summary = collect_notes(opener=opener, gap_seconds=0)
    assert called["count"] == 0
    assert summary["error"] == "没有可用的小红书登录"
    assert list_notes()[0]["last_status"] == "login_required"


def test_note_html_leaves_view_empty():
    fields = parse_note_html('"likedCount": 4, "collectedCount": 5, "commentCount": 6')
    assert fields.view_count is None
    assert fields.liked_count == 4
