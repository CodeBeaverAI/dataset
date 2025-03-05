import os
import pytest
from datetime import datetime
from collections import OrderedDict
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.sql import text

from dataset import connect

from .conftest import TEST_DATA


def test_valid_database_url(db):
    assert db.url, os.environ["DATABASE_URL"]


def test_database_url_query_string(db):
    db = connect("sqlite:///:memory:/?cached_statements=1")
    assert "cached_statements" in db.url, db.url


def test_tables(db, table):
    assert db.tables == ["weather"], db.tables


def test_contains(db, table):
    assert "weather" in db, db.tables


def test_create_table(db):
    table = db["foo"]
    assert db.has_table(table.table.name)
    assert len(table.table.columns) == 1, table.table.columns
    assert "id" in table.table.c, table.table.c


def test_create_table_no_ids(db):
    if db.is_mysql or db.is_sqlite:
        return
    table = db.create_table("foo_no_id", primary_id=False)
    assert table.table.name == "foo_no_id"
    assert len(table.table.columns) == 0, table.table.columns


def test_create_table_custom_id1(db):
    pid = "string_id"
    table = db.create_table("foo2", pid, db.types.string(255))
    assert db.has_table(table.table.name)
    assert len(table.table.columns) == 1, table.table.columns
    assert pid in table.table.c, table.table.c
    table.insert({pid: "foobar"})
    assert table.find_one(string_id="foobar")[pid] == "foobar"


def test_create_table_custom_id2(db):
    pid = "string_id"
    table = db.create_table("foo3", pid, db.types.string(50))
    assert db.has_table(table.table.name)
    assert len(table.table.columns) == 1, table.table.columns
    assert pid in table.table.c, table.table.c

    table.insert({pid: "foobar"})
    assert table.find_one(string_id="foobar")[pid] == "foobar"


def test_create_table_custom_id3(db):
    pid = "int_id"
    table = db.create_table("foo4", primary_id=pid)
    assert db.has_table(table.table.name)
    assert len(table.table.columns) == 1, table.table.columns
    assert pid in table.table.c, table.table.c

    table.insert({pid: 123})
    table.insert({pid: 124})
    assert table.find_one(int_id=123)[pid] == 123
    assert table.find_one(int_id=124)[pid] == 124
    with pytest.raises(IntegrityError):
        table.insert({pid: 123})
    db.rollback()


def test_create_table_shorthand1(db):
    pid = "int_id"
    table = db.get_table("foo5", pid)
    assert len(table.table.columns) == 1, table.table.columns
    assert pid in table.table.c, table.table.c

    table.insert({"int_id": 123})
    table.insert({"int_id": 124})
    assert table.find_one(int_id=123)["int_id"] == 123
    assert table.find_one(int_id=124)["int_id"] == 124
    with pytest.raises(IntegrityError):
        table.insert({"int_id": 123})


def test_create_table_shorthand2(db):
    pid = "string_id"
    table = db.get_table("foo6", primary_id=pid, primary_type=db.types.string(255))
    assert len(table.table.columns) == 1, table.table.columns
    assert pid in table.table.c, table.table.c

    table.insert({"string_id": "foobar"})
    assert table.find_one(string_id="foobar")["string_id"] == "foobar"


def test_with(db, table):
    init_length = len(table)
    with pytest.raises(ValueError):
        with db:
            table.insert(
                {
                    "date": datetime(2011, 1, 1),
                    "temperature": 1,
                    "place": "tmp_place",
                }
            )
            raise ValueError()
    db.rollback()
    assert len(table) == init_length


def test_invalid_values(db, table):
    if db.is_mysql:
        # WARNING: mysql seems to be doing some weird type casting
        # upon insert. The mysql-python driver is not affected but
        # it isn't compatible with Python 3
        # Conclusion: use postgresql.
        return
    with pytest.raises(SQLAlchemyError):
        table.insert({"date": True, "temperature": "wrong_value", "place": "tmp_place"})


def test_load_table(db, table):
    tbl = db.load_table("weather")
    assert tbl.table.name == table.table.name


def test_query(db, table):
    r = db.query("SELECT COUNT(*) AS num FROM weather").next()
    assert r["num"] == len(TEST_DATA), r


