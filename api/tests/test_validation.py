"""Input validation: plain-text fields are cleaned of invisible/control characters and reject markup."""

import pytest
from pydantic import ValidationError

from app.routers.documents import _safe_display_name
from app.schemas import BotCreate, BotUpdate, ChatRequest, clean_text

RLO = "‮"  # right-to-left override: makes "invoice<RLO>fdp.exe" display as "invoiceexe.pdf"


# --- clean_text --------------------------------------------------------------------------

def test_clean_text_strips_control_and_bidi_characters():
    assert clean_text(f"Ac\x00me\x07 {RLO}Bot⁦") == "Acme Bot"


def test_clean_text_keeps_newlines_and_tabs_only_when_multiline():
    assert clean_text("a\nb\tc", multiline=True) == "a\nb\tc"
    assert clean_text("a\nb\tc") == "a b c"


def test_clean_text_trims_and_normalizes_unicode():
    # "e" + combining acute (2 code points) becomes the single precomposed "é".
    assert clean_text("  Café  ") == "Café"


def test_clean_text_keeps_emoji_joiners():
    family = "\U0001F468‍\U0001F469‍\U0001F467"
    assert clean_text(family) == family


# --- bot fields ----------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "<script>alert(1)</script>",
    "Acme <img src=x onerror=alert(1)>",
    "<svg/onload=alert(1)>",
    "Help </title><script>",
    "<!-- x -->",
])
def test_bot_name_rejects_html_markup(name):
    with pytest.raises(ValidationError, match="HTML"):
        BotCreate(name=name)


@pytest.mark.parametrize("name", ["Acme & Sons", "R&D <3", "a < b", "Q&A: 2 > 1"])
def test_bot_name_allows_ordinary_symbols(name):
    assert BotCreate(name=name).name == name


def test_bot_name_rejects_whitespace_only():
    with pytest.raises(ValidationError):
        BotCreate(name="   ‮  ")


def test_bot_update_cleans_and_rejects_markup_in_welcome_message():
    assert BotUpdate(welcome_message=f"  Hi{RLO}!  ").welcome_message == "Hi!"
    with pytest.raises(ValidationError, match="HTML"):
        BotUpdate(welcome_message='Hi <a href="javascript:alert(1)">click</a>')


def test_bot_update_instructions_keep_newlines_but_drop_control_chars():
    assert BotUpdate(instructions="Be brief.\n\x00Reply in French.").instructions == "Be brief.\nReply in French."


def test_bot_update_rejects_blank_name():
    with pytest.raises(ValidationError):
        BotUpdate(name="  ")


# --- chat question ----------------------------------------------------------------------

def test_chat_question_is_cleaned_and_must_not_be_blank():
    assert ChatRequest(question=" How\x00 do refunds work?\n").question == "How do refunds work?"
    with pytest.raises(ValidationError):
        ChatRequest(question=" \x00‮ ")


def test_chat_question_may_mention_html_since_it_is_never_rendered_as_html():
    # Customers may legitimately ask "how do I add a <script> tag?"; output escaping makes it safe.
    q = "How do I add the <script> tag to my site?"
    assert ChatRequest(question=q).question == q


# --- upload display names ----------------------------------------------------------------

def test_upload_display_name_strips_bidi_spoofing_and_paths():
    assert _safe_display_name(f"..\..\invoice{RLO}fdp.exe") == "invoicefdp.exe"
    assert _safe_display_name(f"{RLO}\x00") == "upload"
