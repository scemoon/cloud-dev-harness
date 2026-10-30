from __future__ import annotations

from typing import TYPE_CHECKING

from tui import platform_commands

if TYPE_CHECKING:
    from tui.widgets.conversation import Conversation


_KNOWN_PROVIDERS = {
    "anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    "openai": ["gpt-4o", "gpt-4-turbo", "gpt-4o-mini"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "minimax": ["MiniMax-M2.7", "MiniMax-M2.5"],
    "minimaxi": ["MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M3"],
    "glm": ["glm-4-plus", "glm-4-flash"],
    "ollama": [],
}


# ── small helpers ──────────────────────────────────────────────────────


def _load_cfg():
    from onecode.config import load_config
    return load_config()


def _save_cfg(cfg):
    from onecode.config import save_config
    save_config(cfg)


def _post_note(conversation, text):
    from tui.widgets.markdown_note import MarkdownNote
    return conversation.post(MarkdownNote(text))


async def _post(conversation, text):
    await _post_note(conversation, text)


# ── status: one-shot snapshot of every onecode: setting ───────────────


async def _status(conversation: "Conversation", parameters: str) -> None:
    """Render a single capability panel: provider, model, mode, skills, MCP."""
    cfg = _load_cfg()
    from onecode.skills.loader import SkillLoader
    from onecode.mcp.manager import MCPManager

    skills = SkillLoader().get_all()
    enabled_skills = sorted(n for n, s in skills.items() if s.enabled)
    disabled_skills = sorted(n for n, s in skills.items() if not s.enabled)

    servers = MCPManager().list()
    enabled_mcps = sorted(s["name"] for s in servers if s.get("enabled", True))
    disabled_mcps = sorted(s["name"] for s in servers if not s.get("enabled", True))

    lines = [
        "**onecode — current state**\n",
        f"- **provider**: `{cfg.default_provider}`",
        f"- **model**: `{cfg.default_model}`",
        f"- **mode**: `{cfg.default_mode}`  (build | plan | solo)",
        f"- **log level**: `{cfg.log_level}`",
        f"- **skills**: {len(enabled_skills)} enabled, {len(disabled_skills)} disabled",
    ]
    if enabled_skills:
        lines.append(f"  - enabled: {', '.join(f'`{n}`' for n in enabled_skills)}")
    if disabled_skills:
        lines.append(f"  - disabled: {', '.join(f'`{n}`' for n in disabled_skills)}")
    lines.append(f"- **mcp servers**: {len(enabled_mcps)} enabled, {len(disabled_mcps)} disabled")
    if enabled_mcps:
        lines.append(f"  - enabled: {', '.join(f'`{n}`' for n in enabled_mcps)}")
    if disabled_mcps:
        lines.append(f"  - disabled: {', '.join(f'`{n}`' for n in disabled_mcps)}")

    lines += [
        "\n**What can I do here?**",
        "- `/onecode:config` — open the TUI config editor",
        "- `/onecode:provider [set <name|n>]` — show / change LLM provider",
        "- `/onecode:model [set <name|n>]` — show / change LLM model",
        "- `/onecode:skill list|enable|disable|add|remove [name]`",
        "- `/onecode:mcp list|enable|disable|add|remove [name|url]`",
        "- `/onecode:compact` — immediately compact context",
        "- `/onecode:help` — show this overview",
    ]
    await _post(conversation, "\n".join(lines))


# ── provider ───────────────────────────────────────────────────────────


