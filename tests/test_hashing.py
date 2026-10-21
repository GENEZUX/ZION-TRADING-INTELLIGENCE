"""DAT-02: same bytes -> same SHA-256; one byte changed -> different hash."""

import hashlib


def test_same_bytes_same_hash():
    a = b"ZION"
    b = b"ZION"
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()


def test_one_byte_changed():
    a = b"ZION"
    b = b"ZIOO"
    assert hashlib.sha256(a).hexdigest() != hashlib.sha256(b).hexdigest()
