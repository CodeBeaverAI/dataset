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

# New tests to increase test coverage
def test_find_invalid_operator(table):
    """Test find with an unsupported operator returns no rows using an unknown operator."""
    # Passing an operator that is not recognized should result in a false() clause, yielding no results.
    results = list(table.find(temperature={"unknown": 5}))
    assert results == [], "Using an unsupported operator should return an empty result set"

def test_create_index_custom_name(db):
    """Test creating an index with a custom name on a table column."""
    tbl = db["index_test"]
    # Create the table by inserting a row
    tbl.insert({"temperature": 22, "place": "TestCity"})
    tbl.create_index(["temperature"], name="custom_index")
    assert tbl.has_index(["temperature"]), "Custom index should be recognized by has_index"

def test_insert_many_empty(table):
    """Test that insert_many with an empty list leaves the table unchanged."""
    initial_count = len(table)
    table.insert_many([], chunk_size=10)
    assert len(table) == initial_count, "Inserting an empty list should not change the table count"

def test_update_many_empty(table):
    """Test that update_many with an empty list leaves the table unchanged."""
    initial_count = len(table)
    table.update_many([], "id")
    assert len(table) == initial_count, "Updating an empty list should not change the table count"

def test_insert_no_ensure(table):
    """Test that extra keys are dropped when ensure is False."""
    # 'place' is an existing column, while 'not_exist' is not
    row_data = {"place": "TestCity", "not_exist": "should_be_dropped"}
    new_id = table.insert(row_data, ensure=False)
    ret = table.find_one(id=new_id)
    assert "place" in ret, "Existing column 'place' should be present"
    assert "not_exist" not in ret, "Non-existing column 'not_exist' should be dropped"

def test_find_operator_filters(table):
    """Test find DSL operators: startswith, endswith, notlike, and notilike."""
    from datetime import datetime
    # Insert a row with a new 'text' column (auto-created when ensure=True)
    new_id = table.insert({
        "date": datetime(2021, 1, 1),
        "temperature": 0,
        "place": "TestPlace",
        "text": "HelloWorld"
    }, ensure=True)
    # Test 'startswith'
    rows = list(table.find(text={"startswith": "Hell"}))
    assert any(r.get("text") == "HelloWorld" for r in rows), "Row with text starting 'Hell' should be found"
    # Test 'endswith'
    rows = list(table.find(text={"endswith": "World"}))
    assert any(r.get("text") == "HelloWorld" for r in rows), "Row with text ending 'World' should be found"
    # Test 'notlike' (should exclude rows that match the pattern)
    rows = list(table.find(text={"notlike": "%Bye%"}))
    assert any(r.get("text") == "HelloWorld" for r in rows), "Row with text not matching '%Bye%' should be found"
    # Test 'notilike' (case-insensitive match)
    rows = list(table.find(text={"notilike": "%bye%"}))
    assert any(r.get("text") == "HelloWorld" for r in rows), "Row with text not matching case-insensitive '%bye%' should be found"

def test_update_empty_data(table):
    """Test update behavior when the update dict becomes empty (only keys are used for filtering)."""
    # Grab an existing row from the table based on a known column value
    sample = table.find_one()
    # Use keys present in the sample so that the update dict (non-key fields) becomes empty.
    # The update method should then return the count of matched records rather than false.
    count = table.update(sample, ["place", "date"])
    assert count > 0, "Update with empty update dict should return the matched row count"

def test_create_index_duplicate_call(db, table):
    """Test that creating an index twice does not error and the index is recognized."""
    from datetime import datetime
    # Insert a new row to ensure the table exists
    table.insert({"date": datetime(2022, 1, 1), "temperature": 15, "place": "IndexCity"})
    # Create an index on the 'temperature' column twice
    table.create_index("temperature")
    table.create_index("temperature")
    assert table.has_index("temperature"), "Index on 'temperature' should exist after duplicate calls"

def test_find_with_in_operator(table):
    """Test filtering using the 'in' operator for the 'place' column."""
    from datetime import datetime
    # Insert rows with distinct place values
    table.insert({"date": datetime(2023, 1, 1), "temperature": 100, "place": "CityA"})
    table.insert({"date": datetime(2023, 1, 2), "temperature": 101, "place": "CityB"})
    table.insert({"date": datetime(2023, 1, 3), "temperature": 102, "place": "CityC"})
    rows = list(table.find(place={"in": ["CityA", "CityC"]}))
    places = [r.get("place", "") for r in rows]
    assert "CityA" in places and "CityC" in places, "Rows with CityA and CityC places should be found using 'in' operator"

def test_update_return_count_for_no_update(table):
    """Test that update returns a count when there is no non-key field to update."""
    from datetime import datetime
    row_data = {"date": datetime(2020, 1, 1), "temperature": 20, "place": "CountCity"}
    new_id = table.insert(row_data)
    # Update with keys only so that the update dict becomes empty
    count = table.update({
        "date": row_data["date"],
        "temperature": row_data["temperature"],
        "place": row_data["place"]
    }, ["place", "date"])
    assert count >= 1, "Update should return count of matched rows when update dict is empty"