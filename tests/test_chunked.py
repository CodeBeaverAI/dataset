import pytest
import itertools

from dataset.chunked import ChunkedInsert, ChunkedUpdate, InvalidCallback

class DummyTable:
    """A dummy table class to record operations on insert and update operations."""
    def __init__(self):
        self.inserts = []
        self.updates = []

    def insert_many(self, items):
        self.inserts.extend(items)

    def update_many(self, items, keys):
        # Record the update call as a tuple: (items, keys)
        self.updates.append((items, keys))

# Test class for Chunked operations
class TestChunked:
    """Test suite for ChunkedInsert and ChunkedUpdate functionality."""

    def test_invalid_callback_insert(self):
        """Test that passing a non-callable callback to ChunkedInsert raises InvalidCallback."""
        dummy = DummyTable()
        with pytest.raises(InvalidCallback):
            ChunkedInsert(dummy, chunksize=1, callback="I am not callable")

    def test_invalid_callback_update(self):
        """Test that passing a non-callable callback to ChunkedUpdate raises InvalidCallback."""
        dummy = DummyTable()
        with pytest.raises(InvalidCallback):
            ChunkedUpdate(dummy, keys=['id'], chunksize=1, callback=123)

    def test_chunked_insert_auto_flush(self):
        """Test that ChunkedInsert flushes automatically when the chunksize is reached."""
        dummy = DummyTable()
        # Use a small chunksize to trigger flush automatically
        inserter = ChunkedInsert(dummy, chunksize=2)
        # Insert rows with different keys; fields should be merged.
        inserter.insert({'a': 1})
        inserter.insert({'b': 2})
        # At this point, flush should have been called automatically
        assert len(dummy.inserts) == 2
        # Check that for each inserted row, the missing field has a None value
        expected = [{'a': 1, 'b': None}, {'a': None, 'b': 2}]
        assert dummy.inserts == expected

    def test_chunked_insert_context_manager(self):
        """Test that ChunkedInsert flushes remaining data when exiting the context manager."""
        dummy = DummyTable()
        with ChunkedInsert(dummy, chunksize=3) as inserter:
            inserter.insert({'x': 10})
            inserter.insert({'y': 20})
            # Do not reach chunksize so flush happens on __exit__
        # Now flush should have been called on exit and both inserted.
        expected = [{'x': 10, 'y': None}, {'x': None, 'y': 20}]
        assert dummy.inserts == expected

    def test_chunked_update_grouping(self):
        """Test that ChunkedUpdate groups rows correctly and calls update_many accordingly."""
        dummy = DummyTable()
        updater = ChunkedUpdate(dummy, keys=['id'], chunksize=2)
        # Insert two items with same keys (so they belong to the same group)
        updater.update({'id': 1, 'value': 'a'})
        updater.update({'id': 2, 'value': 'b'})
        # Flush should be called manually
        updater.flush()
        # Since both items have the same set of keys, they will be grouped in one update_many call
        assert len(dummy.updates) == 1
        updated_items, update_keys = dummy.updates[0]
        # The update keys passed in should be ['id']
        assert update_keys == ['id']
        # Confirm that the updated group contains the two items
        assert {'id': 1, 'value': 'a'} in updated_items
        assert {'id': 2, 'value': 'b'} in updated_items

    def test_chunked_update_context_manager_with_callback(self):
        """Test that ChunkedUpdate flushes on context manager exit and that a callback is invoked."""
        dummy = DummyTable()
        callback_called = []

        def callback(queue):
            callback_called.append(len(queue))

        with ChunkedUpdate(dummy, keys=['id'], chunksize=3, callback=callback) as updater:
            updater.update({'id': 1, 'name': 'Alice'})
            updater.update({'id': 2, 'name': 'Bob'})
            # Do not add a third row so flush happens on __exit__
        # Ensure callback was called once during flush
        assert callback_called == [2]
        # Check that an update_many call was made (even if with a single group)
        assert len(dummy.updates) == 1

    def test_empty_flush(self):
        """Test that calling flush on an empty queue works without error for both insert and update."""
        dummy = DummyTable()
        inserter = ChunkedInsert(dummy, chunksize=2)
        # Call flush on an empty queue via context manager
        with inserter:
            pass
        # Also test update flush on empty queue
        updater = ChunkedUpdate(dummy, keys=['id'], chunksize=2)
        with updater:
            pass
        # No assertions needed; just ensuring no exceptions are raised.

    def test_chunked_insert_callback_invocation(self):
        """Test that ChunkedInsert invokes its callback and merges fields correctly during flush."""
        dummy = DummyTable()
        callback_called = []
        def callback(queue):
            callback_called.append(len(queue))
        # Use a chunksize of 3 to delay flush until 3 items have been added.
        inserter = ChunkedInsert(dummy, chunksize=3, callback=callback)
        inserter.insert({'a': 1})
        inserter.insert({'b': 2})
        # At this point, flush hasn't been triggered so callback should not have been called.
        assert callback_called == []
        # Inserting the third item triggers flush.
        inserter.insert({'c': 3})
        # After flush, callback should have been invoked with a queue of length 3.
        assert callback_called == [3]
        # All inserted rows should have merged fields from all items: keys 'a', 'b', and 'c'.
        expected = [
            {'a': 1, 'b': None, 'c': None},
            {'a': None, 'b': 2, 'c': None},
            {'a': None, 'b': None, 'c': 3}
        ]
        assert dummy.inserts == expected

    def test_chunked_update_multiple_groups(self):
        """Test that ChunkedUpdate groups updated items by their set of keys when they differ."""
        dummy = DummyTable()
        updater = ChunkedUpdate(dummy, keys=['id'], chunksize=5)
        # Two items with the same keys (group 1)
        updater.update({'id': 1, 'value': 'a'})
        updater.update({'id': 2, 'value': 'b'})
        # One item with a different keys set (group 2)
        updater.update({'id': 3})
        # One more item matching group 1 keys
        updater.update({'id': 4, 'value': 'd'})
        # Manually flush to trigger update_many calls
        updater.flush()
        # Ensure that exactly two update_many calls were made, one for each distinct keys set.
        assert len(dummy.updates) == 2
        # Verify that one group contains three items (group1 with keys {'id', 'value'})
        # and the other group contains one item (group2 with keys {'id'}).
        group_sizes = sorted(len(items) for items, _ in dummy.updates)
        assert group_sizes == [1, 3]
        # Also verify that all update_many calls used the update keys ['id'].
        for items, keys in dummy.updates:
            assert keys == ['id']
    def test_manual_flush_insert(self):
        """Test that manually calling flush in ChunkedInsert works as expected (without reaching chunksize)."""
        dummy = DummyTable()
        inserter = ChunkedInsert(dummy, chunksize=5)
        inserter.insert({'p': 100})
        inserter.insert({'q': 200})
        # Manually call flush even though the chunksize has not been reached
        inserter.flush()
        expected = [{'p': 100, 'q': None}, {'p': None, 'q': 200}]
        assert dummy.inserts == expected

    def test_manual_flush_update(self):
        """Test that manually calling flush in ChunkedUpdate triggers the callback and update_many correctly."""
        dummy = DummyTable()
        callback_called = []

        def update_callback(queue):
            callback_called.append(len(queue))

        updater = ChunkedUpdate(dummy, keys=['id'], chunksize=5, callback=update_callback)
        updater.update({'id': 10, 'r': 'x'})
        # Manually flush the pending update operation
        updater.flush()
        # Verify that the callback was invoked with a queue length of 1
        assert callback_called == [1]
        # Verify that update_many was called exactly once and with the correct parameters
        assert len(dummy.updates) == 1
        updated_items, update_keys = dummy.updates[0]
        assert update_keys == ['id']
        assert {'id': 10, 'r': 'x'} in updated_items