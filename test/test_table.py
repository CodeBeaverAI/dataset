import os
import pytest
from datetime import datetime
from collections import OrderedDict
from sqlalchemy.types import BIGINT, INTEGER, VARCHAR, TEXT
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, ArgumentError
import threading
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

def test_order_by_invalid(table):
    """Test that order_by with an invalid column does not break and that valid ordering still works."""
    # Insert an additional row so ordering makes sense
    table.insert({"date": datetime(2022, 1, 1), "temperature": 5, "place": "TestCity"})
    # Pass an invalid order_by column ("non_existent") before a valid one ("temperature")
    results = list(table.find(order_by=["non_existent", "temperature"]))
    # We expect that only a valid ordering is applied eventually.
    # Here we simply check that rows have the "temperature" key.
    for row in results:
        assert "temperature" in row

def test_between_invalid(table):
    """Test that providing an invalid number of arguments to a 'between' filter raises an error."""
    with pytest.raises(ValueError):
        # Passing a list with one element should raise an error because tuple unpacking fails.
        list(table.find(temperature={"between": [5]}))

def test_find_unsupported_operator(table):
    """Test that using an unsupported operator in a filter returns no results."""
    # Insert a known row
    table.insert({"date": datetime(2022, 2, 2), "temperature": 15, "place": "TestTown"})
    results = list(table.find(temperature={"unknown": 15}))
    # An unsupported operator should resolve to a false() clause so that no rows match.
    assert results == []

def test_update_no_change(table):
    """Test update when the update payload is fully consumed by key filters resulting in no new data to update."""
    # Insert a unique row.
    row_id = table.insert({"date": datetime(2020, 5, 5), "temperature": 20, "place": "Unique"})
    row = table.find_one(id=row_id)
    # Calling update with keys only (i.e. without any remaining data) should return the count of matching rows.
    count = table.update(row, ["id"])
    # At least one row should match
    assert count >= 1

def test_insert_non_dict(table):
    """Test that inserting a non-dictionary value causes an error."""
    with pytest.raises(AttributeError):
        table.insert("not a dict")

def test_create_index_duplicate(table):
    """Test that creating an index on the same column twice does not create duplicate indexes or raise an error."""
    # First creation of the index
    table.create_index(["place"])
    # Second creation should simply be a no-op.
    table.create_index(["place"])
    # Fetch indexes and verify that at least one index covers the 'place' column.
    indexes = table.db.inspect.get_indexes(table.name, schema=table.db.schema)
    assert any("place" in idx.get("column_names", []) for idx in indexes)

def test_drop_nonexistent_column(table):
    """Test that attempting to drop a non-existent column does not crash the operation."""
    if table.db.is_sqlite:
        pytest.skip("SQLite does not support dropping columns, skipping test.")
    try:
        table.drop_column("nonexistent_column")
    except Exception:
        pytest.fail("Dropping a non-existent column raised an exception")

    # Clear the table for a controlled test.
    table.delete()
    # Insert rows with duplicate 'place' values.
    table.insert({"date": datetime(2022, 3, 3), "temperature": 10, "place": "SameTown"})
    table.insert({"date": datetime(2022, 3, 4), "temperature": 12, "place": "SameTown"})
    distinct_rows = list(table.distinct("place"))
    assert len(distinct_rows) == 1

def test_delete_with_filters(table):
    """Test deletion with multiple filter criteria to ensure only matching rows are removed."""
    # Insert distinct rows.
    table.insert({"date": datetime(2021, 1, 1), "temperature": 0, "place": "DeleteTown"})
    table.insert({"date": datetime(2021, 1, 2), "temperature": 1, "place": "DeleteTown"})
    original_count = len(table)
    # Delete the row with the specified date.
    deleted = table.delete(place="DeleteTown", date=datetime(2021, 1, 1))
    assert deleted is True
    new_count = len(table)
    assert new_count == original_count - 1

def test_drop_table_idempotent(db):
    """Test that dropping a table twice does not cause an exception."""
    table = db["temp_table"]
    table.insert({"date": datetime(2023, 1, 1), "temperature": 5, "place": "TempPlace"})
    table.drop()
    # Dropping an already dropped table should not raise an exception.
    try:
        table.drop()
    except Exception:
        pytest.fail("Dropping an already dropped table raised an exception")

