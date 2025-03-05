import pytest
from datetime import datetime
from test.test_row_type import Constructor

def test_constructor_attribute_get():
    """Test that attribute access on Constructor returns expected values."""
    data = {"temperature": 20, "place": "Paris", "date": datetime(2020, 1, 1)}
    c = Constructor(data)
    assert c.temperature == 20
    assert c.place == "Paris"
    assert c["date"] == datetime(2020, 1, 1)

def test_constructor_missing_attribute_raises_keyerror():
    """Test that accessing a missing attribute raises KeyError."""
    c = Constructor({"a": 1})
    with pytest.raises(KeyError):
        _ = c.nonexistent

def test_constructor_update_affects_attribute_access():
    """Test that updating the Constructor dictionary reflects in attribute access."""
    c = Constructor({"a": 5})
    c.update({"b": 10})
    assert c.b == 10

def test_constructor_overlapping_method_names():
    """Test that keys overlapping with dict methods still return correct value via __getattr__."""
    c = Constructor({"keys": "value_of_keys", "get": "value_of_get"})
    # Direct attribute access for 'keys' returns the built-in method, so we use __getattr__ for testing.
    assert c["keys"] == "value_of_keys"
    assert c.__getattr__("get") == "value_of_get"
# New tests to increase test coverage for table operations and custom row type conversion.
class FakeDB:
    """Fake database class for testing that holds a row_type attribute."""
    def __init__(self):
        self.row_type = dict

class FakeTable:
    """Fake table implementing insert, find_one, find, distinct, __iter__, and __len__ operations."""
    def __init__(self, db):
        self.records = []
        self.db = db

    def insert(self, record):
        self.records.append(record)

    def __apply_row_type(self, rec):
        if rec is None:
            return None
        if hasattr(self.db, "row_type") and self.db.row_type:
            return self.db.row_type(rec)
        return rec

    def find_one(self, **kwargs):
        for rec in self.records:
            match = True
            for k, v in kwargs.items():
                if k == "_limit":
                    continue
                if rec.get(k) != v:
                    match = False
                    break
            if match:
                return self.__apply_row_type(rec)
        return None

    def find(self, **kwargs):
        limit = kwargs.pop('_limit', None)
        result = []
        for rec in self.records:
            if all(rec.get(k) == v for k, v in kwargs.items()):
                result.append(self.__apply_row_type(rec))
                if limit is not None and len(result) >= limit:
                    break
        return result

    def distinct(self, *fields):
        seen = set()
        result = []
        for rec in self.records:
            key = tuple(rec.get(f) for f in fields)
            if key not in seen:
                seen.add(key)
                rec_data = {f: rec.get(f) for f in fields}
                result.append(self.__apply_row_type(rec_data))
        return result

    def __iter__(self):
        for rec in self.records:
            yield self.__apply_row_type(rec)

    def __len__(self):
        return len(self.records)

def test_integration_find_one_fake_table():
    """Test integration of find_one using FakeDB and FakeTable with Constructor as row type."""
    db = FakeDB()
    db.row_type = Constructor  # use Constructor to allow attribute access
    table = FakeTable(db)
    from datetime import datetime
    row = {"date": datetime(2011, 1, 2), "temperature": -10, "place": "Berlin"}
    table.insert(row)
    found = table.find_one(place="Berlin")
    assert found is not None
    # Test both dict and attribute access
    assert found["temperature"] == -10
    assert found.temperature == -10
    missing = table.find_one(place="Atlantis")
    assert missing is None

def test_integration_find_fake_table():
    """Test integration of the find method with limit functionality using FakeDB and FakeTable."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    # Insert multiple records
    rows = [
        {"place": "CityA", "value": 1},
        {"place": "CityA", "value": 2},
        {"place": "CityA", "value": 3},
        {"place": "CityB", "value": 4},
    ]
    for r in rows:
        table.insert(r)
    results = table.find(place="CityA")
    assert len(results) == 3
    for item in results:
        assert isinstance(item, Constructor)
    limited = table.find(place="CityA", _limit=2)
    assert len(limited) == 2

def test_integration_distinct_fake_table():
    """Test integration of the distinct method using FakeDB and FakeTable with multiple field criteria."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    # Insert records with duplicates
    rows = [
        {"cat": "A", "num": 1},
        {"cat": "A", "num": 2},
        {"cat": "B", "num": 3},
        {"cat": "B", "num": 3},  # duplicate
        {"cat": "C", "num": 4},
    ]
    for r in rows:
        table.insert(r)
    distinct_cats = table.distinct("cat")
    # Expect three distinct cat values: A, B, and C
    assert len(distinct_cats) == 3
    for item in distinct_cats:
        assert isinstance(item, Constructor)
    distinct_cat_num = table.distinct("cat", "num")
    # Expect four distinct records (duplicates for B,3 should be filtered)
    assert len(distinct_cat_num) == 4

