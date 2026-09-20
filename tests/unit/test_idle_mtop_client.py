from src.services.idle_mtop_client import (
    extract_item_id_from_link,
    mtop_sign,
)


def test_mtop_sign_known_vector():
    token = "cc94cd3faaf92877acfaa80a0c3f1ba7"
    t = "1786023034440"
    app_key = "34839810"
    data = '{"itemId":"1023226360868"}'
    assert mtop_sign(token, t, app_key, data) == "61f6f22d42303f84a0a6c9d0750ebf9d"


def test_extract_item_id_from_pc_link():
    link = "https://www.goofish.com/item?id=1023226360868&spm=a21ybx"
    assert extract_item_id_from_link(link) == "1023226360868"


def test_extract_item_id_from_fleamarket():
    link = "fleamarket://awesome_detail?itemId=1023226360868&id=1023226360868"
    assert extract_item_id_from_link(link) == "1023226360868"
