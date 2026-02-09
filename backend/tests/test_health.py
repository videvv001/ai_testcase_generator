import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def _get_health():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/health")


def test_health_ok():
    response = asyncio.run(_get_health())
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "ok"
    assert "service" in body
    assert "environment" in body
