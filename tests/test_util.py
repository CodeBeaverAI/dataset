import pytest
from collections import OrderedDict, namedtuple
from urllib.parse import urlparse, parse_qs
from dataset.util import (convert_row, iter_result_proxy, make_sqlite_url, ResultIter,
                            normalize_column_name, normalize_column_key, normalize_table_name,
                            safe_url, index_name, pad_chunk_columns, row_type, QUERY_STEP)
from sqlalchemy.exc import ResourceClosedError

# A fake ResultProxy object to simulate fetchall, fetchmany, keys and close behavior.
class FakeResultProxy:
    def __init__(self, data, step=None):
        self.data = data
        self.index = 0
        self.step = step

    def fetchall(self):
        if self.index >= len(self.data):
            return []
        chunk = self.data[self.index:]
        self.index = len(self.data)
        return chunk

    def fetchmany(self, size):
        if self.index >= len(self.data):
            return []
        chunk = self.data[self.index:self.index+size]
        self.index += size
        return chunk

    def keys(self):
        if self.data:
            # Assume that each row is a namedtuple having _fields
            return list(self.data[0]._fields) if hasattr(self.data[0], "_fields") else []
        return []

    def close(self):
        pass

def test_convert_row_valid():
    """Test convert_row with a valid namedtuple row."""
    TestRow = namedtuple("TestRow", ["a", "b"])
    row = TestRow(1, 2)
    result = convert_row(OrderedDict, row)
    assert isinstance(result, OrderedDict)
    assert result["a"] == 1
    assert result["b"] == 2

def test_convert_row_none():
    """Test convert_row with None input."""
    assert convert_row(OrderedDict, None) is None

def test_iter_result_proxy_fetchall():
    """Test iter_result_proxy using fetchall method."""
    TestRow = namedtuple("TestRow", ["a"])
    data = [TestRow(1), TestRow(2)]
    rp = FakeResultProxy(data)
    results = list(iter_result_proxy(rp))
    assert len(results) == 2
    assert results[0].a == 1
    assert results[1].a == 2

def test_iter_result_proxy_fetchmany():
    """Test iter_result_proxy using fetchmany method with step parameter."""
    TestRow = namedtuple("TestRow", ["a"])
    data = [TestRow(10), TestRow(20), TestRow(30)]
    rp = FakeResultProxy(data)
    results = list(iter_result_proxy(rp, step=2))
    assert len(results) == 3
    assert results[0].a == 10
    assert results[2].a == 30

def test_make_sqlite_url_no_params():
    """Test make_sqlite_url with no optional parameters."""
    path = "test.db"
    url = make_sqlite_url(path)
    assert url == "sqlite:///" + path

def test_make_sqlite_url_with_params():
    """Test make_sqlite_url with various parameters."""
    path = "test.db"
    url = make_sqlite_url(path, cache="shared", timeout=5.0, mode="ro",
                            check_same_thread=False, immutable=True, nolock=True)
    # Expect URL to start with schema "sqlite:///file:test.db?"
    assert url.startswith("sqlite:///file:" + path + "?")
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert qs.get("cache") == ["shared"]
    assert qs.get("timeout") == ["5.0"]
    assert qs.get("mode") == ["ro"]
    assert qs.get("nolock") == ["1"]
    assert qs.get("immutable") == ["1"]
    assert qs.get("check_same_thread") == ["false"]
    assert qs.get("uri") == ["true"]

def test_result_iter_normal():
    """Test ResultIter iteration with normal data."""
    TestRow = namedtuple("TestRow", ["a", "b"])
    data = [TestRow(1, 2), TestRow(3, 4)]
    rp = FakeResultProxy(data)
    result_iter = ResultIter(rp, row_type=OrderedDict, step=1)
    rows = list(result_iter)
    assert len(rows) == 2
    assert rows[0]["a"] == 1
    result_iter.close()  # should not raise an exception

def test_result_iter_resource_closed():
    """Test ResultIter handles ResourceClosedError."""
    class FakeClosedCursor:
        def keys(self):
            raise ResourceClosedError
        def close(self):
            pass
    fake_cursor = FakeClosedCursor()
    result_iter = ResultIter(fake_cursor)
    rows = list(result_iter)
    assert rows == []

