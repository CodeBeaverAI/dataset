import pytest
from collections import namedtuple, OrderedDict
from urllib.parse import urlparse, parse_qs
from dataset.util import (
    convert_row,
    iter_result_proxy,
    make_sqlite_url,
    ResultIter,
    normalize_column_name,
    normalize_column_key,
    normalize_table_name,
    safe_url,
    index_name,
    pad_chunk_columns,
    DatasetException,
)
from sqlalchemy.exc import ResourceClosedError

class DummyResultProxy:
    """A dummy ResultProxy to simulate fetchall and fetchmany behavior."""
    def __init__(self, chunks, use_fetchall=True):
        self.chunks = chunks.copy()
        self.use_fetchall = use_fetchall

    def fetchall(self):
        if self.chunks:
            return self.chunks.pop(0)
        return []

    def fetchmany(self, size):
        if self.chunks:
            chunk = self.chunks.pop(0)
            return chunk[:size]
        return []

    def keys(self):
        return ['a', 'b']

    def close(self):
        pass

class DummyCursor:
    """A dummy cursor simulating sqlite cursor behavior."""
    def __init__(self, rows):
        self._rows = iter(rows)
        self.closed = False

    def keys(self):
        return ['a', 'b']

    def fetchmany(self, size):
        result = []
        try:
            for _ in range(size):
                result.append(next(self._rows))
        except StopIteration:
            pass
        return result

    def fetchall(self):
        return list(self._rows)

    def close(self):
        self.closed = True

class DummyCursorClosed:
    """A dummy cursor that immediately raises ResourceClosedError."""
    def keys(self):
        raise ResourceClosedError("Cursor closed")

    def close(self):
        pass

