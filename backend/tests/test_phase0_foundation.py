"""Phase 0 foundation tests: schema, repository, and run lifecycle."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.repository import SchemaVersionError, SqliteRepository


def test_schema_version_stored(conn) -> None:
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    assert row["value"] == "1"
    conn.close()


def test_schema_version_mismatch_refuses(tmp_path, project_root) -> None:
    db = tmp_path / "mismatch.db"
    repo = SqliteRepository(
        db_path=db,
        schema_path=project_root / "backend" / "schema.sql",
        expected_version="1",
    )
    with repo._connect() as conn:
        conn.execute(
            "UPDATE schema_meta SET value = '999' WHERE key = 'schema_version'"
        )
        conn.commit()
    with pytest.raises(SchemaVersionError):
        SqliteRepository(
            db_path=db,
            schema_path=project_root / "backend" / "schema.sql",
            expected_version="1",
        )


def test_repository_satisfies_protocol(repo: SqliteRepository) -> None:
    from app.repository import Repository

    assert isinstance(repo, Repository)


def test_create_and_get_run(client: TestClient) -> None:
    resp = client.post(
        "/runs",
        json={"name": "Demo run", "reference_date": "2026-01-15"},
    )
    assert resp.status_code == 201
    run = resp.json()
    assert run["name"] == "Demo run"
    assert run["status"] == "created"
    assert run["is_synthetic"] is True

    got = client.get(f"/runs/{run['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == run["id"]


def test_get_missing_run_404(client: TestClient) -> None:
    assert client.get("/runs/does-not-exist").status_code == 404


def test_list_and_delete_run(client: TestClient) -> None:
    created = client.post(
        "/runs", json={"name": "R1", "reference_date": "2026-01-15"}
    ).json()
    assert any(r["id"] == created["id"] for r in client.get("/runs").json())

    assert client.delete(f"/runs/{created['id']}").status_code == 204
    assert client.get(f"/runs/{created['id']}").status_code == 404


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["notice"] == "Independent demo. Synthetic data."
    assert "llm_provider" in body
    assert "llm_hosted" in body
    assert "llm_warning" in body
