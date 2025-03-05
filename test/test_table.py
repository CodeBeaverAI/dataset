import os
import pytest
from datetime import datetime
from collections import OrderedDict
from sqlalchemy.types import BIGINT, INTEGER, VARCHAR, TEXT
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, ArgumentError
from sqlalchemy.sql.expression import false

from dataset import chunked

from .conftest import TEST_DATA, TEST_CITY_1


def test_insert(table):
    assert len(table) == len(TEST_DATA), len(table)
    last_id = table.insert(
        {"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"}
    )
    assert len(table) == len(TEST_DATA) + 1, len(table)
    assert table.find_one(id=last_id)["place"] == "Berlin"


def test_insert_ignore(table):
    table.insert_ignore(
        {"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"},
        ["place"],
    )
    assert len(table) == len(TEST_DATA) + 1, len(table)
    table.insert_ignore(
        {"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"},
        ["place"],
    )
    assert len(table) == len(TEST_DATA) + 1, len(table)


def test_insert_ignore_all_key(table):
    for i in range(0, 4):
        table.insert_ignore(
            {"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"},
            ["date", "temperature", "place"],
        )
    assert len(table) == len(TEST_DATA) + 1, len(table)


def test_insert_json(table):
    last_id = table.insert(
        {
            "date": datetime(2011, 1, 2),
            "temperature": -10,
            "place": "Berlin",
            "info": {
                "currency": "EUR",
                "language": "German",
                "population": 3292365,
            },
        }
    )
    assert len(table) == len(TEST_DATA) + 1, len(table)
    assert table.find_one(id=last_id)["place"] == "Berlin"


def test_upsert(table):
    table.upsert(
        {"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"},
        ["place"],
    )
    assert len(table) == len(TEST_DATA) + 1, len(table)
    table.upsert(
        {"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"},
        ["place"],
    )
    assert len(table) == len(TEST_DATA) + 1, len(table)


def test_upsert_single_column(db):
    table = db["banana_single_col"]
    table.upsert({"color": "Yellow"}, ["color"])
    assert len(table) == 1, len(table)
    table.upsert({"color": "Yellow"}, ["color"])
    assert len(table) == 1, len(table)


def test_upsert_all_key(table):
    assert len(table) == len(TEST_DATA), len(table)
    for i in range(0, 2):
        table.upsert(
            {"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"},
            ["date", "temperature", "place"],
        )
    assert len(table) == len(TEST_DATA) + 1, len(table)


def test_upsert_id(db):
    table = db["banana_with_id"]
    data = dict(id=10, title="I am a banana!")
    table.upsert(data, ["id"])
    assert len(table) == 1, len(table)


def test_update_while_iter(table):
    for row in table:
        row["foo"] = "bar"
        table.update(row, ["place", "date"])
    assert len(table) == len(TEST_DATA), len(table)


def test_weird_column_names(table):
    with pytest.raises(ValueError):
        table.insert(
            {
                "date": datetime(2011, 1, 2),
                "temperature": -10,
                "foo.bar": "Berlin",
                "qux.bar": "Huhu",
            }
        )


def test_cased_column_names(db):
    tbl = db["cased_column_names"]
    tbl.insert({"place": "Berlin"})
    tbl.insert({"Place": "Berlin"})
    tbl.insert({"PLACE ": "Berlin"})
    assert len(tbl.columns) == 2, tbl.columns
    assert len(list(tbl.find(Place="Berlin"))) == 3
    assert len(list(tbl.find(place="Berlin"))) == 3
    assert len(list(tbl.find(PLACE="Berlin"))) == 3


def test_invalid_column_names(db):
    tbl = db["weather"]
    with pytest.raises(ValueError):
        tbl.insert({None: "banana"})

    with pytest.raises(ValueError):
        tbl.insert({"": "banana"})

    with pytest.raises(ValueError):
        tbl.insert({"-": "banana"})


