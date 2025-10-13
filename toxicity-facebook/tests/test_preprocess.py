from preprocess.clean import clean_text


def test_clean_text_removes_url_and_mentions():
    text = "Hey @user cek https://contoh.com sekarang 😀"
    cleaned = clean_text(text)
    assert "http" not in cleaned
    assert "@" not in cleaned
    assert "😀" not in cleaned
    assert "cek" in cleaned