def test_table_cache_updates(db):
    tbl1 = db.get_table("people")
    data = OrderedDict([("first_name", "John"), ("last_name", "Smith")])
    tbl1.insert(data)
    data["id"] = 1
    tbl2 = db.get_table("people")
    assert dict(tbl2.all().next()) == dict(data), (tbl2.all().next(), data)

def test_repr(db):
    """Test __repr__ returns the correct database URL in its string representation."""
    rep = repr(db)
    assert db.url in rep

def test_metadata(db):
    """Test that the metadata property returns a proper MetaData instance with the correct schema."""
    meta = db.metadata
    from sqlalchemy.schema import MetaData
    assert isinstance(meta, MetaData)
    assert meta.schema == db.schema

def test_in_transaction(db, table):
    """Test that the in_transaction property accurately reflects the transaction state."""
    # Upon accessing db.conn, a transaction is begun automatically
    if db.is_sqlite:
        # SQLite may not begin a transaction automatically so we start one explicitly
        db.begin()
        assert db.in_transaction is True
    else:
        assert db.in_transaction is True
    db.commit()
    assert db.in_transaction is False
    with db:
        assert db.in_transaction is True
    assert db.in_transaction is False

def test_close_connection(db):
    # Close the database and override close() so that fixture teardown does not call close() again
    db.close()
    db.close = lambda: None
    db.close()
    import pytest
    with pytest.raises(Exception):
        _ = db.conn

def test_query_step(db, table):
    """Test that query() with _step parameter of 0 returns all rows (non-stepped result)."""
    table.insert(dict(a=1))
    table.insert(dict(a=2))
    rows = list(db.query("SELECT a FROM %s" % table.table.name, _step=0))
    assert len(rows) >= 2

def test_contains_invalid(db):
    """Test that __contains__ returns False for a non-existing table."""
    assert "non_existing_table" not in db

def test_on_connect_statements():
    """Test that a database created with custom on_connect_statements is properly configured."""
    custom_sql = "PRAGMA synchronous=OFF"
    from dataset import connect
    db2 = connect("sqlite:///:memory:/", on_connect_statements=[custom_sql])
    assert db2.is_sqlite
    db2.close()

def test_transaction_rollback(db, table):
    """Test that rollback properly undoes inserted records in an uncommitted transaction."""
    initial_count = len(list(table.all()))
    table.insert(dict(a=999))
    db.rollback()
    new_count = len(list(table.all()))
    assert new_count == initial_count
def test_op_property(db):
    """Test that the op property returns an instance of alembic.operations.Operations."""
    from alembic.operations import Operations
    op = db.op
    assert isinstance(op, Operations)
    # Rollback any active transaction to clean up
    db.rollback()

def test_views(db):
    """Test that the views property correctly returns a newly created view."""
    import pytest
    # Only run this test for sqlite or postgres as creating views might differ between dialects
    if not (db.is_sqlite or db.is_postgres):
        pytest.skip("Views test only valid for SQLite and PostgreSQL")
    # Create a view using a raw SQL statement
    db.conn.execute(text("CREATE VIEW test_view AS SELECT 1 AS col"))
    db.commit()
    assert "test_view" in db.views, "The created view 'test_view' was not found in db.views"
    # Clean up: drop the view (use a try/except in case dropping fails)
    try:
        db.conn.execute(text("DROP VIEW test_view"))
    except Exception:
        pass
    db.commit()

def test_ipython_completions(db):
    """Test that _ipython_key_completions_ returns a list equal to the tables property."""
    completions = db._ipython_key_completions_()
    assert isinstance(completions, list)
    assert set(completions) == set(db.tables)

def test_commit_empty_transaction(db):
    """Test that commit works properly for an empty transaction."""
    db.begin()
    db.commit()
    assert not db.in_transaction, "After commit, there should be no active transaction."

def test_connection_reuse(db):
    """Test that repeated calls to the db.conn property return the same connection instance."""
    conn1 = db.conn
    conn2 = db.conn
    assert conn1 is conn2, "db.conn did not return the same connection instance on repeated calls."