def test_delete(table):
    table.insert({"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"})
    original_count = len(table)
    assert len(table) == len(TEST_DATA) + 1, len(table)
    # Test bad use of API
    with pytest.raises(ArgumentError):
        table.delete({"place": "Berlin"})
    assert len(table) == original_count, len(table)

    assert table.delete(place="Berlin") is True, "should return 1"
    assert len(table) == len(TEST_DATA), len(table)
    assert table.delete() is True, "should return non zero"
    assert len(table) == 0, len(table)


def test_repr(table):
    assert (
        repr(table) == "<Table(weather)>"
    ), "the representation should be <Table(weather)>"


def test_delete_nonexist_entry(table):
    assert (
        table.delete(place="Berlin") is False
    ), "entry not exist, should fail to delete"


def test_find_one(table):
    table.insert({"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"})
    d = table.find_one(place="Berlin")
    assert d["temperature"] == -10, d
    d = table.find_one(place="Atlantis")
    assert d is None, d


def test_count(table):
    assert len(table) == 6, len(table)
    length = table.count(place=TEST_CITY_1)
    assert length == 3, length


def test_find(table):
    ds = list(table.find(place=TEST_CITY_1))
    assert len(ds) == 3, ds
    ds = list(table.find(place=TEST_CITY_1, _limit=2))
    assert len(ds) == 2, ds
    ds = list(table.find(place=TEST_CITY_1, _limit=2, _step=1))
    assert len(ds) == 2, ds
    ds = list(table.find(place=TEST_CITY_1, _limit=1, _step=2))
    assert len(ds) == 1, ds
    ds = list(table.find(_step=2))
    assert len(ds) == len(TEST_DATA), ds
    ds = list(table.find(order_by=["temperature"]))
    assert ds[0]["temperature"] == -1, ds
    ds = list(table.find(order_by=["-temperature"]))
    assert ds[0]["temperature"] == 8, ds
    ds = list(table.find(table.table.columns.temperature > 4))
    assert len(ds) == 3, ds


def test_find_dsl(table):
    ds = list(table.find(place={"like": "%lw%"}))
    assert len(ds) == 3, ds
    ds = list(table.find(temperature={">": 5}))
    assert len(ds) == 2, ds
    ds = list(table.find(temperature={">=": 5}))
    assert len(ds) == 3, ds
    ds = list(table.find(temperature={"<": 0}))
    assert len(ds) == 1, ds
    ds = list(table.find(temperature={"<=": 0}))
    assert len(ds) == 2, ds
    ds = list(table.find(temperature={"!=": -1}))
    assert len(ds) == 5, ds
    ds = list(table.find(temperature={"between": [5, 8]}))
    assert len(ds) == 3, ds
    ds = list(table.find(place={"=": "G€lway"}))
    assert len(ds) == 3, ds
    ds = list(table.find(place={"ilike": "%LwAy"}))
    assert len(ds) == 3, ds


def test_offset(table):
    ds = list(table.find(place=TEST_CITY_1, _offset=1))
    assert len(ds) == 2, ds
    ds = list(table.find(place=TEST_CITY_1, _limit=2, _offset=2))
    assert len(ds) == 1, ds


def test_streamed_update(table):
    ds = list(table.find(place=TEST_CITY_1, _streamed=True, _step=1))
    assert len(ds) == 3, len(ds)
    for row in table.find(place=TEST_CITY_1, _streamed=True, _step=1):
        row["temperature"] = -1
        table.update(row, ["id"])


def test_distinct(table):
    x = list(table.distinct("place"))
    assert len(x) == 2, x
    x = list(table.distinct("place", "date"))
    assert len(x) == 6, x
    x = list(
        table.distinct(
            "place",
            "date",
            table.table.columns.date >= datetime(2011, 1, 2, 0, 0),
        )
    )
    assert len(x) == 4, x

    x = list(table.distinct("temperature", place="B€rkeley"))
    assert len(x) == 3, x
    x = list(table.distinct("temperature", place=["B€rkeley", "G€lway"]))
    assert len(x) == 6, x


def test_insert_many(table):
    data = TEST_DATA * 100
    table.insert_many(data, chunk_size=13)
    assert len(table) == len(data) + 6, (len(table), len(data))


