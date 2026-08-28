"""Tests for project display metadata (name + description), the
/api/project endpoints, the cloud-sync launch warning, and skeleton
symlink self-heal."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from enough import project_meta, prompt, skeleton
from enough import server as server_mod
from enough.server import create_app


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    pd = tmp_path / "MyBook"
    skeleton.ensure_skeleton(pd)
    return pd


@pytest.fixture()
def client(project: Path):
    app = create_app(project, "http://127.0.0.1:1/v1", supervise=False)
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------
# project_meta module
# --------------------------------------------------------------------------

def test_defaults_to_folder_name(project: Path):
    m = project_meta.load(project)
    assert m["name"] == "MyBook"
    assert m["description"] == ""
    assert m["folder"] == "MyBook"
    assert m["path"] == str(project)


def test_save_round_trip_and_trim(project: Path):
    m = project_meta.save(project, "  A Memoir  ", "About my life.\r\n\n")
    assert m["name"] == "A Memoir"
    assert m["description"] == "About my life."  # CRLF normalized, trailing ws stripped
    assert (project / "rness" / "project.json").is_file()
    # reload sees the same
    assert project_meta.load(project)["name"] == "A Memoir"


def test_empty_name_resets_to_folder(project: Path):
    project_meta.save(project, "Custom", "x")
    assert project_meta.load(project)["name"] == "Custom"
    project_meta.save(project, "   ", "x")
    assert project_meta.load(project)["name"] == "MyBook"


def test_description_capped(project: Path):
    huge = "z" * (project_meta.MAX_DESCRIPTION_CHARS + 500)
    m = project_meta.save(project, "n", huge)
    assert len(m["description"]) <= project_meta.MAX_DESCRIPTION_CHARS


def test_corrupt_metadata_is_non_fatal(project: Path):
    (project / "rness" / "project.json").write_text("{not json", encoding="utf-8")
    m = project_meta.load(project)
    assert m["name"] == "MyBook"  # falls back instead of raising
    assert m["ui"] == {"ui_scale": 1.0, "text_scale": 1.0}


# --------------------------------------------------------------------------
# per-project display scales (uiscale round)
# --------------------------------------------------------------------------

def test_ui_defaults_when_unset(project: Path):
    assert project_meta.load(project)["ui"] == {"ui_scale": 1.0, "text_scale": 1.0}


def test_save_ui_round_trip_grid_and_clamp(project: Path):
    m = project_meta.save_ui(project, 1.2500001, 9.7)
    assert m["ui"]["ui_scale"] == 1.3          # rounded to the 0.1 grid
    assert m["ui"]["text_scale"] == 4.0        # hard-clamped
    m = project_meta.save_ui(project, 0.01, "nonsense")
    assert m["ui"]["ui_scale"] == 0.3          # clamped up to the floor
    assert m["ui"]["text_scale"] == 1.0        # unparseable resets to 1.0


def test_save_ui_preserves_name_and_vice_versa(project: Path):
    project_meta.save(project, "Winter Bees", "A beekeeping memoir.")
    project_meta.save_ui(project, 1.5, 0.9)
    m = project_meta.load(project)
    assert m["name"] == "Winter Bees"          # save_ui kept the editor's half
    assert m["ui"] == {"ui_scale": 1.5, "text_scale": 0.9}
    project_meta.save(project, "Winter Bees II", "Still bees.")
    m = project_meta.load(project)
    assert m["ui"] == {"ui_scale": 1.5, "text_scale": 0.9}  # save() kept ours


def test_corrupt_ui_block_is_non_fatal(project: Path):
    (project / "rness" / "project.json").write_text(
        '{"name": "x", "description": "", "ui": "garbage"}', encoding="utf-8")
    assert project_meta.load(project)["ui"] == {"ui_scale": 1.0, "text_scale": 1.0}


# --------------------------------------------------------------------------
# /api/project endpoints
# --------------------------------------------------------------------------

def test_api_get_default(client: TestClient):
    r = client.get("/api/project")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "MyBook"
    assert body["description"] == ""
    assert body["path"].endswith("MyBook")


def test_api_post_persists_without_renaming_folder(client: TestClient, project: Path):
    r = client.post("/api/project", json={"name": "Winter Bees",
                                          "description": "A beekeeping memoir."})
    assert r.status_code == 200
    assert r.json()["name"] == "Winter Bees"
    # GET reflects it
    assert client.get("/api/project").json()["description"] == "A beekeeping memoir."
    # the folder on disk is untouched
    assert project.name == "MyBook" and project.is_dir()


def test_api_post_bad_body(client: TestClient):
    r = client.post("/api/project", content=b"not json",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_project_name_templated_into_index(client: TestClient):
    client.post("/api/project", json={"name": "Tab Title Test", "description": ""})
    html = client.get("/").text
    assert "Tab Title Test" in html
    assert "<!-- PROJECT_NAME -->" not in html  # placeholder was replaced


def test_api_project_ui_persists_and_cleans(client: TestClient, project: Path):
    r = client.post("/api/project/ui", json={"ui_scale": 1.45, "text_scale": 0.9})
    assert r.status_code == 200
    assert r.json()["ui"] == {"ui_scale": 1.4, "text_scale": 0.9}
    assert project_meta.load(project)["ui"]["ui_scale"] == 1.4


def test_boot_ui_state_templated_into_index(client: TestClient):
    client.post("/api/project/ui", json={"ui_scale": 1.4, "text_scale": 0.9})
    html = client.get("/").text
    assert "/*UI_STATE_JSON*/null" not in html  # placeholder was replaced
    assert '"ui_scale": 1.4' in html or '"ui_scale":1.4' in html


# --------------------------------------------------------------------------
# Prompt injection
# --------------------------------------------------------------------------

def test_description_injected_into_system_prompt(project: Path):
    project_meta.save(project, "MyBook", "A memoir about beekeeping in winter.")
    sp = prompt.assemble_system_prompt(project)
    assert "Project Description" in sp
    assert "beekeeping in winter" in sp


def test_empty_description_omitted_from_prompt(project: Path):
    project_meta.save(project, "MyBook", "")
    sp = prompt.assemble_system_prompt(project)
    assert "Project Description" not in sp


# --------------------------------------------------------------------------
# Cloud-sync detection + launch warning
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path, label", [
    ("/Users/m/Library/CloudStorage/GoogleDrive-a@b.com/My Drive/p", "Google Drive"),
    ("/Users/m/Library/CloudStorage/Dropbox/p", "Dropbox"),
    ("/Users/m/Library/CloudStorage/OneDrive-Co/p", "OneDrive"),
    ("/Users/m/Library/Mobile Documents/com~apple~CloudDocs/p", "iCloud Drive"),
    ("/Users/m/Dropbox/p", "Dropbox"),
    ("/Users/m/code/local", None),
])
def test_cloud_sync_provider(path: str, label):
    assert skeleton.cloud_sync_provider(Path(path)) == label


def test_empty_hint_warns_in_cloud_root():
    html = server_mod._render_empty_hint(
        Path("/Users/m/Library/CloudStorage/GoogleDrive-a@b.com/My Drive/p")
    )
    assert "Google Drive" in html
    assert "empty-hint--notice" in html


def test_empty_hint_quiet_on_local_disk(project: Path):
    # A normal local project with a fresh skeleton => default hint, no notice.
    html = server_mod._render_empty_hint(project)
    assert "empty-hint--notice" not in html


# --------------------------------------------------------------------------
# Skeleton symlink self-heal
# --------------------------------------------------------------------------

def test_heal_repairs_cross_machine_links(project: Path):
    pol = project / "rness" / "policies" / "requests.md"
    assert pol.is_symlink() and pol.exists()

    # Simulate a link synced from another machine (user "0gs").
    pol.unlink(); pol.symlink_to("/Users/0gs/enough/defaults/policies/requests.md")
    assert skeleton._symlink_is_broken(pol)

    repaired = skeleton._heal_skeleton_symlinks(
        project, skeleton._install_defaults_root()
    )
    assert "rness/policies/requests.md" in repaired
    assert pol.exists() and "0gs" not in os.readlink(pol)


def test_heal_preserves_user_customized_file(project: Path):
    # 'customize for this project' replaces a symlink with a real file.
    ctx = project / "rness" / "policies" / "context-management.md"
    ctx.unlink(); ctx.write_text("MY CUSTOM POLICY", encoding="utf-8")
    skeleton._heal_skeleton_symlinks(
        project, skeleton._install_defaults_root()
    )
    assert not ctx.is_symlink()
    assert ctx.read_text(encoding="utf-8") == "MY CUSTOM POLICY"


def test_heal_is_idempotent_on_healthy_project(project: Path):
    repaired = skeleton._heal_skeleton_symlinks(
        project, skeleton._install_defaults_root()
    )
    assert repaired == []


def test_infoworld_link_pruned(project: Path):
    # A leftover per-project `infoworld` symlink (pre-dissolve) is removed;
    # a real user-made `infoworld/` dir is left alone.
    iw = project / "infoworld"
    if iw.is_symlink() or iw.exists():
        iw.unlink()
    iw.symlink_to("/Users/0gs/enough/infoworld")
    assert skeleton._prune_infoworld_link(project) is True
    assert not iw.exists() and not iw.is_symlink()