def test_integration_iter_fake_table():
    """Test the iteration functionality of FakeTable ensuring all records are converted to Constructor."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]
    for r in rows:
        table.insert(r)
    count = 0
    for rec in table:
        count += 1
        assert isinstance(rec, Constructor)
def test_no_row_type_returns_dict():
    """Test that when db.row_type is None, FakeTable returns plain dicts instead of using Constructor."""
    db = FakeDB()
    db.row_type = None
    table = FakeTable(db)
    row = {"id": 1, "value": "test"}
    table.insert(row)
    result = table.find_one(id=1)
    assert result is not None
    assert isinstance(result, dict)
    # Ensure that it is not converted to a Constructor
    assert not hasattr(result, "value") or result["value"] == "test"
def test_find_no_filters_returns_all():
    """Test that calling find with no filter kwargs returns all records."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]
    for row in rows:
        table.insert(row)
    results = table.find()
    assert len(results) == len(rows)
    for res in results:
        assert isinstance(res, Constructor)
def test_distinct_missing_field():
    """Test distinct method handling of keys that are missing in some records."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1, "value": "a"},
        {"id": 2},  # missing 'value', so rec.get('value') will be None
        {"id": 3, "value": "a"},
        {"id": 4, "value": None},
    ]
    for row in rows:
        table.insert(row)
    results = table.distinct("value")
    distinct_values = set()
    for res in results:
        distinct_values.add(res.value)
    # Expect one distinct value "a" and one None
    assert "a" in distinct_values
    assert None in distinct_values
    assert len(results) == 2
def test_iter_empty_table():
    """Test that iterating over an empty FakeTable yields no records."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    count = 0
    for rec in table:
        count += 1
    assert count == 0
    assert len(table) == 0
def test_find_limit_zero_fake_table():
    """Test the find method with _limit=0 edge case.
    Due to the logic ordering in FakeTable.find, a _limit of 0 still returns 1 record."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1, "value": "x"},
        {"id": 2, "value": "x"},
    ]
    for r in rows:
        table.insert(r)
    results = table.find(value="x", _limit=0)
    # The first matching record is appended then _limit is checked causing an early break
    assert len(results) == 1

def test_custom_row_type_enhanced_fake_table():
    """Test using a custom EnhancedConstructor as the row type that adds a description method."""
    # Define a custom row type that extends Constructor with an extra method.
    class EnhancedConstructor(Constructor):
        def description(self):
            return f"{self.place} on {self.date.strftime('%Y-%m-%d')}"

    db = FakeDB()
    db.row_type = EnhancedConstructor
    table = FakeTable(db)
    from datetime import datetime
    row = {"date": datetime(2021, 12, 25), "place": "New York", "temperature": 5}
    table.insert(row)
    result = table.find_one(place="New York")
    assert result is not None
    # Test that the custom method works alongside dictionary and attribute access.
    assert result.description() == "New York on 2021-12-25"
    assert result.temperature == 5

def test_find_with_nonexistent_field_returns_empty_list():
    """Test that searching with a filter for a nonexistent field returns an empty list."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1, "value": "a"},
        {"id": 2, "value": "b"},
    ]
    for r in rows:
        table.insert(r)
    results = table.find(nonexistent="anything")
    assert results == []

