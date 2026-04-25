from sqlalchemy import Column, String

from server.db.base import Base, ULIDPK, generate_ulid


class _Probe(Base):
    __tablename__ = "_probe_table"
    id: ULIDPK
    label = Column(String)


def test_ulid_generator_returns_26_char_string():
    u = generate_ulid()
    assert isinstance(u, str)
    assert len(u) == 26


def test_base_is_declarative():
    assert hasattr(Base, "metadata")