async def _provider(conversation: "Conversation", parameters: str) -> None:
    cfg = _load_cfg()
    args = parameters.strip().split()
    sub = args[0].lower() if args else ""

    if sub in ("", "show", "list"):
        registered = sorted(_KNOWN_PROVIDERS.keys())
        lines = [
            "**LLM Provider**\n",
            f"- current: `{cfg.default_provider}`",
            f"- available ({len(registered)}):",
        ]
        for i, name in enumerate(registered, 1):
            marker = " ← active" if name == cfg.default_provider else ""
            models = _KNOWN_PROVIDERS[name]
            model_hint = f"  models: {', '.join(models)}" if models else "  models: (any local)"
            lines.append(f"  `{i}) {name}`{marker}{model_hint}")
        lines += [
            "\n**How to switch**",
            "- `/onecode:provider set <name>` — e.g. `set minimaxi`",
            "- `/onecode:provider set <n>` — by number from the list above",
            "\n*Tip:* the provider change applies to new sessions; the current session keeps the active model until you start a new conversation.",
        ]
        await _post(conversation, "\n".join(lines))
        return

    if sub == "set":
        if len(args) < 2:
            conversation.notify("Usage: /onecode:provider set <name|n>", title="/onecode:provider", severity="error")
            return
        target = args[1].strip()
        registered = sorted(_KNOWN_PROVIDERS.keys())
        if target.isdigit():
            idx = int(target)
            if 1 <= idx <= len(registered):
                target = registered[idx - 1]
        if target not in registered:
            conversation.notify(
                f"Unknown provider '{target}'. Use /onecode:provider to list available ones.",
                title="/onecode:provider",
                severity="error",
            )
            return
        cfg.default_provider = target
        _save_cfg(cfg)
        try:
            conversation.app.settings.set("provider", target)
        except Exception:
            pass
        conversation.flash(f"onecode provider set to [b]{target}")
        await _status(conversation, "")
        return

    await _post(conversation, _HELP_PROVIDER)


_HELP_PROVIDER = (
    "**/onecode:provider** — show / switch the LLM provider\n\n"
    "**Sub-commands**\n"
    "- `(none)` or `show` — list registered providers with current marker\n"
    "- `set <name>` — switch provider (name or list-number)\n\n"
    "**Examples**\n"
    "- `/onecode:provider` — show the picker\n"
    "- `/onecode:provider set minimaxi` — switch by name\n"
    "- `/onecode:provider set 3` — switch by list number"
)


# ── model ──────────────────────────────────────────────────────────────


async def _model(conversation: "Conversation", parameters: str) -> None:
    cfg = _load_cfg()
    args = parameters.strip().split()
    sub = args[0].lower() if args else ""

    provider = cfg.default_provider
    known = _KNOWN_PROVIDERS.get(provider, [])

    if sub in ("", "show", "list"):
        lines = [
            "**LLM Model**\n",
            f"- provider: `{provider}`",
            f"- current:  `{cfg.default_model}`",
        ]
        if known:
            lines.append(f"- known models for `{provider}` ({len(known)}):")
            for i, name in enumerate(known, 1):
                marker = " ← active" if name == cfg.default_model else ""
                lines.append(f"  `{i}) {name}`{marker}")
        else:
            lines.append("- *(no preset list — type any model name)*")
        lines += [
            "\n**How to switch**",
            "- `/onecode:model set <name>` — e.g. `set MiniMax-M2.7`",
            "- `/onecode:model set <n>` — by number from the list above",
            "- `/onecode:model set <any-string>` — for providers without a preset",
            "\n*Tip:* changing the model mid-session does not retroactively update the active request; new turns will use the new model.",
        ]
        await _post(conversation, "\n".join(lines))
        return

    if sub == "set":
        if len(args) < 2:
            conversation.notify("Usage: /onecode:model set <name|n>", title="/onecode:model", severity="error")
            return
        target = args[1].strip()
        if target.isdigit() and known:
            idx = int(target)
            if 1 <= idx <= len(known):
                target = known[idx - 1]
        if not target:
            conversation.notify("Model name required", title="/onecode:model", severity="error")
            return
        cfg.default_model = target
        _save_cfg(cfg)
        try:
            conversation.app.settings.set("model", target)
        except Exception:
            pass
        conversation.flash(f"onecode model set to [b]{target}")
        await _status(conversation, "")
        return

    await _post(conversation, _HELP_MODEL)


_HELP_MODEL = (
    "**/onecode:model** — show / switch the LLM model\n\n"
    "**Sub-commands**\n"
    "- `(none)` or `show` — list known models for the current provider\n"
    "- `set <name>` — switch model (name or list-number)\n\n"
    "**Examples**\n"
    "- `/onecode:model` — show the picker for the current provider\n"
    "- `/onecode:model set MiniMax-M2.7` — switch by name\n"
    "- `/onecode:model set 1` — switch by list number"
)


# ── skill ──────────────────────────────────────────────────────────────


