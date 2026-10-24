import json

import pytest

from seopilot import metadata_adapter
from seopilot.metadata_adapter import MetadataAdapterError, generate_metadata_patch

PAGE = (
    "export const metadata = {title:'Old title', description:'Old description', "
    "robots: {index:true}, alternates:{canonical:'/about'}};\n"
    "export default function Page(){return <main>Unchanged page content</main>}"
)
EDIT = {"url": "https://example.com/about", "route": "/about", "title": "Reviewed title"}


async def test_real_helper_updates_only_static_metadata():
    result = await generate_metadata_patch({"app/about/page.tsx": PAGE}, [EDIT])
    change = result["changes"][0]
    assert change["old_title"] == "Old title"
    assert change["old_description"] == "Old description"
    assert change["description"] == "Old description"
    assert change["before"] == PAGE
    assert change["after"] == PAGE.replace("'Old title'", '"Reviewed title"')
    assert result["mappings"] == [{"url": EDIT["url"], "route": "/about", "path": "app/about/page.tsx"}]


async def test_inherited_metadata_is_read_only_and_page_override_is_added():
    layout = "export const metadata = {title:'Site title', description:'Inherited text'};"
    source = "export default function Page() {return <main>About the site</main>}"
    files = {"src/app/layout.tsx": layout, "src/app/(marketing)/about/page.tsx": source}
    result = await generate_metadata_patch(files, [EDIT])
    change = result["changes"][0]
    assert change["path"] == "src/app/(marketing)/about/page.tsx"
    assert change["old_title"] == "Site title"
    assert change["description"] == "Inherited text"
    assert change["after"].endswith(source)
    assert files["src/app/layout.tsx"] == layout


async def test_source_code_is_never_executed(tmp_path):
    marker = tmp_path / "must-not-exist"
    source = (
        f"require('node:fs').writeFileSync({json.dumps(str(marker))}, 'executed');\n"
        "throw new Error('SOURCE_CANARY_DO_NOT_SEND');\n"
        + PAGE
    )
    result = await generate_metadata_patch({"app/about/page.tsx": source}, [EDIT])
    assert "SOURCE_CANARY_DO_NOT_SEND" in result["changes"][0]["after"]
    assert not marker.exists()


@pytest.mark.parametrize("path,source", [
    ("app/about/page.tsx", '"use client"; ' + PAGE),
    ("app/about/page.tsx", "export async function generateMetadata(){return {title:'dynamic'}}"),
    ("app/about/page.tsx", "export const metadata = {...other, title:'Old'}"),
    ("app/about/page.tsx", "export const metadata = {title:{template:'%s | Site', default:'Site'}}"),
    ("app/about/page.tsx", "export const metadata = {['title']:'Old'}"),
    ("app/[slug]/page.tsx", PAGE),
    ("app/@modal/about/page.tsx", PAGE),
    ("app/(.)about/page.tsx", PAGE),
])
async def test_unsupported_source_refuses_without_source_in_error(path, source):
    with pytest.raises(MetadataAdapterError) as caught:
        await generate_metadata_patch({path: source + "\n// PRIVATE_SOURCE_CANARY"}, [EDIT])
    assert "PRIVATE_SOURCE_CANARY" not in str(caught.value)


@pytest.mark.parametrize("path", [
    "../app/about/page.tsx", "app/../about/page.tsx", "app\\about\\page.tsx",
    ".github/workflows/checks.yml", "app/about/layout.tsx/../../page.tsx", "app//about/page.tsx",
])
async def test_forbidden_paths_are_rejected_before_starting_a_subprocess(path, monkeypatch):
    def unexpected(*_args, **_kwargs):
        pytest.fail("No parser process should start for an unsafe path")

    monkeypatch.setattr(metadata_adapter.asyncio, "create_subprocess_exec", unexpected)
    with pytest.raises(MetadataAdapterError):
        await generate_metadata_patch({path: PAGE}, [EDIT])


async def test_bounded_pages_and_files():
    with pytest.raises(MetadataAdapterError, match="between one and three"):
        await generate_metadata_patch({"app/about/page.tsx": PAGE}, [EDIT] * 4)
    with pytest.raises(MetadataAdapterError, match="bounded limit"):
        await generate_metadata_patch({"app/about/page.tsx": "x" * (128 * 1024 + 1)}, [EDIT])


async def test_subprocess_has_fixed_helper_and_no_secret_or_node_loader_environment(monkeypatch):
    for name in ("OPENAI_API_KEY", "GITHUB_APP_PRIVATE_KEY_PATH", "GITHUB_TOKEN", "NODE_OPTIONS", "NODE_PATH"):
        monkeypatch.setenv(name, "SECRET_CANARY_DO_NOT_FORWARD")
    recorded = {}

    class Process:
        returncode = 0

        async def communicate(self, data):
            recorded["input"] = json.loads(data)
            return json.dumps({"ok": True, "changes": [{"path": "app/about/page.tsx", "before": PAGE,
                                "after": PAGE.replace("'Old title'", '"Reviewed title"')}],
                               "mappings": []}).encode(), None

    async def create_process(*args, **kwargs):
        recorded["args"] = args
        recorded["kwargs"] = kwargs
        return Process()

    monkeypatch.setattr(metadata_adapter.asyncio, "create_subprocess_exec", create_process)
    await generate_metadata_patch({"app/about/page.tsx": PAGE}, [EDIT])
    assert recorded["args"][1:] == (str(metadata_adapter.HELPER),)
    assert recorded["kwargs"]["cwd"] == str(metadata_adapter.HELPER.parent)
    assert "SECRET_CANARY" not in json.dumps(recorded)
    assert recorded["input"]["edits"] == [EDIT]
    assert recorded["kwargs"]["stderr"] == metadata_adapter.asyncio.subprocess.DEVNULL


async def test_missing_node_is_actionable(monkeypatch):
    monkeypatch.setattr(metadata_adapter.shutil, "which", lambda _: None)
    with pytest.raises(MetadataAdapterError, match="npm ci"):
        await generate_metadata_patch({"app/about/page.tsx": PAGE}, [EDIT])


async def test_timeout_kills_parser_and_returns_safe_error(monkeypatch):
    state = {"killed": False}

    class Process:
        async def communicate(self, data):
            return b"", None

        def kill(self):
            state["killed"] = True

        async def wait(self):
            return 1

    async def create_process(*_args, **_kwargs):
        return Process()

    async def expire(coroutine, **_kwargs):
        coroutine.close()
        raise TimeoutError

    monkeypatch.setattr(metadata_adapter.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(metadata_adapter.asyncio, "wait_for", expire)
    with pytest.raises(MetadataAdapterError, match="time limit"):
        await generate_metadata_patch({"app/about/page.tsx": PAGE}, [EDIT])
    assert state["killed"]
