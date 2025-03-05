import pytest
import itertools

from dataset.chunked import ChunkedInsert, ChunkedUpdate, InvalidCallback

class DummyTable:
    def __init__(self):
        self.inserted = []
        self.updated = []

    def insert_many(self, items):
        # capture a copy to avoid mutation issues
        self.inserted.append(list(items))

    def update_many(self, items, keys):
        self.updated.append((list(items), keys))

# Tests for ChunkedInsert

def test_chunked_insert_invalid_callback():
    """Test that invalid callback raises InvalidCallback."""
    dummy = DummyTable()
    with pytest.raises(InvalidCallback):
        ChunkedInsert(dummy, callback="not_callable")

def test_chunked_insert_auto_flush():
    """Test that insert auto flushes when chunk size is reached and callback is executed."""
    dummy = DummyTable()
    callback_calls = []
    def callback(queue):
        callback_calls.append(list(queue))  # capture snapshot of the queue before insertion
    inserter = ChunkedInsert(dummy, chunksize=2, callback=callback)
    # Insert two items; first item is buffered, second triggers flush.
    row1 = {"a": 1}
    row2 = {"b": 2}
    inserter.insert(row1)
    # At this point, the queue has one item.
    assert len(inserter.queue) == 1
    inserter.insert(row2)  # triggers flush
    # After flush, queue should be empty.
    assert len(inserter.queue) == 0
    # Verify callback was called exactly once.
    assert len(callback_calls) == 1
    # Check that inserted items have fields normalized: each row contains all keys seen so far.
    inserted = dummy.inserted[0]
    for item in inserted:
        assert "a" in item
        assert "b" in item

def test_chunked_insert_manual_flush():
    """Test that manual flush works correctly for ChunkedInsert."""
    dummy = DummyTable()
    inserter = ChunkedInsert(dummy, chunksize=3)
    row = {"x": 10}
    inserter.insert(row)
    # Queue is not auto flushed because chunksize is not reached.
    assert len(inserter.queue) == 1
    inserter.flush()  # manually flush
    assert len(inserter.queue) == 0
    assert len(dummy.inserted) == 1
    # After flush, the row should contain the key "x".
    assert dummy.inserted[0][0]["x"] == 10

def test_chunked_insert_context_manager():
    """Test that ChunkedInsert works correctly as a context manager."""
    dummy = DummyTable()
    with ChunkedInsert(dummy, chunksize=5) as inserter:
        inserter.insert({"p": 100})
        inserter.insert({"q": 200})
        # Not reaching chunksize, so queue should be pending
        assert len(inserter.queue) == 2
    # On context exit, flush should have been automatically called.
    assert len(dummy.inserted) == 1
    # Verify that fields are normalized across inserted rows.
    inserted = dummy.inserted[0]
    for item in inserted:
        # The union of seen keys is {"p", "q"}.
        assert "p" in item
        assert "q" in item

# Tests for ChunkedUpdate

def test_chunked_update_auto_flush():
    """Test that update auto flushes and groups rows correctly with callback."""
    dummy = DummyTable()
    callback_calls = []
    def callback(queue):
        callback_calls.append(list(queue))
    updater = ChunkedUpdate(dummy, keys=["id"], chunksize=2, callback=callback)
    # Prepare updates with the same keys.
    row1 = {"id": 1, "val": "a"}
    row2 = {"id": 1, "val": "b"}
    updater.update(row1)
    # Queue not flushed yet.
    assert len(updater.queue) == 1
    updater.update(row2)  # triggers flush
    # After flush, queue should be empty.
    assert len(updater.queue) == 0
    # Callback should have been called once.
    assert len(callback_calls) == 1
    # Verify that update_many was called with grouped rows (both rows in one group since they share the same keys).
    assert len(dummy.updated) == 1
    group, keys_passed = dummy.updated[0]
    assert keys_passed == ["id"]
    assert len(group) == 2

def test_chunked_update_manual_flush_with_different_keys():
    """Test manual flush for ChunkedUpdate with rows having different keys."""
    dummy = DummyTable()
    updater = ChunkedUpdate(dummy, keys=["key"], chunksize=5)
    # Insert rows with different sets of keys.
    row1 = {"key": 1, "data": "x"}
    row2 = {"data": "y"}  # lacks key 'key'
    updater.update(row1)
    updater.update(row2)
    # Manually flush without reaching the chunksize.
    updater.flush()
    # Since groupby groups items based on dict.keys, these rows should fall into 2 distinct groups.
    assert len(dummy.updated) == 2

def test_chunked_update_context_manager():
    """Test that ChunkedUpdate works correctly as a context manager."""
    dummy = DummyTable()
    with ChunkedUpdate(dummy, keys=["uid"], chunksize=3) as updater:
        updater.update({"uid": 10, "status": "ok"})
        updater.update({"uid": 10, "status": "fail"})
    # Upon context exit, flush should have been automatically called.
    # Expect one group since both rows have the same keys.
    assert len(dummy.updated) == 1
    group, keys_passed = dummy.updated[0]
    assert keys_passed == ["uid"]
    assert len(group) == 2
def test_chunked_insert_empty_flush():
    """Test that flush on empty queue for ChunkedInsert calls the callback and insert_many even if no items exist."""
    dummy = DummyTable()
    callback_calls = []
    # Define a callback that appends a copy of the queue when called
    def callback(queue):
        callback_calls.append(list(queue))
    inserter = ChunkedInsert(dummy, chunksize=2, callback=callback)
    # Directly call flush even though no items have been inserted.
    inserter.flush()
    # flush calls callback (with empty queue) and insert_many with empty list.
    # DummyTable.insert_many will append an empty list to dummy.inserted.
    assert callback_calls == [[]]
    assert dummy.inserted == [[]]

def test_chunked_update_empty_flush():
    """Test that flush on empty queue for ChunkedUpdate calls the callback and update_many even if no items exist."""
    dummy = DummyTable()
    callback_calls = []
    def callback(queue):
        callback_calls.append(list(queue))
    updater = ChunkedUpdate(dummy, keys=["id"], chunksize=2, callback=callback)
    updater.flush()
    # Since there are no items, callback is called with an empty list and update_many is never invoked.
    assert callback_calls == [[]]
    # No update_many call should result in dummy.updated remaining empty.
    assert dummy.updated == []

def test_chunked_insert_context_manager_exception():
    """Test that ChunkedInsert flushes on context exit even when an exception is raised within the context."""
    dummy = DummyTable()
    try:
        with ChunkedInsert(dummy, chunksize=5) as inserter:
            inserter.insert({"p": 300})
            raise ValueError("ChunkedInsert exception")
    except ValueError:
        pass
    # Upon context exit, flush should have been called.
    # DummyTable.insert_many should have been invoked once with the pending row.
    assert len(dummy.inserted) == 1
    inserted = dummy.inserted[0]
    # Normalization should happen (the union of keys is {"p"})
    for item in inserted:
        assert "p" in item

def test_chunked_update_context_manager_exception():
    """Test that ChunkedUpdate flushes on context exit even when an exception is raised within the context."""
    dummy = DummyTable()
    try:
        with ChunkedUpdate(dummy, keys=["uid"], chunksize=5) as updater:
            updater.update({"uid": 20, "flag": True})
            raise ValueError("ChunkedUpdate exception")
    except ValueError:
        pass
    # Flush should have been called on exit, causing update_many to be invoked.
    assert len(dummy.updated) == 1
    group, keys_passed = dummy.updated[0]
    assert keys_passed == ["uid"]
    assert len(group) == 1