class TestUtil:
    """Test suite for functions in dataset/util.py"""

    def test_convert_row(self):
        """Test converting a namedtuple row into an OrderedDict."""
        Row = namedtuple("Row", ["a", "b"])
        row = Row(1, 2)
        result = convert_row(OrderedDict, row)
        assert isinstance(result, OrderedDict)
        assert result["a"] == 1
        assert result["b"] == 2

    def test_convert_row_none(self):
        """Test that convert_row returns None when the input row is None."""
        result = convert_row(OrderedDict, None)
        assert result is None

    def test_iter_result_proxy_fetchall(self):
        """Test iter_result_proxy using fetchall."""
        rows = [(1, 2), (3, 4)]
        rp = DummyResultProxy(chunks=[rows], use_fetchall=True)
        results = list(iter_result_proxy(rp))
        assert results == rows

    def test_iter_result_proxy_fetchmany(self):
        """Test iter_result_proxy using fetchmany with a specified step size."""
        rows = [(5, 6), (7, 8)]
        rp = DummyResultProxy(chunks=[rows], use_fetchall=False)
        results = list(iter_result_proxy(rp, step=1))
        # With step=1, fetchmany returns one row per call.
        assert results == [rows[0]]

    def test_make_sqlite_url_no_params(self):
        """Test make_sqlite_url without extra parameters."""
        path = "test.db"
        url = make_sqlite_url(path)
        assert url == "sqlite:///" + path

    def test_make_sqlite_url_with_params(self):
        """Test make_sqlite_url when using various extra parameters."""
        path = "test.db"
        url = make_sqlite_url(path, cache="shared", timeout=30, mode="rw", check_same_thread=False, immutable=True, nolock=True)
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        assert qs.get("cache") == ["shared"]
        assert qs.get("timeout") == ["30"]
        assert qs.get("mode") == ["rw"]
        assert qs.get("nolock") == ["1"]
        assert qs.get("immutable") == ["1"]
        assert qs.get("check_same_thread") == ["false"]
        assert qs.get("uri") == ["true"]

    def test_resultiter_iteration(self):
        """Test that ResultIter correctly wraps the cursor and converts rows."""
        rows = [tuple([1, 2]), tuple([3, 4])]
        Row = namedtuple("Row", ["a", "b"])
        rows = [Row(1, 2), Row(3, 4)]
        cursor = DummyCursor(rows)
        result_iter = ResultIter(cursor, row_type=OrderedDict, step=1)
        result_list = list(result_iter)
        expected = [OrderedDict([('a', 1), ('b', 2)]), OrderedDict([('a', 3), ('b', 4)])]
        assert result_list == expected
        # Verify that the cursor is closed after iteration.
        assert cursor.closed is True

    def test_resultiter_closed_cursor(self):
        """Test that ResultIter handles a cursor that raises ResourceClosedError."""
        cursor = DummyCursorClosed()
        result_iter = ResultIter(cursor, row_type=OrderedDict, step=1)
        result_list = list(result_iter)
        assert result_list == []

    def test_normalize_column_name_valid(self):
        """Test normalize_column_name with a valid input string."""
        name = "  valid_column  "
        normalized = normalize_column_name(name)
        assert normalized == "valid_column"

    def test_normalize_column_name_invalid_type(self):
        """Test that normalize_column_name raises ValueError when input is not a string."""
        with pytest.raises(ValueError):
            normalize_column_name(123)

    def test_normalize_column_name_invalid_chars(self):
        """Test normalize_column_name raises ValueError when name contains invalid characters."""
        with pytest.raises(ValueError):
            normalize_column_name("invalid.column")
        with pytest.raises(ValueError):
            normalize_column_name("invalid-column")

    def test_normalize_column_name_truncate(self):
        """Test that normalize_column_name properly truncates overly long names."""
        long_name = "a" * 70
        normalized = normalize_column_name(long_name)
        # Ensure that the UTF-8 encoded byte length is less than 64.
        assert len(normalized.encode("utf-8")) < 64

    def test_normalize_column_key(self):
        """Test normalize_column_key to verify trimming and uppercase conversion."""
        key = "  col Name "
        normalized = normalize_column_key(key)
        assert normalized == "COLNAME"
        assert normalize_column_key(None) is None

    def test_normalize_table_name_valid(self):
        """Test normalize_table_name with a valid input."""
        name = "  my_table  "
        normalized = normalize_table_name(name)
        assert normalized == "my_table"

    def test_normalize_table_name_invalid(self):
        """Test normalize_table_name raises ValueError for invalid table names."""
        with pytest.raises(ValueError):
            normalize_table_name("")
        with pytest.raises(ValueError):
            normalize_table_name(456)

    def test_safe_url_with_password(self):
        """Test that safe_url removes the password from the URL."""
        url = "postgresql://user:secret@localhost:5432/db"
        safe = safe_url(url)
        assert "secret" not in safe
        assert "*****" in safe

    def test_safe_url_without_password(self):
        """Test that safe_url returns the URL unchanged if no password is present."""
        url = "postgresql://user@localhost:5432/db"
        safe = safe_url(url)
        assert safe == url

    def test_index_name(self):
        """Test that index_name produces the correct artificial index name."""
        idx = index_name("table", ["col1", "col2"])
        assert idx.startswith("ix_table_")
        parts = idx.split("_")
        assert len(parts[-1]) == 16

    def test_pad_chunk_columns(self):
        """Test that pad_chunk_columns properly pads records with missing columns."""
        chunk = [{"a": 1}, {"b": 2}]
        columns = ["a", "b", "c"]
        padded = pad_chunk_columns(chunk, columns)
        for record in padded:
            for col in columns:
                assert col in record

    def test_dataset_exception(self):
        """Test that DatasetException can be raised and caught."""
        with pytest.raises(DatasetException):
            raise DatasetException("Test error")
    def test_iter_result_proxy_empty(self):
        """Test iter_result_proxy yields nothing when there are no rows."""
        rp = DummyResultProxy(chunks=[], use_fetchall=True)
        results = list(iter_result_proxy(rp))
        assert results == []

    def test_resultiter_manual_close(self):
        """Test that manually calling close on a ResultIter properly closes the cursor."""
        cursor = DummyCursor([])
        result_iter = ResultIter(cursor, row_type=OrderedDict, step=1)
        result_iter.close()
        assert cursor.closed is True

    def test_make_sqlite_url_invalid_cache(self):
        """Test that make_sqlite_url raises an AssertionError for an invalid cache value."""
        with pytest.raises(AssertionError):
            make_sqlite_url("test.db", cache="invalid")

    def test_make_sqlite_url_invalid_mode(self):
        """Test that make_sqlite_url raises an AssertionError for an invalid mode value."""
        with pytest.raises(AssertionError):
            make_sqlite_url("test.db", mode="invalid")

    def test_resultiter_iter_method(self):
        """Test that __iter__ of ResultIter returns the instance itself."""
        cursor = DummyCursor([])
        result_iter = ResultIter(cursor, row_type=OrderedDict, step=1)
        assert result_iter.__iter__() is result_iter

    def test_convert_row_invalid(self):
        """Test that convert_row raises an error when the row does not have a _fields attribute."""
        with pytest.raises(AttributeError):
            convert_row(OrderedDict, (1, 2))

    def test_normalize_column_key_empty(self):
        """Test that normalize_column_key returns an empty string when input is only whitespace."""
        normalized = normalize_column_key("     ")
        assert normalized == ""

    def test_index_name_consistency(self):
        """Test that index_name returns the same result when called twice with the same inputs, and different when columns order changes."""
        name1 = index_name("table", ["col1", "col2"])
        name2 = index_name("table", ["col1", "col2"])
        assert name1 == name2
        name3 = index_name("table", ["col2", "col1"])
        assert name1 != name3

    def test_pad_chunk_columns_already_full(self):
        """Test that pad_chunk_columns does not modify records that already contain all columns."""
        chunk = [{"a": 1, "b": 2, "c": 3}, {"a": 4, "b": 5, "c": 6}]
        columns = ["a", "b", "c"]
        padded = pad_chunk_columns(chunk, columns)
        assert padded == chunk

    def test_pad_chunk_columns_empty_chunk(self):
        """Test that pad_chunk_columns returns an empty list when given an empty chunk."""
        padded = pad_chunk_columns([], ["a", "b"])
        assert padded == []