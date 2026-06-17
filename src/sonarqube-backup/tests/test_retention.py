from src import retention


NAMES = [
    "sonarqube-20260101-031500.tar.gz",
    "sonarqube-20260102-031500.tar.gz",
    "sonarqube-20260103-031500.tar.gz",
    "sonarqube-20260104-031500.tar.gz",
]


def test_select_expired_keeps_newest_n():
    expired = retention.select_expired(NAMES, keep=2)
    assert expired == [
        "sonarqube-20260101-031500.tar.gz",
        "sonarqube-20260102-031500.tar.gz",
    ]


def test_select_expired_nothing_when_under_limit():
    assert retention.select_expired(NAMES, keep=10) == []


def test_select_expired_keep_zero_keeps_all():
    assert retention.select_expired(NAMES, keep=0) == []


def test_select_expired_is_order_independent():
    shuffled = list(reversed(NAMES))
    assert retention.select_expired(shuffled, keep=1) == NAMES[:-1]


def test_prune_local_deletes_expired(tmp_path):
    for name in NAMES:
        (tmp_path / name).write_bytes(b"x")
    # an unrelated file must be left untouched
    (tmp_path / "notes.txt").write_text("keep me")

    deleted = retention.prune_local(tmp_path, keep=1)

    assert len(deleted) == 3
    remaining = sorted(p.name for p in tmp_path.glob("*.tar.gz"))
    assert remaining == ["sonarqube-20260104-031500.tar.gz"]
    assert (tmp_path / "notes.txt").exists()
