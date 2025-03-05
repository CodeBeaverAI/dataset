import os
import pytest
from datetime import datetime
from collections import OrderedDict
from sqlalchemy.types import BIGINT, INTEGER, VARCHAR, TEXT
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, ArgumentError

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

def test_exists_property(db):
    """Test the exists property of a table before and after creation and drop."""
    # Create a new temporary table instance with a unique name.
    temp = db["temp_exists"]
    # Before any operations, the table should not exist.
    assert not temp.exists, "Table should not exist yet"
    # Insert a row to trigger auto table creation (ensure=True forces schema creation)
    temp.insert({"dummy": "data"}, ensure=True)
    assert temp.exists, "Table should exist after insertion"
    # Now drop the table and check exists property again.
    temp.drop()
    assert not temp.exists, "Table should not exist after drop"

def test_insert_no_ensure(table, db):
    """Test that inserting a row with an unknown column using ensure=False omits that column."""
    # Create a dedicated table to avoid schema conflict with the main fixture.
    test_tbl = db["no_ensure_test"]
    # Insert a row with an extra column; since ensure is False it should not be created.
    inserted = test_tbl.insert({"date": datetime(2011, 1, 2), "temperature": 25, "place": "Testville", "extra": "value"}, ensure=False)
    new_row = test_tbl.find_one(id=inserted)
    # The extra column should not appear in the stored row.
    assert "extra" not in new_row, "Extra column should not be created when ensure is False"

def test_create_index_non_existing(table):
    """Test creating an index with a non-existent column does nothing."""
    # Create a column that is known to exist.
    table.create_column("existing", VARCHAR(50))
    # Attempt to create an index on one existing and one non-existing column.
    table.create_index(["existing", "non_existing"], name="idx_test")
    # Since "non_existing" does not exist, the index should not be created.
    assert not table.has_index(["existing", "non_existing"]), "Index should not be created with non-existent column"

def test_update_no_op(table):
    """Test updating a row with only key fields returns the count without making alterations."""
    # Insert a test row.
    row = {"date": datetime(2011, 1, 2), "temperature": 15, "place": "Nowhere"}
    inserted = table.insert(row, ensure=True)
    # Invoke update with no additional update fields (only key values provided).
    count = table.update({
        "date": row["date"],
        "temperature": row["temperature"],
        "place": row["place"]
    }, ["date", "temperature", "place"])
    # Should return the count (the number of matched rows); we’re not altering any value.
    assert count >= 1, "Update with no changes should return the number of matching rows"

def test_chunked_insert_edge_case(table):
    """Test that a chunked insert with empty data does not modify the table."""
    initial_len = len(table)
    with chunked.ChunkedInsert(table) as ci:
        # Do not insert any data.
        pass
    assert len(table) == initial_len, "Empty chunked insert should not change table count"

def test_stream_results(table):
    """Test that streamed query returns the expected number of rows."""
    # Insert a few rows with a distinct place.
    for i in range(3):
        table.insert({"date": datetime(2011, 1, 2), "temperature": 20+i, "place": "Streamville"}, ensure=True)
    rows = list(table.find(place="Streamville", _streamed=True, _step=1))
    assert len(rows) == 3, "Streamed query should return exactly three rows"

# End of inserted tests.
def test_unknown_operator_filter(table):
    """Test that using an unknown operator yields no results."""
    # Insert a row with a distinctive place to later filter on.
    table.insert({"date": datetime(2021, 1, 1), "temperature": 25, "place": "UnknownOp"}, ensure=True)
    # Use an unknown operator 'foobar' – _generate_clause will return false() so no row should match.
    results = list(table.find(place={"foobar": "UnknownOp"}))
    assert len(results) == 0, "Expected no results with an unknown operator filter"

def test_order_by_invalid_column(table):
    """Test that ordering by a non-existing column does not break the query."""
    # Order by a non-existent column should simply be ignored.
    results = list(table.find(order_by=["nonexistent"]))
    # Expect all rows to be returned.
    assert len(results) == len(table), "Expected all rows when ordering by an invalid column"

def test_create_duplicate_column(db, table):
    """Test that creating a duplicate column does not alter the table schema."""
    initial_columns = set(table.columns)
    # Create a new column 'duplicate_test'
    table.create_column("duplicate_test", INTEGER)
    # Calling create_column again should not add an extra column.
    table.create_column("duplicate_test", INTEGER)
    new_columns = set(table.columns)
    # The new set should have exactly one more column than the initial set.
    assert "duplicate_test" in new_columns, "Column 'duplicate_test' should exist in the schema"
    assert len(new_columns) == len(initial_columns) + 1, "Duplicate column creation should not add extra columns"

def test_update_keys_removal(table):
    """Test that keys used for matching are removed from the update payload."""
    # Insert a row with an extra field.
    row_data = {"date": datetime(2022, 2, 2), "temperature": 15, "place": "KeyTest", "extra": "initial"}
    rid = table.insert(row_data.copy(), ensure=True)
    # Update using keys (date and place) while also changing the 'extra' value.
    update_data = {"date": row_data["date"], "place": row_data["place"], "extra": "updated"}
    count = table.update(update_data, ["date", "place"])
    assert count >= 1, "Update should affect at least one row"
    updated_row = table.find_one(id=rid)
    assert updated_row.get("extra") == "updated", "Update did not modify 'extra' field correctly"
def test_update_many_empty(db):
    """
    Test that update_many with an empty list of rows does not alter the table.
    """
    tbl = db["empty_update_test"]
    # Insert a couple of rows into the table.
    tbl.insert_many([{"temp": 10}, {"temp": 20}])
    initial_count = tbl.count()
    # Call update_many with an empty list.
    tbl.update_many([], "id")
    assert tbl.count() == initial_count, "update_many with empty list should not change table rows"

def test_upsert_many_empty(db):
    """
    Test that upsert_many with an empty list does not alter the table.
    """
    tbl = db["empty_upsert_test"]
    tbl.insert({"name": "Alice"}, ensure=True)
    initial_count = tbl.count()
    tbl.upsert_many([], "id")
    assert tbl.count() == initial_count, "upsert_many with empty list should not change table rows"

def test_order_by_mixed(table):
    """
    Test ordering with a mix of valid and invalid columns.
    Invalid ordering columns should be ignored.
    """
    # Add test rows with specific temperatures.
    table.insert({"date": datetime(2022, 1, 1), "temperature": 15, "place": "X"})
    table.insert({"date": datetime(2022, 1, 2), "temperature": 10, "place": "Y"})
    table.insert({"date": datetime(2022, 1, 3), "temperature": 20, "place": "Z"})
    # Order by valid temperature ascending; an invalid column "nonexistent" should be ignored.
    results = list(table.find(order_by=["temperature", "nonexistent"]))
    temps = [row["temperature"] for row in results]
    assert temps == sorted(temps), "Rows should be ordered by temperature ascending"
    
    # Order by descending temperature using valid flag; again invalid should be ignored.
    results_desc = list(table.find(order_by=["-temperature", "nonexistent"]))
    temps_desc = [row["temperature"] for row in results_desc]
    assert temps_desc == sorted(temps_desc, reverse=True), "Rows should be ordered by temperature descending"

def test_insert_boolean_and_null(table):
    """
    Test inserting rows with boolean and None values.
    """
    # Insert a row with a None temperature and a boolean value in 'active'.
    inserted_id = table.insert({"date": datetime(2020, 5, 5), "temperature": None, "place": "TestVille", "active": True}, ensure=True)
    row = table.find_one(id=inserted_id)
    assert row["temperature"] is None, "Temperature should be None"
    assert row["active"] is True, "Active should be True"