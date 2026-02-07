from VoiceServer import main


def test_parse_supabase_public_url():
    url = "https://example.supabase.co/storage/v1/object/public/user-audio/abc/voice.m4a"
    assert main.parse_supabase_object_from_url(url) == ("user-audio", "abc/voice.m4a")


def test_parse_supabase_signed_url():
    url = "https://example.supabase.co/storage/v1/object/sign/user-audio/voice.m4a?token=abc"
    assert main.parse_supabase_object_from_url(url) == ("user-audio", "voice.m4a")


def test_parse_supabase_url_returns_none_for_other_hosts():
    assert main.parse_supabase_object_from_url("https://example.com/audio.m4a") is None