async def _skill(conversation: "Conversation", parameters: str) -> None:
    from onecode.skills.manager import SkillManager
    from onecode.skills.loader import SkillLoader
    from onecode.skills.create import create_skill_scaffold

    parts = parameters.strip().split()
    sub = parts[0].lower() if parts else ""
    rest = " ".join(parts[1:]) if len(parts) > 1 else ""

    if sub in ("", "list", "show"):
        skills = SkillLoader().get_all()
        if not skills:
            await _post(conversation, "**Skills**\n\n_No skills installed._\n\nUse `/onecode:skill add <name>` to scaffold a new one.")
            return
        lines = ["**Skills**\n"]
        names = sorted(skills.keys())
        for i, name in enumerate(names, 1):
            s = skills[name]
            marker = "✓" if s.enabled else "✗"
            desc = s.description or "(no description)"
            lines.append(f"- `{i}) {marker}` **{name}** — {desc}")
        lines += [
            "\n**How to manage**",
            "- `/onecode:skill enable <name|n>` — turn on",
            "- `/onecode:skill disable <name|n>` — turn off",
            "- `/onecode:skill add <name>` — scaffold a new skill",
            "- `/onecode:skill remove <name|n>` — delete a skill",
        ]
        await _post(conversation, "\n".join(lines))
        return

    if sub == "enable" or sub == "disable":
        if not rest.strip():
            conversation.notify(f"Usage: /onecode:skill {sub} <name|n>", title=f"/onecode:skill {sub}", severity="error")
            return
        target = _resolve_indexed_name(conversation, rest.strip(), SkillLoader().get_all(), sub)
        if target is None:
            return
        mgr = SkillManager()
        mgr.enable(target, sub == "enable")
        conversation.flash(f"skill [b]{target}[/b] {sub}d")
        await _skill(conversation, "list")
        return

    if sub == "add":
        name = rest.strip()
        if not name:
            conversation.notify("Usage: /onecode:skill add <name>", title="/onecode:skill add", severity="error")
            return
        mgr = SkillManager()
        if mgr.get(name):
            conversation.notify(f"Skill '{name}' already exists", title="/onecode:skill add", severity="error")
            return
        err = create_skill_scaffold(mgr.skills_dir, name, f"A skill for {name}")
        if err:
            conversation.notify(f"Error: {err}", title="/onecode:skill add", severity="error")
            return
        await _post(
            conversation,
            f"**Skill '{name}' created**\n\n"
            f"- location: `{mgr.skills_dir / name}`\n"
            f"- edit `SKILL.md` to add instructions\n"
            f"- then `/onecode:skill list` to confirm it shows up",
        )
        return

    if sub == "remove":
        if not rest.strip():
            conversation.notify("Usage: /onecode:skill remove <name|n>", title="/onecode:skill remove", severity="error")
            return
        target = _resolve_indexed_name(conversation, rest.strip(), SkillLoader().get_all(), sub)
        if target is None:
            return
        SkillManager().remove(target)
        conversation.flash(f"skill [b]{target}[/b] removed")
        await _skill(conversation, "list")
        return

    if sub == "create":
        name = rest.strip()
        if not name:
            conversation.notify("Usage: /onecode:skill create <name>", title="/onecode:skill create", severity="error")
            return
        from onecode.skills.model import Skill as SkillModel
        valid, err_msg = SkillModel.validate_name(name)
        if not valid:
            conversation.notify(f"Invalid name: {err_msg}", title="/onecode:skill create", severity="error")
            return
        mgr = SkillManager()
        if mgr.get(name):
            conversation.notify(f"Skill '{name}' already exists", title="/onecode:skill create", severity="error")
            return
        err = create_skill_scaffold(mgr.skills_dir, name, f"A skill for {name}")
        if err:
            conversation.notify(f"Error: {err}", title="/onecode:skill create", severity="error")
            return
        await _post(
            conversation,
            f"**Skill '{name}' created**\n\n"
            f"- location: `{mgr.skills_dir / name}`\n"
            f"- edit `SKILL.md` to add instructions\n"
            f"- then `/onecode:skill list` to confirm",
        )
        return

    if sub in ("search", "find"):
        keyword = rest.strip()
        if not keyword:
            conversation.notify("Usage: /onecode:skill search <keyword>", title="/onecode:skill search", severity="error")
            return
        results = SkillLoader().search(keyword)
        if not results:
            await _post(conversation, f"**Skill Search: `{keyword}`**\n\n_No matches found._")
            return
        lines = [f"**Skill Search: `{keyword}`**\n"]
        for i, s in enumerate(results, 1):
            marker = "✓" if s.enabled else "✗"
            desc = s.description or "(no description)"
            lines.append(f"- `{i}) {marker}` **{s.name}** — {desc}")
        lines.append(f"\n{len(results)} match(es)")
        await _post(conversation, "\n".join(lines))
        return

    await _post(conversation, _HELP_SKILL)


