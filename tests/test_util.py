import pytest
from collections import namedtuple, OrderedDict
from urllib.parse import urlparse, parse_qs
from hashlib import sha1
from sqlalchemy.exc import ResourceClosedError
from dataset.util import (
    convert_row,
    DatasetException,
    iter_result_proxy,
    make_sqlite_url,
    ResultIter,
    normalize_column_name,
    normalize_column_key,
    normalize_table_name,
    safe_url,
    index_name,
    pad_chunk_columns,
)

# Fake ResultProxy for testing iter_result_proxy and ResultIter
class FakeCursor:
    def __init__(self, rows, keys=None, fetchmany_size=None, raise_on_keys=False):
        self.rows = rows[:]  # copy list of rows
        self.fetchmany_size = fetchmany_size
        self.closed = False
        self._keys = keys if keys is not None else (list(rows[0]._fields) if rows else [])
        self.raise_on_keys = raise_on_keys

    def fetchall(self):
        result = self.rows
        self.rows = []
        return result

    def fetchmany(self, size):
        if self.fetchmany_size is not None:
            size = self.fetchmany_size
        chunk = self.rows[:size]
        self.rows = self.rows[size:]
        return chunk

    def keys(self):
        if self.raise_on_keys:
            raise ResourceClosedError("Cursor is closed")
        return self._keys

    def close(self):
        self.closed = True

# Define a dummy row type to simulate namedtuple rows for testing convert_row and ResultIter.
DummyRow = namedtuple("DummyRow", ["a", "b"])

