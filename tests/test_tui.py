"""Exercise both terminal workspaces without a network or physical terminal."""

import asyncio
import importlib
from unittest.mock import AsyncMock

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput


@pytest.fixture(params=["src.inference", "nexus_terminal"])
def tui(request, monkeypatch, tmp_path):
    base = request.param
    api = importlib.import_module(
        base + (".assistant_cli" if base == "src.inference" else ".cli")
    )
    module = importlib.import_module(base + ".tui")
    monkeypatch.setenv("VONK_CONFIG_DIR", str(tmp_path))
    for provider in api.PROVIDERS:
        monkeypatch.delenv(f"{provider.upper()}_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("VONK_BASE_URL", raising=False)
    return api, module


def _managed_selection(api):
    if api.__name__ == "src.inference.assistant_cli":
        return "openrouter", "openrouter/free"
    return "vonk", "opencode"


def _configure_key(provider, monkeypatch):
    if provider == "vonk":
        monkeypatch.setenv("VONK_API_KEY", "synthetic_key")
        monkeypatch.setenv("VONK_BASE_URL", "https://vonk.example")
    else:
        monkeypatch.setenv(f"{provider.upper()}_API_KEY", "synthetic_key")


def test_fullscreen_sends_with_selected_managed_or_hosted_model(tui, monkeypatch):
    api, module = tui

    async def exercise():
        provider, model = _managed_selection(api)
        _configure_key(provider, monkeypatch)
        started = asyncio.Event()

        async def byok(**kwargs):
            started.set()
            return {"response": "Hello\x1b]52;c;secret\x1b world"}

        async def managed(**kwargs):
            started.set()
            return "Hello\x1b]52;c;secret\x1b world"

        monkeypatch.setattr(api, "complete_byok", AsyncMock(side_effect=byok))
        if provider == "vonk":
            monkeypatch.setattr(api, "complete_vonk", AsyncMock(side_effect=managed))

        with create_pipe_input() as pipe:
            ui = module.Workspace(api, input=pipe, output=DummyOutput())
            ui.select(provider, model)
            ui.composer.text = "hello"
            ui.app.pre_run_callables.append(ui.send)

            async def driver():
                await asyncio.wait_for(started.wait(), 2)
                await ui.task
                pipe.send_text("\x1b")

            task = asyncio.create_task(driver())
            assert await asyncio.wait_for(ui.app.run_async(), 4) == 0
            await task
            assert ui.provider == provider
            assert "Hello world" in ui.transcript
            assert "secret" not in ui.transcript
            assert not ui.busy
            if provider == "vonk":
                assert api.complete_vonk.call_args.kwargs["model"] == "opencode"
            else:
                assert api.complete_byok.call_args.kwargs["provider"] == provider
            assert ui.messages[-1]["content"] == "Hello\x1b]52;c;secret\x1b world"

    asyncio.run(exercise())


def test_fullscreen_preserves_unconnected_prompt_and_cancels_request(tui, monkeypatch):
    api, module = tui

    async def exercise():
        provider, model = _managed_selection(api)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("VONK_API_KEY", raising=False)
        monkeypatch.delenv("VONK_BASE_URL", raising=False)

        with create_pipe_input() as pipe:
            ui = module.Workspace(api, input=pipe, output=DummyOutput())
            ui.composer.text = "keep my prompt"
            ui.send()
            assert ui.composer.text == "keep my prompt"
            assert "/connect" in ui.notice

            _configure_key(provider, monkeypatch)
            ui.select(provider, model)
            started = asyncio.Event()

            async def waiting(**kwargs):
                started.set()
                await asyncio.Event().wait()

            if provider == "vonk":
                monkeypatch.setattr(api, "complete_vonk", waiting)
            else:
                monkeypatch.setattr(api, "complete_byok", waiting)

            ui.composer.text = "hello"
            ui.app.pre_run_callables.append(ui.send)

            async def driver():
                await asyncio.wait_for(started.wait(), 2)
                pipe.send_text("\x1b")
                await ui.task
                pipe.send_text("\x1b")

            task = asyncio.create_task(driver())
            assert await asyncio.wait_for(ui.app.run_async(), 4) == 0
            await task
            assert "Request cancelled" in ui.transcript
            assert not ui.messages[1:]
            assert not ui.busy

    asyncio.run(exercise())