_HELP_SKILL = (
    "**/onecode:skill** — manage installed skills\n\n"
    "**Sub-commands**\n"
    "- `(none)` or `list` — show all skills with status\n"
    "- `create <name>` — scaffold a new skill\n"
    "- `search <keyword>` — search skills by keyword\n"
    "- `enable <name|n>` — turn a skill on\n"
    "- `disable <name|n>` — turn a skill off\n"
    "- `add <name>` — scaffold a new skill (alias for create)\n"
    "- `remove <name|n>` — delete a skill\n\n"
    "**Examples**\n"
    "- `/onecode:skill` — list\n"
    "- `/onecode:skill create my-skill` — scaffold a new skill\n"
    "- `/onecode:skill search browser` — find browser-related skills\n"
    "- `/onecode:skill enable 2` — enable the skill at index 2"
)


# ── mcp ────────────────────────────────────────────────────────────────


async def _mcp(conversation: "Conversation", parameters: str) -> None:
    from onecode.mcp.manager import MCPManager

    parts = parameters.strip().split()
    sub = parts[0].lower() if parts else ""
    rest = " ".join(parts[1:]) if len(parts) > 1 else ""

    if sub in ("", "list", "show"):
        servers = MCPManager().list()
        if not servers:
            await _post(
                conversation,
                "**MCP Servers**\n\n_None configured._\n\n"
                "Use `/onecode:mcp add <name> <url>` for an SSE server, "
                "`/onecode:mcp add <name> --type stdio --command <cmd>` for stdio, or "
                "`/onecode:mcp add <name> --type http --url <url>` for HTTP.",
            )
            return
        lines = ["**MCP Servers**\n"]
        for i, s in enumerate(servers, 1):
            name = s.get("name", "?")
            transport = s.get("transport", "sse")
            enabled = s.get("enabled", True)
            marker = "✓" if enabled else "✗"
            if transport == "sse":
                lines.append(f"- `{i}) {marker}` **{name}** (SSE) — `{s.get('url', '')}`")
            elif transport == "http":
                url = s.get("url", "")
                headers = s.get("headers", {})
                line = f"- `{i}) {marker}` **{name}** (HTTP) — `{url}`"
                if headers:
                    line += f" headers: {', '.join(headers.keys())}"
                lines.append(line)
            else:
                cmd = s.get("command", "")
                cmd_args = " ".join(s.get("args") or [])
                env = s.get("env", {})
                line = f"- `{i}) {marker}` **{name}** (stdio) — `{cmd} {cmd_args}`".rstrip()
                if env:
                    line += f" env: {', '.join(env.keys())}"
                lines.append(line)
        lines += [
            "\n**How to manage**",
            "- `/onecode:mcp enable <name|n>`",
            "- `/onecode:mcp disable <name|n>`",
            "- `/onecode:mcp remove <name|n>`",
        ]
        await _post(conversation, "\n".join(lines))
        return

    if sub == "enable" or sub == "disable":
        if not rest.strip():
            conversation.notify(f"Usage: /onecode:mcp {sub} <name|n>", title=f"/onecode:mcp {sub}", severity="error")
            return
        mgr = MCPManager()
        target = _resolve_indexed_name(conversation, rest.strip(), {s["name"]: s for s in mgr.list()}, sub)
        if target is None:
            return
        err = mgr.enable(target, sub == "enable")
        if err:
            conversation.notify(f"Error: {err}", title=f"/onecode:mcp {sub}", severity="error")
            return
        conversation.flash(f"mcp server [b]{target}[/b] {sub}d")
        await _mcp(conversation, "list")
        return

    if sub == "add":
        parts_shlex = rest.split()
        if len(parts_shlex) < 2:
            await _post(
                conversation,
                "**/onecode:mcp add** — register a new MCP server\n\n"
                "- **SSE** (default): `/onecode:mcp add <name> <url>`\n"
                "- **stdio**: `/onecode:mcp add <name> --type stdio --command <cmd> --args a,b --env K=V`\n"
                "- **HTTP**: `/onecode:mcp add <name> --type http --url <url> --headers K=V`",
            )
            return
        name = parts_shlex[0]
        pos_url = parts_shlex[1] if not parts_shlex[1].startswith("--") else ""

        transport = "sse"
        command = ""
        cmd_args = []
        env_dict = {}
        headers_dict = {}
        explicit_url = ""

        i = 1
        while i < len(parts_shlex):
            tok = parts_shlex[i]
            if tok == "--type" and i + 1 < len(parts_shlex):
                transport = parts_shlex[i + 1]
                i += 2
            elif tok == "--command" and i + 1 < len(parts_shlex):
                command = parts_shlex[i + 1]
                i += 2
            elif tok == "--args" and i + 1 < len(parts_shlex):
                cmd_args = [a.strip() for a in parts_shlex[i + 1].split(",")]
                i += 2
            elif tok == "--env" and i + 1 < len(parts_shlex):
                for pair in parts_shlex[i + 1].split(","):
                    if "=" in pair:
                        k, _, v = pair.partition("=")
                        env_dict[k.strip()] = v.strip()
                i += 2
            elif tok == "--url" and i + 1 < len(parts_shlex):
                explicit_url = parts_shlex[i + 1]
                i += 2
            elif tok == "--headers" and i + 1 < len(parts_shlex):
                for pair in parts_shlex[i + 1].split(","):
                    if "=" in pair:
                        k, _, v = pair.partition("=")
                        headers_dict[k.strip()] = v.strip()
                i += 2
            else:
                i += 1

        mgr = MCPManager()
        if mgr.get(name):
            conversation.notify(f"MCP server '{name}' already exists", title="/onecode:mcp add", severity="error")
            return

        final_url = explicit_url or pos_url

        if transport == "http":
            if not final_url:
                conversation.notify("Error: --url required for http transport", title="/onecode:mcp add", severity="error")
                return
            mgr.add_http(name, final_url, headers=headers_dict)
            await _post(conversation, f"**MCP Server '{name}' added**\n\n- transport: HTTP\n- URL: `{final_url}`\n\nUse `/onecode:mcp list` to confirm.")
        elif transport == "stdio":
            if not command:
                conversation.notify("Error: --command required for stdio transport", title="/onecode:mcp add", severity="error")
                return
            mgr.add_stdio(name, command, args=cmd_args, env=env_dict)
            await _post(conversation, f"**MCP Server '{name}' added**\n\n- transport: stdio\n- command: `{command}`\n\nUse `/onecode:mcp list` to confirm.")
        else:
            if not final_url:
                conversation.notify("Error: URL is required for SSE transport", title="/onecode:mcp add", severity="error")
                return
            mgr.add(name, final_url, transport="sse")
            await _post(conversation, f"**MCP Server '{name}' added**\n\n- transport: SSE\n- URL: `{final_url}`\n\nUse `/onecode:mcp list` to confirm.")
        return

    if sub == "remove":
        if not rest.strip():
            conversation.notify("Usage: /onecode:mcp remove <name|n>", title="/onecode:mcp remove", severity="error")
            return
        mgr = MCPManager()
        target = _resolve_indexed_name(conversation, rest.strip(), {s["name"]: s for s in mgr.list()}, sub)
        if target is None:
            return
        mgr.remove(target)
        conversation.flash(f"mcp server [b]{target}[/b] removed")
        await _mcp(conversation, "list")
        return

    await _post(conversation, _HELP_MCP)