def test_chunked_insert(table):
    data = TEST_DATA * 100
    with chunked.ChunkedInsert(table) as chunk_tbl:
        for item in data:
            chunk_tbl.insert(item)
    assert len(table) == len(data) + 6, (len(table), len(data))


def test_chunked_insert_callback(table):
    data = TEST_DATA * 100
    N = 0

    def callback(queue):
        nonlocal N
        N += len(queue)

    with chunked.ChunkedInsert(table, callback=callback) as chunk_tbl:
        for item in data:
            chunk_tbl.insert(item)
    assert len(data) == N
    assert len(table) == len(data) + 6


def test_update_many(db):
    tbl = db["update_many_test"]
    tbl.insert_many([dict(temp=10), dict(temp=20), dict(temp=30)])
    tbl.update_many([dict(id=1, temp=50), dict(id=3, temp=50)], "id")

    # Ensure data has been updated.
    assert tbl.find_one(id=1)["temp"] == tbl.find_one(id=3)["temp"]


def test_chunked_update(db):
    tbl = db["update_many_test"]
    tbl.insert_many(
        [
            dict(temp=10, location="asdf"),
            dict(temp=20, location="qwer"),
            dict(temp=30, location="asdf"),
        ]
    )
    db.commit()

    chunked_tbl = chunked.ChunkedUpdate(tbl, ["id"])
    chunked_tbl.update(dict(id=1, temp=50))
    chunked_tbl.update(dict(id=2, location="asdf"))
    chunked_tbl.update(dict(id=3, temp=50))
    chunked_tbl.flush()
    db.commit()

    # Ensure data has been updated.
    assert tbl.find_one(id=1)["temp"] == tbl.find_one(id=3)["temp"] == 50
    assert tbl.find_one(id=2)["location"] == tbl.find_one(id=3)["location"] == "asdf"


def test_upsert_many(db):
    # Also tests updating on records with different attributes
    tbl = db["upsert_many_test"]

    W = 100
    tbl.upsert_many([dict(age=10), dict(weight=W)], "id")
    assert tbl.find_one(id=1)["age"] == 10

    tbl.upsert_many([dict(id=1, age=70), dict(id=2, weight=W / 2)], "id")
    assert tbl.find_one(id=2)["weight"] == W / 2


def test_drop_operations(table):
    assert table._table is not None, "table shouldn't be dropped yet"
    table.drop()
    assert table._table is None, "table should be dropped now"
    assert list(table.all()) == [], table.all()
    assert table.count() == 0, table.count()


def test_table_drop(db, table):
    assert "weather" in db
    db["weather"].drop()
    assert "weather" not in db


def test_table_drop_then_create(db, table):
    assert "weather" in db
    db["weather"].drop()
    assert "weather" not in db
    db["weather"].insert({"foo": "bar"})


def test_columns(table):
    cols = table.columns
    assert len(list(cols)) == 4, "column count mismatch"
    assert "date" in cols and "temperature" in cols and "place" in cols


def test_drop_column(table):
    try:
        table.drop_column("date")
        assert "date" not in table.columns
    except RuntimeError:
        pass


def test_iter(table):
    c = 0
    for row in table:
        c += 1
    assert c == len(table)


def test_update(table):
    date = datetime(2011, 1, 2)
    res = table.update(
        {"date": date, "temperature": -10, "place": TEST_CITY_1}, ["place", "date"]
    )
    assert res, "update should return True"
    m = table.find_one(place=TEST_CITY_1, date=date)
    assert m["temperature"] == -10, (
        "new temp. should be -10 but is %d" % m["temperature"]
    )


def test_create_column(db, table):
    flt = db.types.float
    table.create_column("foo", flt)
    assert "foo" in table.table.c, table.table.c
    assert isinstance(table.table.c["foo"].type, flt), table.table.c["foo"].type
    assert "foo" in table.columns, table.columns


