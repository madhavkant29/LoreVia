import pytest

from app.utils.pagination_utils import build_paginated_response, validate_pagination


class TestBuildPaginatedResponse:
    def test_no_items(self):
        result = build_paginated_response([], total=0, limit=50, offset=0)
        assert result.items == []
        assert result.total == 0
        assert result.limit == 50
        assert result.offset == 0
        assert result.has_more is False

    def test_fewer_items_than_limit(self):
        result = build_paginated_response(["a", "b", "c"], total=3, limit=50, offset=0)
        assert len(result.items) == 3
        assert result.has_more is False

    def test_exactly_limit_items(self):
        result = build_paginated_response(list(range(50)), total=50, limit=50, offset=0)
        assert len(result.items) == 50
        assert result.has_more is False

    def test_more_items_than_limit(self):
        result = build_paginated_response(list(range(50)), total=100, limit=50, offset=0)
        assert len(result.items) == 50
        assert result.has_more is True

    def test_second_page(self):
        items = list(range(100))
        result = build_paginated_response(items[50:100], total=100, limit=50, offset=50)
        assert len(result.items) == 50
        assert result.items[0] == 50
        assert result.items[-1] == 99
        assert result.has_more is False

    def test_has_more_with_partial_last_page(self):
        result = build_paginated_response(list(range(30)), total=80, limit=50, offset=50)
        assert len(result.items) == 30
        assert result.has_more is False

    def test_offset_zero(self):
        result = build_paginated_response(list(range(50)), total=200, limit=50, offset=0)
        assert result.offset == 0
        assert result.has_more is True


class TestValidatePagination:
    async def test_valid(self):
        await validate_pagination(50, 0)

    async def test_limit_too_small(self):
        with pytest.raises(Exception):
            await validate_pagination(0, 0)

    async def test_limit_too_large(self):
        with pytest.raises(Exception):
            await validate_pagination(101, 0)

    async def test_offset_negative(self):
        with pytest.raises(Exception):
            await validate_pagination(50, -1)
