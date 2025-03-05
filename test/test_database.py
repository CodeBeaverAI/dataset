import os
import pytest
from datetime import datetime
from collections import OrderedDict
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

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
        """Test __repr__ returns safe URL representation."""
        rep = repr(db)
        from dataset.util import safe_url
        assert safe_url(db.url) in rep
    
    def test_in_transaction(db):
        """Test that in_transaction returns True as soon as a connection is accessed."""
        # accessing the connection starts a transaction so this should be True.
        assert db.in_transaction is True
    
    def test_close_database(db):
        """Test that closing the database resets engine and table cache."""
        _ = db.get_table("dummy_close")
        db.close()
        assert db._engine is None
        assert db._tables == {}
    
    def test_ipython_key_completions(db):
        """Test that _ipython_key_completions returns a list of table names."""
        _ = db.get_table("ipython_test")
        completions = db._ipython_key_completions_()
        # normalize table names are used so 'ipython_test' should be there.
        assert "ipython_test" in completions
    
    def test_flush_tables(db):
        """Test that _flush_tables resets internal table metadata for cached tables."""
        table_obj = db.get_table("flush_test")
        # Set a dummy _table value
        table_obj._table = "dummy"
        db._flush_tables()
        assert table_obj._table is None
    
    def test_query_with_text_object(db):
        """Test that the query method accepts SQLAlchemy text objects."""
        table_obj = db.create_table("query_text")
        table_obj.insert({'id': 1})
        from sqlalchemy.sql import text
        result = list(db.query(text("SELECT * FROM query_text")))
        assert len(result) >= 1
        assert result[0]['id'] == 1
    
    def test_query_without_step(db):
        """Test that the query method returns all rows when _step is disabled."""
        table_obj = db.create_table("query_no_step")
        table_obj.insert({'id': 2})
        result = list(db.query("SELECT * FROM query_no_step", _step=False))
        assert len(result) >= 1
        assert result[0]['id'] == 2
    
    def test_context_manager_no_exception(db):
        """Test that the context manager commits the transaction if no error occurs."""
        weather_table = db.get_table("weather")
        initial_count = len(list(weather_table.all()))
        with db:
            weather_table.insert({"date": "2023-10-11", "temperature": 25, "place": "test"})
        new_count = len(list(weather_table.all()))
        assert new_count == initial_count + 1
    
    def test_context_manager_with_exception(db):
        """Test that the context manager rolls back the transaction if an error is raised."""
        weather_table = db.get_table("weather")
        initial_count = len(list(weather_table.all()))
        try:
            with db:
                weather_table.insert({"date": "2023-10-12", "temperature": 30, "place": "rollback_test"})
                raise RuntimeError("Triggering rollback")
        except RuntimeError:
            pass
        new_count = len(list(weather_table.all()))
        assert new_count == initial_count