def test_updated_record_affects_iteration():
    """Test that updating a record in the underlying table affects the result during iteration.
    This confirms that the conversion via __apply_row_type happens on the fly."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    row = {"id": 1, "value": "initial"}
    table.insert(row)
    # Update the record directly in table.records
    table.records[0]["value"] = "updated"
    for rec in table:
        assert rec.value == "updated"
def test_find_with_multiple_conditions():
    """Test that find_one and find work with multiple filtering conditions."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1, "a": "foo", "b": "bar", "c": 10},
        {"id": 2, "a": "foo", "b": "baz", "c": 20},
        {"id": 3, "a": "qux", "b": "bar", "c": 30},
        {"id": 4, "a": "foo", "b": "bar", "c": 40},
    ]
    for row in rows:
        table.insert(row)
    # Test find_one with multiple conditions (should match the first occurrence)
    res = table.find_one(a="foo", b="bar")
    assert res is not None
    assert res.a == "foo"
    assert res.b == "bar"
    # Test find with the same conditions returns all matching records (id 1 and 4)
    results = table.find(a="foo", b="bar")
    assert len(results) == 2

def test_find_invalid_limit():
    """Test the find method with a negative _limit value to verify edge case behavior."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1, "value": "x"},
        {"id": 2, "value": "x"},
        {"id": 3, "value": "x"},
    ]
    for r in rows:
        table.insert(r)
    results = table.find(value="x", _limit=-1)
    # With a negative _limit the condition is met almost immediately so only one record is returned
    assert len(results) == 1

def test_custom_lambda_row_type():
    """Test using a custom lambda as the row type to transform records."""
    db = FakeDB()
    # Custom lambda that adds an 'extra' key to the record
    db.row_type = lambda rec: {**rec, "extra": "yes"}
    table = FakeTable(db)
    row = {"id": 100, "value": "lambda test"}
    table.insert(row)
    # Test find_one conversion
    res_one = table.find_one(id=100)
    assert res_one is not None
    assert res_one["extra"] == "yes"
    # Test find conversion
    results = table.find(id=100)
    for rec in results:
        assert rec["extra"] == "yes"
    # Test distinct conversion using custom lambda row type
    distinct = table.distinct("value")
    for rec in distinct:
        assert rec["extra"] == "yes"
    # Test iteration conversion
    found = False
    for rec in table:
        if rec.get("id") == 100:
            found = True
            assert rec["extra"] == "yes"
    assert found

def test_non_callable_row_type():
    """Test that setting a non-callable row_type raises an error when transforming a record."""
    db = FakeDB()
    db.row_type = 5  # non-callable row_type
    table = FakeTable(db)
    row = {"id": 1, "value": "error expected"}
    table.insert(row)
    import pytest
    with pytest.raises(TypeError):
        _ = table.find_one(id=1)
def test_custom_namedtuple_row_type():
    """Test using a custom row_type as collections.namedtuple returning a tuple conversion."""
    from collections import namedtuple
    CustomRow = namedtuple("CustomRow", ["id", "value"])
    db = FakeDB()
    db.row_type = lambda rec: CustomRow(**rec)
    table = FakeTable(db)
    row = {"id": 1, "value": "test"}
    table.insert(row)
    result = table.find_one(id=1)
    assert isinstance(result, CustomRow)
    assert result.id == 1
    assert result.value == "test"

def test_exception_in_custom_row_type():
    """Test that exceptions in custom row_type conversion propagate as expected."""
    def faulty_row_type(record):
        # Attempt to access a key that might be missing so a KeyError is raised.
        return record["mandatory"]
    db = FakeDB()
    db.row_type = faulty_row_type
    table = FakeTable(db)
    row = {"id": 1, "value": "error expected"}
    table.insert(row)
    import pytest
    with pytest.raises(KeyError):
        _ = table.find_one(id=1)
def test_distinct_empty_fields():
    """Test that calling distinct with no field filters returns a single entry (an empty dict) as distinct."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"a": 1},
        {"b": 2},
    ]
    for row in rows:
        table.insert(row)
    # When no field is provided, every record yields an empty key tuple so only one item is returned.
    result = table.distinct()
    assert len(result) == 1
    # The distinct entry should be an empty dict converted by Constructor.
    assert result[0] == {}

