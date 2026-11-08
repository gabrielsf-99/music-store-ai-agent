import pytest

from emporio.tools.orders import contact_matches, normalize_phone

EMAIL = "ana.exemplo@example.com"
PHONE_DIGITS = "67999990001"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("(67) 99999-0001", "67999990001"),
        ("67 99999-0001", "67999990001"),
        ("+55 (67) 99999-0001", "67999990001"),
        ("5567999990001", "67999990001"),
        ("(67) 3333-0003", "6733330003"),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "contact",
    [EMAIL, " Ana.Exemplo@Example.com ", "(67) 99999-0001", "+55 67 99999-0001", "67999990001"],
)
def test_contact_matches(contact):
    assert contact_matches(contact, EMAIL, PHONE_DIGITS)


@pytest.mark.parametrize(
    "contact",
    [
        "outra.pessoa@example.com",
        "(67) 99999-0002",
        "99999-0001",  # without area code
        "0001",
        "",
    ],
)
def test_contact_does_not_match(contact):
    assert not contact_matches(contact, EMAIL, PHONE_DIGITS)
