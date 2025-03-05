import pytest
from collections import namedtuple, OrderedDict
from urllib.parse import urlparse, parse_qs
from hashlib import sha1
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
    QUERY_STEP,
    row_type
)

class DummyResultProxy:
    """A dummy result proxy to simulate fetchall and fetchmany behavior."""
    def __init__(self, chunks):
        self.chunks = chunks
        self.index = 0
    def fetchall(self):
        if self.index < len(self.chunks):
            result = self.chunks[self.index]
            self.index += 1
            return result
        return []
    def fetchmany(self, size):
        if self.index < len(self.chunks):
            result = self.chunks[self.index]
            self.index += 1
            return result
        return []

class DummyClosedCursor:
    """A dummy cursor that simulates an already closed resource."""
    def keys(self):
        from sqlalchemy.exc import ResourceClosedError
        raise ResourceClosedError
    def close(self):
        pass

class TestUtil:
    def test_convert_row_valid(self):
        """Test convert_row with a valid row object."""
        DummyRow = namedtuple("DummyRow", ["a", "b"])
        row_obj = DummyRow(1, "x")
        result = convert_row(OrderedDict, row_obj)
        assert result == OrderedDict([("a", 1), ("b", "x")])

    def test_convert_row_none(self):
        """Test convert_row with None as row."""
        result = convert_row(OrderedDict, None)
        assert result is None

    def test_iter_result_proxy_fetchall(self):
        """Test iter_result_proxy using fetchall."""
        DummyRow = namedtuple("DummyRow", ["a", "b"])
        rows = [DummyRow(1, "x"), DummyRow(2, "y")]
        rp = DummyResultProxy(chunks=[rows])
        iterator = iter_result_proxy(rp)
        collected = list(iterator)
        assert collected == rows

    def test_iter_result_proxy_fetchmany(self):
        """Test iter_result_proxy using fetchmany with step size."""
        DummyRow = namedtuple("DummyRow", ["a", "b"])
        rows_part1 = [DummyRow(1, "x")]
        rows_part2 = [DummyRow(2, "y")]
        rp = DummyResultProxy(chunks=[rows_part1, rows_part2])
        iterator = iter_result_proxy(rp, step=1)
        collected = list(iterator)
        assert collected == rows_part1 + rows_part2

    def test_make_sqlite_url_default(self):
        """Test make_sqlite_url with default parameters."""
        url = make_sqlite_url("test.db")
        assert url == "sqlite:///test.db"

    def test_make_sqlite_url_with_params(self):
        """Test make_sqlite_url with various parameters."""
        url = make_sqlite_url("test.db", cache="shared", timeout=30, mode="ro", check_same_thread=False, immutable=True, nolock=True)
        # URL should start with 'sqlite:///file:test.db?' and include parameters
        assert url.startswith("sqlite:///file:test.db?")
        query = url.split("?", 1)[1]
        params = parse_qs(query)
        assert params.get("cache") == ["shared"]
        assert params.get("timeout") == ["30"]
        assert params.get("mode") == ["ro"]
        assert params.get("nolock") == ["1"]
        assert params.get("immutable") == ["1"]
        assert params.get("check_same_thread") == ["false"]
        assert params.get("uri") == ["true"]

    def test_result_iter_normal(self):
        """Test ResultIter normal behavior."""
        DummyRow = namedtuple("DummyRow", ["a", "b"])
        rows = [DummyRow(1, "x"), DummyRow(2, "y")]
        # Create a dummy cursor for ResultIter
        class DummyCursorForResultIter:
            def __init__(self, rows):
                self.rows = rows
                self.index = 0
            def keys(self):
                return list(self.rows[0]._fields) if self.rows else []
            def fetchall(self):
                if self.index == 0:
                    self.index = len(self.rows)
                    return self.rows
                return []
            def close(self):
                self.closed = True
        cursor = DummyCursorForResultIter(rows)
        iter_obj = ResultIter(cursor, row_type=OrderedDict)
        collected = list(iter_obj)
        expected = [OrderedDict(zip(r._fields, r)) for r in rows]
        assert collected == expected

    def test_result_iter_closed(self):
        """Test ResultIter with a closed cursor that raises ResourceClosedError."""
        cursor = DummyClosedCursor()
        iter_obj = ResultIter(cursor)
        # Since the cursor raises ResourceClosedError, keys should be empty and iteration should be empty
        assert iter_obj.keys == []
        with pytest.raises(StopIteration):
            next(iter_obj)

    def test_normalize_column_name_valid(self):
        """Test normalize_column_name with valid name."""
        valid_name = "  column_name  "
        normalized = normalize_column_name(valid_name)
        # Should be trimmed and valid (not containing dots or dashes and within 63 characters)
        assert normalized == "column_name"

    def test_normalize_column_name_invalid(self):
        """Test normalize_column_name with invalid names."""
        with pytest.raises(ValueError):
            normalize_column_name("column.name")
        with pytest.raises(ValueError):
            normalize_column_name("column-name")
        with pytest.raises(ValueError):
            normalize_column_name("   ")  # empty after stripping

    def test_normalize_column_key(self):
        """Test normalize_column_key transforms to uppercase and removes spaces."""
        assert normalize_column_key("column key") == "COLUMNKEY"
        assert normalize_column_key(" Column ") == "COLUMN"
        assert normalize_column_key(None) is None

    def test_normalize_table_name_valid(self):
        """Test normalize_table_name with a valid table name."""
        table_name = "  MyTable   "
        normalized = normalize_table_name(table_name)
        assert normalized == "MyTable"

    def test_normalize_table_name_invalid(self):
        """Test normalize_table_name with an invalid table name."""
        with pytest.raises(ValueError):
            normalize_table_name("   ")
        with pytest.raises(ValueError):
            normalize_table_name(123)

    def test_safe_url(self):
        """Test safe_url to ensure the password is hidden."""
        url_with_pwd = "postgresql://user:secret@localhost/db"
        safe = safe_url(url_with_pwd)
        assert "secret" not in safe
        assert "*****" in safe
        # URL without a password should remain unchanged
        url_no_pwd = "postgresql://user@localhost/db"
        assert safe_url(url_no_pwd) == url_no_pwd

    def test_index_name(self):
        """Test index_name generates a valid index name."""
        table = "mytable"
        columns = ["col1", "col2"]
        ix = index_name(table, columns)
        # Check that the index name starts with "ix_mytable_" and has proper length.
        assert ix.startswith("ix_mytable_")
        key_part = ix.split("_")[-1]
        assert len(key_part) == 16

    def test_pad_chunk_columns(self):
        """Test pad_chunk_columns ensures each record has the required columns."""
        chunk = [{"a": 1}, {"b": 2}, {"a": 3, "c": 4}]
        columns = ["a", "b", "c"]
        padded = pad_chunk_columns(chunk, columns)
        for record in padded:
            for col in columns:
                assert col in record
        # Check that missing columns are padded with None.
        assert padded[0]["b"] is None
        assert padded[0]["c"] is None
        assert padded[1]["a"] is None
        assert padded[1]["c"] is None

    def test_normalize_column_name_long(self):
        """Test that normalize_column_name trims long names to fit 63 chars and ensures utf-8 byte length is less than 64."""
        long_name = "a" * 100
        normalized = normalize_column_name(long_name)
        # For ASCII all characters are 1 byte, so should be exactly 63 characters
        assert len(normalized) == 63

    def test_normalize_column_name_non_string(self):
        """Test that normalize_column_name raises ValueError for non-string inputs."""
        with pytest.raises(ValueError):
            normalize_column_name(12345)

    def test_make_sqlite_url_timeout_only(self):
        """Test make_sqlite_url with only the timeout parameter provided."""
        url = make_sqlite_url("test_timeout.db", timeout=10)
        assert url.startswith("sqlite:///file:test_timeout.db?")
        query = url.split("?", 1)[1]
        params = parse_qs(query)
        assert params.get("timeout") == ["10"]
        assert params.get("uri") == ["true"]

    def test_pad_chunk_columns_empty_chunk(self):
        """Test that pad_chunk_columns returns an empty list when provided an empty chunk."""
        chunk = []
        columns = ["a", "b"]
        padded = pad_chunk_columns(chunk, columns)
        assert padded == []

    def test_index_name_empty_columns(self):
        """Test index_name with an empty list of columns produces a valid index name."""
        ix = index_name("table", [])
        expected_hash = sha1("".encode("utf-8")).hexdigest()[:16]
        expected = "ix_table_" + expected_hash
        assert ix == expected

    def test_result_iter_next_after_iteration(self):
        """Test that calling next() after exhausting the ResultIter raises StopIteration consistently."""
        DummyRow = namedtuple("DummyRow", ["a", "b"])
        rows = [DummyRow(1, "x")]
        class DummyCursorForNextTest:
            def __init__(self, rows):
                self.rows = rows
                self.index = 0
            def keys(self):
                return list(self.rows[0]._fields) if self.rows else []
            def fetchall(self):
                if self.index == 0:
                    self.index = len(self.rows)
                    return self.rows
                return []
            def close(self):
                self.closed = True
        cursor = DummyCursorForNextTest(rows)
        iter_obj = ResultIter(cursor, row_type=OrderedDict)
        # Exhaust the iterator
        list(iter_obj)
        with pytest.raises(StopIteration):
            next(iter_obj)

    def test_iter_result_proxy_empty_initially(self):
        pass
    def test_result_iter_calls_close(self):
        """Test that ResultIter.close() is called after iteration is exhausted."""
        DummyRow = namedtuple("DummyRow", ["a"])
        rows = [DummyRow(1)]
        closed_flag = {"closed": False}
        class DummyCursorForClose:
            def __init__(self, rows):
                self.rows = rows
                self.index = 0
            def keys(self):
                return list(self.rows[0]._fields) if self.rows else []
            def fetchall(self):
                if self.index == 0:
                    self.index = len(self.rows)
                    return self.rows
                return []
            def close(self):
                closed_flag["closed"] = True
        cursor = DummyCursorForClose(rows)
        iter_obj = ResultIter(cursor, row_type=OrderedDict)
        # Force the iterator to exhaust
        list(iter_obj)
        assert closed_flag["closed"] is True

    def test_normalize_column_name_multibyte(self):
        """Test that normalize_column_name trims multibyte names to adhere to the utf-8 byte limit."""
        # Use a multibyte character (e.g., "é": 2 bytes in utf-8); 70 instances
        multi_byte_name = "é" * 70
        normalized = normalize_column_name(multi_byte_name)
        # Check that the utf-8 encoding of normalized is less than 64 bytes
        assert len(normalized.encode("utf-8")) < 64

    def test_convert_row_invalid(self):
        """Test convert_row with an object that does not have a _fields attribute."""
        class NoFields:
            pass
        with pytest.raises(AttributeError):
            convert_row(OrderedDict, NoFields())
        """Test that iter_result_proxy returns an empty iterator when no rows are fetched."""
        rp = DummyResultProxy(chunks=[])
        iterator = iter_result_proxy(rp)
        collected = list(iterator)
        assert collected == []
# End of tests for dataset/util.py