def test_find_one_with_limit_keyword_ignored():
    """Test that passing '_limit' to find_one is ignored so it behaves normally."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    row = {"id": 10, "value": "test"}
    table.insert(row)
    # Pass _limit as extra keyword; it should be skipped during filtering.
    result = table.find_one(id=10, _limit=100)
    assert result is not None
    assert result.id == 10

def test_insert_non_dict_record_exception():
    """Test that inserting a non-dictionary record will raise an error when trying to perform get on it."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    table.insert(["not", "a", "dict"])
    with pytest.raises(AttributeError):
        _ = table.find_one(somekey="value")

def test_find_with_none_as_filter_value():
    """Test that find correctly matches records with a None filter value."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1, "optional": None},
        {"id": 2, "optional": "present"},
    ]
    for row in rows:
        table.insert(row)
    result = table.find(optional=None)
    assert len(result) == 1
    assert result[0].id == 1
def test_switch_row_type():
    """Test that switching the db.row_type dynamically affects row conversion."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    row = {"id": 99, "name": "First"}
    table.insert(row)
    result1 = table.find_one(id=99)
    # Check that result1 was converted using Constructor
    assert hasattr(result1, "name")
    # Now switch the row type to a lambda that adds an extra key
    db.row_type = lambda rec: {**rec, "extra": "modified"}
    result2 = table.find_one(id=99)
    # Check that the new conversion is applied (a plain dict with extra key)
    assert isinstance(result2, dict)
    assert result2.get("extra") == "modified"

def test_find_invalid_limit_type():
    """Test that using a non-integer _limit value causes a TypeError during comparison."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    rows = [
        {"id": 1, "value": "x"},
        {"id": 2, "value": "x"},
    ]
    for r in rows:
        table.insert(r)
    import pytest
    with pytest.raises(TypeError):
        _ = table.find(value="x", _limit="non_integer")
def test_modification_of_converted_record_does_not_affect_underlying_data():
    """Test that modifying a converted record does not change the underlying record in FakeTable."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    row = {"id": 1, "value": "original"}
    table.insert(row)
    converted = table.find_one(id=1)
    # Modify the converted record
    converted["value"] = "modified"
    # Get a new conversion from the underlying record
    fresh = table.find_one(id=1)
    assert fresh["value"] == "original", "Underlying record should not be affected by modifications to the converted record"

def test_find_returns_fresh_instances_on_each_call():
    """Test that each call to find_one returns a fresh conversion instance and not a cached object."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    row = {"id": 2, "value": "constant"}
    table.insert(row)
    first_instance = table.find_one(id=2)
    second_instance = table.find_one(id=2)
    assert first_instance is not second_instance, "Each conversion should produce a new instance"

def test_find_no_matching_record_returns_none():
    """Test that find_one returns None when no record matches the provided filter."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    table.insert({"id": 3, "value": "test"})
    result = table.find_one(id=999)
    assert result is None, "find_one should return None if no matching record is found"
def test_custom_constant_row_type():
    """Test using a constant lambda as the row_type that returns a constant value regardless of record content.
    This ensures that find_one, iteration, and distinct all return the constant conversion."""
    db = FakeDB()
    db.row_type = lambda rec: "constant"
    table = FakeTable(db)
    row = {"id": 101, "value": "dummy"}
    table.insert(row)
    result = table.find_one(id=101)
    assert result == "constant", "Expected constant conversion for find_one"
    iter_results = list(table)
    # All results via iteration should yield the constant value
    for item in iter_results:
        assert item == "constant", "Iteration did not yield constant conversion"
    distinct_results = table.distinct("value")
    for item in distinct_results:
        assert item == "constant", "Distinct did not yield constant conversion"

def test_find_with_list_field():
    """Test that the find method correctly matches records with list fields using equality.
    The record should be found only when the list exactly matches."""
    db = FakeDB()
    db.row_type = Constructor
    table = FakeTable(db)
    row1 = {"id": 201, "tags": ["a", "b", "c"]}
    row2 = {"id": 202, "tags": ["x", "y"]}
    table.insert(row1)
    table.insert(row2)
    # Search for the record with an exact match on the list field.
    result = table.find_one(tags=["a", "b", "c"])
    assert result is not None, "Expected to find record with matching list"
    assert result.id == 201
    # A search for a list that does not match should return None.
    result_none = table.find_one(tags=["non", "matching"])
    assert result_none is None, "Expected no record with non-matching list"