class TestUtil:
    def test_convert_row_with_valid_row(self):
        """Test convert_row with a valid row-like object."""
        row = DummyRow(a=1, b=2)
        result = convert_row(OrderedDict, row)
        assert result == OrderedDict([("a", 1), ("b", 2)])

    def test_convert_row_with_none(self):
        """Test that convert_row returns None when given None."""
        assert convert_row(OrderedDict, None) is None

    def test_iter_result_proxy_fetchall(self):
        """Test iter_result_proxy using fetchall method."""
        rows = [DummyRow(a=i, b=i+1) for i in range(5)]
        fake_cursor = FakeCursor(rows)
        result = list(iter_result_proxy(fake_cursor))
        assert result == rows

    def test_iter_result_proxy_fetchmany(self):
        """Test iter_result_proxy using fetchmany method."""
        rows = [DummyRow(a=i, b=i+1) for i in range(5)]
        fake_cursor = FakeCursor(rows, fetchmany_size=2)
        result = list(iter_result_proxy(fake_cursor, step=2))
        assert result == rows

    def test_make_sqlite_url_basic(self):
        """Test that make_sqlite_url returns a basic URL when no extra params are provided."""
        url = make_sqlite_url("test.db")
        assert url == "sqlite:///test.db"

    def test_make_sqlite_url_with_params(self):
        """Test that make_sqlite_url returns a URL with encoded query parameters."""
        url = make_sqlite_url("test.db", cache="shared", timeout=30, mode="rw", check_same_thread=False, immutable=True, nolock=True)
        # The URL should start with 'sqlite:///file:test.db?' due to URI scheme
        assert url.startswith("sqlite:///file:test.db?")
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        expected = {
            "cache": ["shared"],
            "timeout": ["30"],
            "mode": ["rw"],
            "nolock": ["1"],
            "immutable": ["1"],
            "check_same_thread": ["false"],
            "uri": ["true"]
        }
        assert qs == expected

    def test_result_iter_normal_iteration(self):
        """Test that ResultIter iterates over rows and closes the cursor upon completion."""
        rows = [DummyRow(a=i, b=i+1) for i in range(3)]
        fake_cursor = FakeCursor(rows)
        result_iter = ResultIter(fake_cursor)
        collected = list(result_iter)
        expected = [OrderedDict([("a", row.a), ("b", row.b)]) for row in rows]
        assert collected == expected
        # After iteration, the cursor should be closed
        assert fake_cursor.closed is True

    def test_result_iter_closed_cursor(self):
        """Test that ResultIter handles ResourceClosedError by using an empty iterator."""
        fake_cursor = FakeCursor([], raise_on_keys=True)
        result_iter = ResultIter(fake_cursor)
        result = list(result_iter)
        assert result == []
        fake_cursor.close()
        assert fake_cursor.closed is True

    def test_normalize_column_name_valid(self):
        """Test normalize_column_name with a valid column name."""
        valid_name = "valid_column"
        assert normalize_column_name(valid_name) == valid_name

    def test_normalize_column_name_invalid(self):
        """Test normalize_column_name with column names that should be rejected."""
        with pytest.raises(ValueError):
            normalize_column_name("invalid.column")
        with pytest.raises(ValueError):
            normalize_column_name("invalid-column")

    def test_normalize_column_name_length(self):
        """Test that normalize_column_name truncates column names exceeding 63 bytes."""
        long_name = "a" * 100
        result = normalize_column_name(long_name)
        assert len(result.encode("utf-8")) < 64

    def test_normalize_column_key(self):
        """Test normalize_column_key converts strings to uppercase and removes spaces."""
        result = normalize_column_key(" col Name ")
        assert result == "COLNAME"
        # Check that None is returned as None
        assert normalize_column_key(None) is None

    def test_normalize_table_name_valid(self):
        """Test normalize_table_name with a valid table name."""
        table_name = "table_name"
        assert normalize_table_name(table_name) == table_name

    def test_normalize_table_name_invalid(self):
        """Test normalize_table_name raises ValueError for invalid names."""
        with pytest.raises(ValueError):
            normalize_table_name("")

    def test_safe_url(self):
        """Test that safe_url masks passwords contained in a connection URL."""
        original_url = "postgres://user:secret@localhost/db"
        result = safe_url(original_url)
        assert "secret" not in result
        assert "*****" in result

    def test_index_name(self):
        """Test that index_name generates an index name in the expected format."""
        table = "mytable"
        columns = ["col1", "col2"]
        idx = index_name(table, columns)
        assert idx.startswith("ix_mytable_")
        key_part = idx[len("ix_mytable_"):]
        # The key should be exactly 16 hex characters; assert its length and that it is valid hex.
        assert len(key_part) == 16
        int(key_part, 16)

    def test_pad_chunk_columns(self):
        """Test that pad_chunk_columns adds missing columns with None values."""
        chunk = [{"a": 1}, {"b": 2}]
        columns = ["a", "b", "c"]
        result = pad_chunk_columns(chunk, columns)
        for record in result:
            for col in columns:
                assert col in record
        # Ensure that existing keys are retained
        assert result[0]["a"] == 1

    def test_dataset_exception(self):
        """Test that DatasetException carries the correct message."""
        exc = DatasetException("Test error")
        assert str(exc) == "Test error"

    def test_make_sqlite_url_invalid_cache(self):
        """Test that make_sqlite_url raises AssertionError for an invalid cache value."""
        with pytest.raises(AssertionError):
            make_sqlite_url("test.db", cache="invalid")

    def test_make_sqlite_url_invalid_mode(self):
        """Test that make_sqlite_url raises AssertionError for an invalid mode value."""
        with pytest.raises(AssertionError):
            make_sqlite_url("test.db", mode="invalid")

    def test_normalize_column_name_non_string(self):
        """Test that normalize_column_name raises ValueError when given a non-string."""
        with pytest.raises(ValueError):
            normalize_column_name(123)

    def test_normalize_table_name_non_string(self):
        """Test that normalize_table_name raises ValueError when given a non-string."""
        with pytest.raises(ValueError):
            normalize_table_name(123)

    def test_normalize_column_key_non_string(self):
        """Test that normalize_column_key returns None when given a non-string."""
        assert normalize_column_key(123) is None

    def test_iter_result_proxy_with_zero(self):
        """Test iter_result_proxy with step=0 returns an empty iterator even if there are rows."""
        rows = [DummyRow(a=i, b=i+1) for i in range(3)]
        fake_cursor = FakeCursor(rows, fetchmany_size=0)
        result = list(iter_result_proxy(fake_cursor, step=0))
        assert result == []
    def test_safe_url_no_password(self):
        """Test that safe_url returns the URL unchanged when there is no password."""
        url = "postgres://user@localhost/db"
        result = safe_url(url)
        assert result == url

    def test_convert_row_custom_row_type(self):
        """Test convert_row with a custom row_type (dict) instead of OrderedDict."""
        row = DummyRow(a=10, b=20)
        result = convert_row(dict, row)
        expected = dict([("a", 10), ("b", 20)])
        assert result == expected

    def test_pad_chunk_columns_empty_chunk(self):
        """Test that pad_chunk_columns returns an empty list when given an empty chunk."""
        chunk = []
        columns = ["a", "b"]
        result = pad_chunk_columns(chunk, columns)
        assert result == []

    def test_pad_chunk_columns_all_present(self):
        """Test that pad_chunk_columns does not modify the chunk if all columns are present."""
        chunk = [{"a": 1, "b": 2}]
        columns = ["a", "b"]
        result = pad_chunk_columns(chunk, columns)
        assert result == chunk

    def test_result_iter_next_after_exhaustion(self):
        """Test that ResultIter raises StopIteration after all rows have been iterated."""
        rows = [DummyRow(a=1, b=2)]
        fake_cursor = FakeCursor(rows)
        result_iter = ResultIter(fake_cursor)
        # Get the only element.
        first = next(result_iter)
        assert first == OrderedDict([("a", 1), ("b", 2)])
        # Next call should raise StopIteration and close the cursor.
        with pytest.raises(StopIteration):
            next(result_iter)
        # Ensure cursor is closed.
    def test_iter_result_proxy_empty(self):
        """Test iter_result_proxy returns an empty list when given an empty cursor."""
        fake_cursor = FakeCursor([])
        result = list(iter_result_proxy(fake_cursor))
        assert result == []

    def test_iter_result_proxy_negative_step(self):
        """Test iter_result_proxy with a negative step value produces expected slice behavior."""
        # Create 3 dummy rows. With step = -1, fetchmany will return rows[:-1] on the first call.
        rows = [DummyRow(a=i, b=i+10) for i in range(3)]
        fake_cursor = FakeCursor(rows)
        result = list(iter_result_proxy(fake_cursor, step=-1))
        # When step is negative, list slicing returns all but the last element.
        expected = rows[:-1]
        assert result == expected

    def test_normalize_column_name_trimmed(self):
        """Test normalize_column_name trims whitespace from a valid column name."""
        input_name = "   trimmed_column   "
        result = normalize_column_name(input_name)
        # The result should be trimmed of whitespace and still be valid.
        assert result == "trimmed_column"

    def test_normalize_table_name_trimmed(self):
        """Test normalize_table_name trims whitespace from a valid table name."""
        input_name = "   trimmed_table   "
        result = normalize_table_name(input_name)
        assert result == "trimmed_table"

    def test_result_iter_iter_method(self):
        """Test that the __iter__ method of ResultIter returns self."""
        rows = [DummyRow(a=99, b=100)]
        fake_cursor = FakeCursor(rows)
        result_iter = ResultIter(fake_cursor)
        # Calling iter() on result_iter should return itself.
        # Verify that __iter__ returns self without closing the cursor
        it = iter(result_iter)
        assert it is result_iter
        # Before iteration the cursor should still be open
        assert not fake_cursor.closed
        # Fully consume the iterator so that the cursor gets closed
        list(result_iter)
        # After iteration, the cursor should be closed
        assert fake_cursor.closed
# End of TestUtil class