def test_normalize_column_name_valid():
    """Test normalize_column_name with valid names."""
    name = " valid_name "
    norm = normalize_column_name(name)
    assert " " not in norm
    assert len(norm) <= 63

def test_normalize_column_name_invalid():
    """Test normalize_column_name with invalid names containing '.' or '-'."""
    with pytest.raises(ValueError):
        normalize_column_name("inva.lid")
    with pytest.raises(ValueError):
        normalize_column_name("inva-lid")

def test_normalize_column_name_non_string():
    """Test normalize_column_name with non-string input."""
    with pytest.raises(ValueError):
        normalize_column_name(123)

def test_normalize_column_name_length():
    """Test normalize_column_name trims name to 63 bytes max considering UTF-8 encoding."""
    long_name = "a" * 100
    norm = normalize_column_name(long_name)
    assert len(norm.encode("utf-8")) < 64

def test_normalize_column_key():
    """Test normalize_column_key returns upper case without spaces and None for invalid values."""
    assert normalize_column_key(" column ") == "COLUMN"
    assert normalize_column_key(None) is None

def test_normalize_table_name_valid():
    """Test normalize_table_name with valid input."""
    name = " my_table "
    norm = normalize_table_name(name)
    assert norm == name.strip()[:63]

def test_normalize_table_name_invalid():
    """Test normalize_table_name raises error on invalid table names."""
    with pytest.raises(ValueError):
        normalize_table_name("")
    with pytest.raises(ValueError):
        normalize_table_name(123)

def test_safe_url_no_password():
    """Test safe_url does not modify a URL with no password."""
    url = "sqlite:///test.db"
    safe = safe_url(url)
    assert safe == url

def test_safe_url_with_password():
    """Test safe_url masks the password in the URL."""
    url = "postgresql://user:secret@localhost/db"
    safe = safe_url(url)
    assert "secret" not in safe
    assert ":*****@" in safe

def test_index_name():
    """Test index_name generates a valid index name."""
    table = "mytable"
    columns = ["col1", "col2"]
    idx = index_name(table, columns)
    assert idx.startswith("ix_" + table + "_")
    parts = idx.split("_")
    assert len(parts[-1]) == 16

def test_pad_chunk_columns():
    """Test pad_chunk_columns adds missing columns with None."""
    chunk = [{"a": 1}, {"b": 2}, {"a": 3, "b": 4}]
    columns = ["a", "b", "c"]
    padded = pad_chunk_columns(chunk, columns)
    for record in padded:
        for col in columns:
            assert col in record

def test_pad_chunk_columns_empty():
    """Test pad_chunk_columns with an empty chunk."""
    padded = pad_chunk_columns([], ["a", "b"])
    assert padded == []
def test_iter_result_proxy_empty():
    """Test iter_result_proxy yields nothing when there is no data."""
    rp = FakeResultProxy([])
    results = list(iter_result_proxy(rp))
    assert results == []

def test_index_name_empty_columns():
    """Test index_name generates a valid index name even with an empty columns list."""
    from hashlib import sha1
    table = "test_table"
    columns = []
    idx = index_name(table, columns)
    expected_key = sha1("".encode("utf-8")).hexdigest()[:16]
    expected = "ix_%s_%s" % (table, expected_key)
    assert idx == expected

def test_convert_row_empty_fields():
    """Test convert_row with a namedtuple that has no fields."""
    TestRow = namedtuple("TestRow", [])
    row = TestRow()
    result = convert_row(OrderedDict, row)
    assert isinstance(result, OrderedDict)
    assert len(result) == 0

def test_normalize_column_name_empty_after_strip():
    """Test normalize_column_name raises a ValueError when name is empty after stripping."""
    with pytest.raises(ValueError):
        normalize_column_name("    ")

def test_normalize_table_name_whitespace():
    """Test normalize_table_name raises a ValueError when name is only whitespace."""
    with pytest.raises(ValueError):
        normalize_table_name("    ")