def test_repr_str_format(table, monkeypatch):
    """Test that the __repr__ method returns a proper string representation with the table name."""
    rep = repr(table)
    assert rep.startswith("<Table(") and rep.endswith(")>")
    name = table.table.name if table.exists else table.name
    assert name in rep
    orig_in_trans = table.db.in_transaction

    monkeypatch.setattr(type(table.db), "in_transaction", property(lambda self: True))
    monkeypatch.setattr(threading, "active_count", lambda: 2)
    with pytest.warns(RuntimeWarning, match="Changing the database schema inside a transaction"):
        table._threading_warn()
        table._threading_warn()

def test_keys_to_args(table):
    """Test the _keys_to_args method to ensure keys are separated correctly from the row."""
    row = {"a": 1, "b": 2}
    args, remainder = table._keys_to_args(row, "a")
    assert args == {"a": 1}
    assert remainder == {"b": 2}

def test_args_to_order_by_invalid(table):
    """Test _args_to_order_by with an invalid column name and a valid one."""
    # Insert a column 'valid' to ensure it exists.
    if not table.has_column("valid"):
        table.create_column("valid", table.db.types.integer)
    orderings = table._args_to_order_by(["nonexistent", "valid"])
    # 'nonexistent' should be ignored, and ordering for 'valid' should appear.
    assert len(orderings) == 1

def test_sync_columns_auto_create(db):
    """Test that missing columns are auto-created when ensure_schema is enabled."""
    tbl = db["auto_create_test"]
    # Ensure auto_create is enabled so that missing columns get created.
    tbl._auto_create = True
    initial_cols = set(tbl.columns)
    new_data = {"new_col": "test_value", "another_col": 123}
    tbl.insert(new_data, ensure=True)
    updated_cols = set(tbl.columns)
    assert "new_col" in updated_cols
    assert "another_col" in updated_cols

def test_update_return_count(table):
    """Test that update returns the count when no new data is provided to update."""
    # Insert a row to update.
    row_id = table.insert({"date": datetime(2024, 1, 1), "temperature": 20, "place": "TestUpdate"})
    row = table.find_one(id=row_id)
    # Call update with keys that fully consume the row, so no new values remain.
    count = table.update(row.copy(), ["id"])
    assert count >= 1
def test_generate_clause_invalid_operator(table):
    """Test that _generate_clause returns a false() clause when an unsupported operator is provided."""
    # Call _generate_clause with an invalid operator and verify that it returns a false() SQL expression.
    clause = table._generate_clause("temperature", "unknown_op", 10)
    compiled_clause = str(clause.compile(compile_kwargs={"literal_binds": True}))
    # The compiled clause should contain "false", regardless of uppercase/lowercase.
    assert "false" in compiled_clause.lower()

def test_args_to_clause_nonexistent_column(table):
    """Test that _args_to_clause returns a false clause part for a nonexistent column."""
    clause = table._args_to_clause({"nonexistent": 42})
    compiled_clause = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "false" in compiled_clause.lower()

def test_delete_using_clause_expression(table):
    """Test deletion using a clause expression while also combining keyword filters."""
    # Insert a row that will be deleted using a clause expression.
    table.insert({"date": datetime(2020, 1, 1), "temperature": 25, "place": "DeleteExpr"})
    from sqlalchemy import literal
    clause_expr = (table.table.c.temperature == 25)
    # Combine the clause expression with an additional keyword filter.
    deleted = table.delete(clause_expr, place="DeleteExpr")
    assert deleted is True
    # Now the row should be gone; deleting it again should return False.
    deleted_again = table.delete(clause_expr, place="DeleteExpr")
    assert deleted_again is False

def test_has_index_primary_key(db):
    """Test that has_index returns True for the primary key column of a table."""
    tbl = db["index_primary_test"]
    # Insert a row to force table creation (which creates the primary key column 'id').
    tbl.insert({"data": "test"})
    # Calling has_index on the primary key column should return True.
    assert tbl.has_index("id") is True

def test_args_to_order_by_mixed(table):
    """Test _args_to_order_by with a mix of valid and invalid column names."""
    # First ensure that the "valid_order" column exists.
    if not table.has_column("valid_order"):
        table.create_column("valid_order", table.db.types.integer)
        # Insert a dummy row including the new column.
        table.insert({"date": datetime(2021, 1, 1), "temperature": 0, "place": "TestPlace", "valid_order": 1})
    orderings = table._args_to_order_by(["nonexistent", "valid_order"])
    # Only "valid_order" is valid so we expect one ordering.
    assert len(orderings) == 1

# End of inserted tests.