def test_ensure_column(db, table):
    flt = db.types.float
    table.create_column_by_example("foo", 0.1)
    assert "foo" in table.table.c, table.table.c
    assert isinstance(table.table.c["foo"].type, flt), table.table.c["bar"].type
    table.create_column_by_example("bar", 1)
    assert "bar" in table.table.c, table.table.c
    assert isinstance(table.table.c["bar"].type, BIGINT), table.table.c["bar"].type
    table.create_column_by_example("pippo", "test")
    assert "pippo" in table.table.c, table.table.c
    assert isinstance(table.table.c["pippo"].type, TEXT), table.table.c["pippo"].type
    table.create_column_by_example("bigbar", 11111111111)
    assert "bigbar" in table.table.c, table.table.c
    assert isinstance(table.table.c["bigbar"].type, BIGINT), table.table.c[
        "bigbar"
    ].type
    table.create_column_by_example("littlebar", -11111111111)
    assert "littlebar" in table.table.c, table.table.c
    assert isinstance(table.table.c["littlebar"].type, BIGINT), table.table.c[
        "littlebar"
    ].type


def test_key_order(db, table):
    res = db.query("SELECT temperature, place FROM weather LIMIT 1")
    keys = list(res.next().keys())
    assert keys[0] == "temperature"
    assert keys[1] == "place"


def test_empty_query(table):
    empty = list(table.find(place="not in data"))
    assert len(empty) == 0, empty

def test_find_unknown_operator(table):
    """Test find with an unknown operator returns no results."""
    # Insert a distinct row below to guarantee a match is possible if operator was recognized
    table.insert({"date": datetime(2020, 1, 1), "temperature": 20, "place": "Test"})
    # Using an unknown operator "foo" should yield a clause that always evaluates to false.
    results = list(table.find(temperature={"foo": 20}))
    assert len(results) == 0, "Unknown operator should result in no rows matching"

def test_create_index_existing(table):
    """Test that creating an index twice does not fail and is handled gracefully."""
    # Create an index on "place"
    table.create_index("place")
    # Attempt again to create the same index
    table.create_index("place")
    # Verify that has_index returns True.
    assert table.has_index("place")

def test_drop_column_sqlite(db, table):
    """Test that dropping a column on SQLite raises a RuntimeError."""
    original_is_sqlite = db.is_sqlite
    db.is_sqlite = True
    try:
        with pytest.raises(RuntimeError):
            table.drop_column("temperature")
    finally:
        db.is_sqlite = original_is_sqlite

def test_sync_columns_without_ensure(table):
    """Test that _sync_columns does not add new keys when ensure is False."""
    # Capture the current columns.
    original_columns = set(table.columns)
    # Create a row with a non-existing column.
    new_row = {"non_existing_col": "value", "place": "Berlin", "date": datetime(2011, 1, 2)}
    synced = table._sync_columns(new_row, ensure=False)
    # "non_existing_col" should not be part of the synced row.
    assert "non_existing_col" not in synced
    # Existing columns should remain.
    assert "place" in synced and "date" in synced

def test_keys_to_args_missing_keys(table):
    """Test _keys_to_args when the row is missing some keys."""
    row = {"date": datetime(2011, 1, 2), "temperature": -10}
    keys = ["date", "place"]
    args, remaining = table._keys_to_args(row, keys)
    # "date" exists, but "place" does not.
    assert args["date"] is not None
    assert args["place"] is None
    # The remaining row should contain only keys not in "keys"
    assert "temperature" in remaining and len(remaining) == 1

def test_generate_clause_edge(table):
    """Test _generate_clause with an unknown operator returns a false clause."""
    clause = table._generate_clause("place", "unknown", "value")
    # Converting to string to compare with false() clause.
    assert str(clause) == str(false())

def test_update_with_missing_filter_keys(table):
    """Test update returns zero count when no rows match the filter keys."""
    # Attempt to update a non-existent row (using "id" as filter)
    result = table.update({"date": datetime(2022, 2, 2), "temperature": 5, "place": "NonExistent"}, ["id"])
    # Since no row should match, the update should return a rowcount of 0 (or possibly None).
    assert result == 0 or result is None