def test_make_sqlite_url_invalid_cache():
    """Test make_sqlite_url raises AssertionError when an invalid cache value is provided."""
    with pytest.raises(AssertionError):
        make_sqlite_url("test.db", cache="invalid")

def test_make_sqlite_url_invalid_mode():
    """Test make_sqlite_url raises AssertionError when an invalid mode value is provided."""
    with pytest.raises(AssertionError):
        make_sqlite_url("test.db", mode="invalid")

def test_result_iter_iter_returns_self():
    """Test that __iter__ returns self for ResultIter objects."""
    TestRow = namedtuple("TestRow", ["a"])
    data = [TestRow(1)]
    rp = FakeResultProxy(data)
    iter_obj = ResultIter(rp)
    # __iter__ should return the object itself
    assert iter(iter_obj) is iter_obj

def test_pad_chunk_columns_non_dict():
    """Test that pad_chunk_columns raises AttributeError when a record is not a dict."""
    # Here we pass a list of tuples (not dict objects)
    chunk = [("a", 1), ("b", 2)]
    with pytest.raises(AttributeError):
        pad_chunk_columns(chunk, ["a", "b"])

def test_normalize_column_key_non_string():
    """Test that normalize_column_key returns None when provided a non-string input."""
    assert normalize_column_key(123) is None

def test_safe_url_empty_password():
    """Test that safe_url masks the password when the URL contains an empty password."""
    url = "postgresql://user:@localhost/db"
    safe = safe_url(url)
    # Check that the empty password gets replaced by :*****@
    assert ":*****@" in safe

def test_result_iter_close_called():
    """Test that calling close on a ResultIter instance calls the underlying cursor's close method."""
    class Dummy:
        def __init__(self):
            self.closed = False
        def close(self):
            self.closed = True
        def keys(self):
            return ["a"]
    dummy = Dummy()
    result_iter = ResultIter(dummy)
    result_iter.close()
    assert dummy.closed is True
def test_make_sqlite_url_check_same_thread_true():
    """Test that make_sqlite_url returns URL without extra parameters if check_same_thread is True."""
    path = "test.db"
    url = make_sqlite_url(path, check_same_thread=True)
    # When no optional parameter is provided, it should simply return the basic URL.
    assert url == "sqlite:///" + path

def test_convert_row_invalid_row():
    """Test that convert_row raises an AttributeError when row does not have _fields attribute."""
    class Dummy:
        a = 1
    dummy = Dummy()
    with pytest.raises(AttributeError):
        convert_row(OrderedDict, dummy)

def test_safe_url_special_characters():
    """Test that safe_url correctly masks passwords that contain special characters."""
    url = "postgresql://user:my$ecret*pass@localhost/db"
    safe = safe_url(url)
    # Ensure that the original password does not appear in the safe URL.
    assert "my$ecret*pass" not in safe
    assert ":*****@" in safe

def test_pad_chunk_columns_overrides_none():
    """Test that pad_chunk_columns does not override keys that already exist, even if they are None."""
    chunk = [{"a": None}, {"b": 2}]
    columns = ["a", "b", "c"]
    padded = pad_chunk_columns(chunk, columns)
    # The existing 'a' with a value of None should not be changed;
    # missing keys 'b' and 'c' should be added where they do not already exist.
    assert padded[0]["a"] is None
    assert "b" in padded[0]
    assert "c" in padded[0]

def test_result_iter_multiple_iterations():
    """Test that iterating a ResultIter once exhausts it and further calls to next() raise StopIteration."""
    TestRow = namedtuple("TestRow", ["a"])
    data = [TestRow(1), TestRow(2)]
    rp = FakeResultProxy(data)
    iter_obj = ResultIter(rp, row_type=OrderedDict, step=1)
    result1 = list(iter_obj)
    # Now iter_obj should be exhausted. Next call to next() should raise StopIteration.
    with pytest.raises(StopIteration):
        next(iter_obj)

def test_normalize_column_key_empty_string():
    """Test that normalize_column_key returns an empty string when provided with a whitespace-only string."""
    result = normalize_column_key("    ")
    # The string returns empty due to stripping spaces.
    assert result == ""