_HELP_MCP = (
    "**/onecode:mcp** — manage MCP (Model Context Protocol) servers\n\n"
    "**Sub-commands**\n"
    "- `(none)` or `list` — show configured servers\n"
    "- `add <name> <url>` — add an SSE server (default)\n"
    "- `add <name> --type stdio --command <cmd> [--args a,b] [--env K=V]` — stdio\n"
    "- `add <name> --type http --url <url> [--headers K=V]` — HTTP\n"
    "- `enable <name|n>` / `disable <name|n>`\n"
    "- `remove <name|n>`\n\n"
    "**Examples**\n"
    "- `/onecode:mcp` — list servers\n"
    "- `/onecode:mcp add my-server https://example.com/mcp` — SSE\n"
    "- `/onecode:mcp add cloudbase --type stdio --command npx --args @cloudbase/cloudbase-mcp@latest --env TENCENTCLOUD_SECRETID=xxx,TENCENTCLOUD_SECRETKEY=xxx` — stdio\n"
    "- `/onecode:mcp add cloudbase --type http --url https://tcb-api.cloud.tencent.com/mcp/v1?env_id=xxx --headers X-TencentCloud-SecretId=xxx` — HTTP\n"
    "- `/onecode:mcp disable 1` — disable the first server in the list"
)