# End of added tests
def test_threading_warning(table, monkeypatch):
    """Test that a RuntimeWarning is triggered when changing the schema during a transaction in a multi-threaded context."""
    # Simulate being in a transaction and having multiple active threads.
    monkeypatch.setattr(type(table.db), "in_transaction", property(lambda self: True))
    monkeypatch.setattr("threading.active_count", lambda: 2)
    with pytest.warns(RuntimeWarning, match="Changing the database schema inside a transaction"):
        table._threading_warn()

def test_sync_columns_with_ensure(table):
    """Test that _sync_columns adds non-existing keys when ensure=True and updates the table schema."""
    old_columns = set(table.columns)
    new_row = {"date": datetime(2011, 1, 2), "place": "Berlin", "extra": "value"}
    result = table._sync_columns(new_row, ensure=True)
    # Check that the new 'extra' column is added in returned row and table.columns.
    assert "extra" in result
    assert "extra" in table.columns

def test_update_no_change(table):
    """Test update returns the number of matching rows if no new value is provided after filter keys are removed."""
    # Insert a sample row.
    table.insert({"date": datetime(2011, 1, 2), "temperature": 20, "place": "NoChange"})
    count_before = table.count(place="NoChange")
    # Provide an update where the row dictionary only contains the filter keys.
    res = table.update({"date": datetime(2011, 1, 2), "place": "NoChange"}, ["date", "place"])
    # Since there are no new column values to update, update() should return the count of matching rows.
    assert res == count_before

def test_upsert_many_empty(db):
    """Test that calling upsert_many with an empty list performs no operations and leaves the table empty."""
    tbl = db["upsert_many_empty_test"]
    tbl.upsert_many([], "id")
    assert tbl.count() == 0
def test_generate_clause_startswith(table):
    """Test _generate_clause with 'startswith' operator returns proper LIKE clause."""
    clause = table._generate_clause("place", "startswith", "Ber")
    compiled = clause.compile(compile_kwargs={"literal_binds": True})
    clause_str = str(compiled)
    assert "LIKE" in clause_str and "Ber%" in clause_str

def test_generate_clause_endswith(table):
    """Test _generate_clause with 'endswith' operator returns proper LIKE clause."""
    clause = table._generate_clause("place", "endswith", "lin")
    compiled = clause.compile(compile_kwargs={"literal_binds": True})
    clause_str = str(compiled)
    assert "LIKE" in clause_str and "%lin" in clause_str

def test_generate_clause_in(table):
    """Test _generate_clause with 'in' operator returns proper IN clause."""
    clause = table._generate_clause("temperature", "in", [1, 2, 3])
    compiled = clause.compile(compile_kwargs={"literal_binds": True})
    clause_str = str(compiled)
    assert "IN" in clause_str

def test_generate_clause_between(table):
    """Test _generate_clause with 'between' operator returns proper BETWEEN clause."""
    clause = table._generate_clause("temperature", "between", (5, 8))
    compiled = clause.compile(compile_kwargs={"literal_binds": True})
    clause_str = str(compiled)
    assert "BETWEEN" in clause_str

def test_column_keys_after_insert(table):
    """Test that inserting a row with ensure=True adds a new column to the table schema and _column_keys."""
    table.insert({"date": datetime(2020, 1, 1), "temperature": 0, "place": "TestCase", "new_column": "new_value"}, ensure=True)
    table.insert({"date": datetime(2020, 1, 1), "temperature": 0, "place": "TestCase", "new_column": "new_value"}, ensure=True)
    # Force reloading of columns by accessing the _column_keys property.
    new_keys = set(table._column_keys.values())
    assert "new_column" in new_keys
    # Also check that the inserted row contains the new column.
    row = table.find_one(new_column="new_value")
    assert row is not None and row.get("new_column") == "new_value"

def test_multiple_index_creation(table):
    """Test creation of a multi-column index and verify that has_index returns True."""
    # Create an index on 'date' and 'place'
    table.create_index(["date", "place"], name="test_multi_idx")
    assert table.has_index(["date", "place"])

def test_update_no_matching_row(table):
    """Test that calling update with filter keys that yield no matching row returns zero (or None)."""
    res = table.update({"date": "2099-01-01", "temperature": 100, "place": "Nowhere"}, ["date", "place"])
    assert res == 0 or res is None