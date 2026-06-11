import pytest
from httpx import ASGITransport, AsyncClient


def _route_paths(app) -> set[str]:
    return {getattr(route, 'path', '') for route in app.routes}


@pytest.mark.asyncio
async def test_llm_debug_routes_disabled_by_default(app_loader):
    main = app_loader()

    paths = _route_paths(main.app)

    assert '/debug/llm' not in paths
    assert '/debug/llm/model' not in paths
    assert '/debug/llm/unload' not in paths
    assert '/debug/llm/stop-loading' not in paths

    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url='http://testserver') as client:
        response = await client.get('/debug/llm')

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_llm_debug_routes_enabled_by_flag(app_loader):
    main = app_loader(enable_llm_debug=True)

    paths = _route_paths(main.app)

    assert '/debug/llm' in paths
    assert '/debug/llm/model' in paths
    assert '/debug/llm/unload' in paths
    assert '/debug/llm/stop-loading' in paths