# ── helpers ────────────────────────────────────────────────────────────


def _resolve_indexed_name(conversation, raw, items, sub_label):
    """Accept either a literal name or a 1-based index from the most recent list.

    ``items`` is either a ``dict[name, ...]`` (skills) or already indexed
    by name (MCP). Returns the resolved name or ``None`` after notifying
    the user on error.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    keys = list(items.keys())
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(keys):
            return keys[idx - 1]
        conversation.notify(
            f"Index {idx} out of range (1..{len(keys)}). Run `/onecode:{sub_label}` first to see numbers.",
            title=f"/onecode:{sub_label}",
            severity="error",
        )
        return None
    if raw in items:
        return raw
    conversation.notify(
        f"Unknown name '{raw}'. Run `/onecode:{sub_label}` first to see available names.",
        title=f"/onecode:{sub_label}",
        severity="error",
    )
    return None


# ── compact ─────────────────────────────────────────────────────────────


async def _compact(conversation: "Conversation", parameters: str) -> None:
    """Immediately compact the agent context to reduce token usage."""
    agent = conversation.agent
    if agent is None:
        conversation.notify("No active agent session", title="/onecode:compact", severity="error")
        return
    if not hasattr(agent, "compact"):
        conversation.notify("Agent does not support context compaction", title="/onecode:compact", severity="error")
        return
    try:
        result = await agent.compact()
        if result is None:
            conversation.notify("Compaction not available", title="/onecode:compact", severity="error")
            return
        await _post(
            conversation,
            f"**Context Compacted**\n"
            f"- level: `{result.get('level', 'unknown')}`\n"
            f"- tokens: `{result.get('tokens_before', 0)}` → `{result.get('tokens_after', 0)}`",
        )
    except Exception as e:
        conversation.notify(f"Compaction failed: {e}", title="/onecode:compact", severity="error")


# ── config ─────────────────────────────────────────────────────────────


def _mask_api_key(v: str | None) -> str:
    if not v:
        return "(not set)"
    if v.startswith("${") and v.endswith("}"):
        return f"{v} (env ref)"
    if len(v) <= 4:
        return "***"
    return v[:4] + "***" + v[-4:]


async def _config(conversation: "Conversation", parameters: str) -> None:
    cfg = _load_cfg()
    parts = parameters.strip().split()
    sub = parts[0].lower() if parts else ""
    rest = " ".join(parts[1:]) if len(parts) > 1 else ""

    if sub in ("", "tui", "screen", "edit"):
        conversation.app.push_screen("config")
        return

    if sub == "list":
        import yaml
        from onecode.config import _dataclass_to_dict
        raw = _dataclass_to_dict(cfg)
        for pid, pcfg in raw.get("providers", {}).items():
            if pcfg.get("api_key"):
                pcfg["api_key"] = _mask_api_key(pcfg["api_key"])
        await _post(conversation, "**onecode config**\n\n```yaml\n" + yaml.dump(raw, default_flow_style=False) + "```")
        return

    if sub == "mode":
        mode_parts = rest.strip().split()
        mode_sub = mode_parts[0].lower() if mode_parts else ""
        if mode_sub == "get" or mode_sub == "":
            await _post(conversation, f"**mode** = `{cfg.default_mode}`  (build | plan | solo)")
            return
        if mode_sub == "set":
            if len(mode_parts) < 2:
                conversation.notify("Usage: /onecode:config mode set <build|plan|solo>", title="/onecode:config mode set", severity="error")
                return
            value = mode_parts[1]
            if value not in ("build", "plan", "solo"):
                conversation.notify("Mode must be one of: build, plan, solo", title="/onecode:config mode set", severity="error")
                return
            cfg.default_mode = value
            _save_cfg(cfg)
            conversation.flash(f"onecode mode set to [b]{value}")
            return
        await _post(conversation, _HELP_CONFIG)
        return

    if sub == "model":
        model_parts = rest.strip().split()
        model_sub = model_parts[0].lower() if model_parts else ""
        if model_sub == "get" or model_sub == "":
            await _post(conversation, f"**model** = `{cfg.default_model}`")
            return
        if model_sub == "set":
            if len(model_parts) < 2:
                conversation.notify("Usage: /onecode:config model set <model-name>", title="/onecode:config model set", severity="error")
                return
            value = model_parts[1]
            cfg.default_model = value
            _save_cfg(cfg)
            conversation.flash(f"onecode model set to [b]{value}")
            return
        await _post(conversation, _HELP_CONFIG)
        return

    if sub == "provider":
        prov_parts = rest.strip().split()
        prov_sub = prov_parts[0].lower() if prov_parts else ""
        prov_rest = " ".join(prov_parts[1:]) if len(prov_parts) > 1 else ""

        if prov_sub in ("", "get"):
            await _post(conversation, f"**provider** = `{cfg.default_provider}`")
            return

        if prov_sub == "set":
            if not prov_rest:
                conversation.notify("Usage: /onecode:config provider set <name>", title="/onecode:config provider set", severity="error")
                return
            cfg.default_provider = prov_rest
            _save_cfg(cfg)
            conversation.flash(f"onecode provider set to [b]{prov_rest}")
            return

        if prov_sub == "list":
            from onecode.models.provider import ProviderRegistry
            from onecode.models.registry import ModelRegistry
            try:
                from onecode.models import providers as _  # noqa: F401
            except ImportError:
                pass
            try:
                ModelRegistry.initialize()
            except Exception:
                pass
            registered = sorted(ProviderRegistry.list())
            current = cfg.default_provider
            lines = [f"**Available providers** ({len(registered)}):\n"]
            for i, name in enumerate(registered, 1):
                marker = " ← active" if name == current else ""
                try:
                    models = ModelRegistry.list_by_provider(name)
                except Exception:
                    models = []
                if models:
                    model_names = sorted({m.id for m in models})
                    shown = ", ".join(model_names[:5])
                    if len(model_names) > 5:
                        shown += f", … (+{len(model_names) - 5})"
                    model_hint = f"  models: {shown}"
                else:
                    model_hint = "  models: (any local)"
                lines.append(f"  `{i}) {name}`{marker}{model_hint}")
            lines.append("\n*Switch with: `/onecode:config provider set <name>`*")
            await _post(conversation, "\n".join(lines))
            return

        if prov_sub in ("api-key", "apikey", "key"):
            key_parts = prov_rest.strip().split()
            key_sub = key_parts[0].lower() if key_parts else ""
            key_rest = " ".join(key_parts[1:]) if len(key_parts) > 1 else ""

            if key_sub == "get":
                if not key_rest:
                    conversation.notify("Usage: /onecode:config provider api-key get <provider>", title="/onecode:config provider api-key get", severity="error")
                    return
                pcfg = cfg.providers.get(key_rest)
                if pcfg:
                    await _post(conversation, f"**{key_rest} api-key** = `{_mask_api_key(pcfg.api_key)}`")
                else:
                    await _post(conversation, f"**{key_rest} api-key** = `(not configured)`")
                return

            if key_sub == "set":
                if len(key_parts) < 3:
                    conversation.notify("Usage: /onecode:config provider api-key set <provider> <key>", title="/onecode:config provider api-key set", severity="error")
                    return
                provider_id = key_parts[1]
                key_value = key_parts[2]
                if provider_id not in cfg.providers:
                    from onecode.config import ProviderConfig
                    cfg.providers[provider_id] = ProviderConfig()
                cfg.providers[provider_id].api_key = key_value
                _save_cfg(cfg)
                conversation.flash(f"onecode {provider_id} api-key set")
                return

            await _post(conversation, _HELP_CONFIG)
            return

        if prov_sub == "endpoint":
            ep_parts = prov_rest.strip().split()
            ep_sub = ep_parts[0].lower() if ep_parts else ""
            ep_rest = " ".join(ep_parts[1:]) if len(ep_parts) > 1 else ""

            if ep_sub == "get":
                if not ep_rest:
                    conversation.notify("Usage: /onecode:config provider endpoint get <provider>", title="/onecode:config provider endpoint get", severity="error")
                    return
                pcfg = cfg.providers.get(ep_rest)
                if pcfg:
                    ep = pcfg.endpoint or "(default)"
                    await _post(conversation, f"**{ep_rest} endpoint** = `{ep}`")
                else:
                    await _post(conversation, f"**{ep_rest} endpoint** = `(not configured)`")
                return

            if ep_sub == "set":
                if len(ep_parts) < 3:
                    conversation.notify("Usage: /onecode:config provider endpoint set <provider> <url>", title="/onecode:config provider endpoint set", severity="error")
                    return
                provider_id = ep_parts[1]
                ep_value = ep_parts[2]
                if provider_id not in cfg.providers:
                    from onecode.config import ProviderConfig
                    cfg.providers[provider_id] = ProviderConfig()
                cfg.providers[provider_id].endpoint = ep_value
                _save_cfg(cfg)
                conversation.flash(f"onecode {provider_id} endpoint set")
                return

            await _post(conversation, _HELP_CONFIG)
            return

        await _post(conversation, _HELP_CONFIG)
        return

    if sub == "log-level":
        ll_parts = rest.strip().split()
        ll_sub = ll_parts[0].lower() if ll_parts else ""
        if ll_sub == "get" or ll_sub == "":
            await _post(conversation, f"**log-level** = `{cfg.log_level}`  (debug | info | warn | error)")
            return
        if ll_sub == "set":
            if len(ll_parts) < 2:
                conversation.notify("Usage: /onecode:config log-level set <debug|info|warn|error>", title="/onecode:config log-level set", severity="error")
                return
            value = ll_parts[1]
            if value not in ("debug", "info", "warn", "error"):
                conversation.notify("Log level must be one of: debug, info, warn, error", title="/onecode:config log-level set", severity="error")
                return
            cfg.log_level = value
            _save_cfg(cfg)
            conversation.flash(f"onecode log-level set to [b]{value}")
            return
        await _post(conversation, _HELP_CONFIG)
        return

    await _post(conversation, _HELP_CONFIG)


_HELP_CONFIG = (
    "**/onecode:config** — manage onecode configuration\n\n"
    "**Sub-commands**\n"
    "- `(none)` or `tui` — open the TUI config editor\n"
    "- `list` — show full YAML configuration (api-key masked)\n"
    "- `mode get|set <build|plan|solo>`\n"
    "- `model get|set <model-name>`\n"
    "- `provider get|set <name>` — get/set default provider\n"
    "- `provider list` — list all available providers\n"
    "- `provider api-key get|set <provider> <key>` — manage provider api-key\n"
    "- `provider endpoint get|set <provider> <url>` — manage provider endpoint\n"
    "- `log-level get|set <debug|info|warn|error>`\n\n"
    "**Examples**\n"
    "- `/onecode:config` — open config editor\n"
    "- `/onecode:config list` — show full config\n"
    "- `/onecode:config mode set solo`\n"
    "- `/onecode:config provider api-key set openai sk-xxx`\n"
    "- `/onecode:config provider endpoint set openai https://api.openai.com/v1`"
)


# ── registration ──────────────────────────────────────────────────────


def register_commands() -> None:
    """Register the slash commands exposed to the TUI prompt.

    The help text intentionally covers both **what** the command does and
    **how** to invoke it (sub-command + index syntax), so the
    autocomplete panel is self-documenting.
    """
    platform_commands.register(
        "help",
        "Show onecode: command overview and current state",
        _status,
        "(no args)",
    )
    platform_commands.register(
        "status",
        "Show current provider, model, mode, skills, and MCP servers",
        _status,
        "(no args)",
    )
    platform_commands.register(
        "provider",
        "Show / switch the LLM provider (current + numbered list)",
        _provider,
        "[set <name|n>]",
    )
    platform_commands.register(
        "model",
        "Show / switch the LLM model for the current provider",
        _model,
        "[set <name|n>]",
    )
    platform_commands.register(
        "skill",
        "Manage skills: list, create, search, enable, disable, add, remove (accepts name or list number)",
        _skill,
        "list|create|search|enable|disable|add|remove [name|n]",
    )
    platform_commands.register(
        "mcp",
        "Manage MCP servers: list, add, enable, disable, remove (accepts name or list number)",
        _mcp,
        "list|add|enable|disable|remove [name|n]",
    )
    platform_commands.register(
        "compact",
        "Immediately compact context to reduce token usage",
        _compact,
        "(no args)",
    )
    platform_commands.register(
        "config",
        "Open config editor TUI, or manage mode/model/provider/api-key/endpoint/log-level",
        _config,
        "mode|model|provider|log-level [get|set <v>]",
    )