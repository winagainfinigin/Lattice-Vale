from pathlib import Path
import ast
import re
import sys
import types
import json
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION.txt").read_text(encoding="ascii").strip()
CONFIGURE = (ROOT / "stack" / "configure-stack.sh").read_text(encoding="utf-8")

assert VERSION in {"14.4.7","14.4.8","14.4.81","14.4.82","14.4.83","14.4.84","14.4.85","14.5.0","14.5.1"}, VERSION
assert "integrations) printf '4' ;;" in CONFIGURE
assert "web['search_backend']='searxng'" in CONFIGURE
assert "web['extract_backend']='latticevale-local'" in CONFIGURE
assert "shared in {'','searxng'}" in CONFIGURE
assert "extract in {'','searxng','latticevale-local'}" in CONFIGURE
assert "latticevale-web-extract" in CONFIGURE
assert "register_web_search_provider" in CONFIGURE
assert "follow_redirects=False" in CONFIGURE
assert "create_ssrf_safe_client" in CONFIGURE
assert "normalize_url_for_request" in CONFIGURE
assert "sensitive_query_param_name" in CONFIGURE
assert "is_safe_url" in CONFIGURE
assert "_MAX_RESPONSE_BYTES = 2_000_000" in CONFIGURE
assert "_MAX_OUTPUT_CHARS = 250_000" in CONFIGURE
assert "_MAX_REDIRECTS = 5" in CONFIGURE
assert "browser['cloud_provider']='local'" in CONFIGURE
assert "web_extract_aux.setdefault('timeout',360)" in CONFIGURE

# Explicit non-SearXNG shared/extract providers remain authoritative: the local extractor
# is selected only when both the shared fallback and extract choice are empty/SearXNG.
config_block = CONFIGURE[CONFIGURE.index("# SearXNG is Hermes' keyless search backend"):CONFIGURE.index("if opts.get('qmd'):", CONFIGURE.index("# SearXNG is Hermes' keyless search backend"))]
assert "shared in {'','searxng'}" in config_block
assert "extract in {'','searxng','latticevale-local'}" in config_block
assert "else:\n        enabled=[x for x in enabled if x not in {'web/latticevale-web-extract','latticevale-web-extract'}]" in config_block

# Execute the exact managed-profile config heredoc against representative repair/install
# states. This guards preservation semantics rather than merely checking source strings.
stage_marker = "python3 - install-options.json data/hermes .installer-managed-profiles <<'PY'\n"
stage_start = CONFIGURE.index(stage_marker) + len(stage_marker)
stage_end = CONFIGURE.index("\nPY\n", stage_start)
stage_source = CONFIGURE[stage_start:stage_end]
plugin_marker = "python3 - data/hermes .installer-managed-profiles <<'PY_LATTICEVALE_WEB_EXTRACT_PLUGIN'\n"
plugin_start = CONFIGURE.index(plugin_marker) + len(plugin_marker)
plugin_end = CONFIGURE.index("\nPY_LATTICEVALE_WEB_EXTRACT_PLUGIN\n", plugin_start)
plugin_source = CONFIGURE[plugin_start:plugin_end]


def run_profile_scenario(initial_web, searxng=True, initial_browser=None, initial_auxiliary=None, initial_tool_gateway=None, env_lines=None):
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        hermes = base / "data" / "hermes"
        assistant = hermes / "profiles" / "assistant"
        assistant.mkdir(parents=True)
        initial = {
            "skills": {"write_approval": False},
            "plugins": {"enabled": [], "disabled": []},
        }
        if initial_web is not None:
            initial["web"] = initial_web
        if initial_browser is not None:
            initial["browser"] = initial_browser
        if initial_auxiliary is not None:
            initial["auxiliary"] = initial_auxiliary
        if initial_tool_gateway is not None:
            initial["tool_gateway"] = initial_tool_gateway
        for cfg_path in (hermes / "config.yaml", assistant / "config.yaml"):
            cfg_path.write_text(yaml.safe_dump(initial, sort_keys=False), encoding="utf-8")
        if env_lines:
            (hermes / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
            (assistant / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        opts = {
            "searxng": searxng,
            "kanban": False,
            "dashboard": False,
            "qmd": False,
            "honcho": False,
        }
        opts_path = base / "install-options.json"
        managed = base / ".installer-managed-profiles"
        opts_path.write_text(json.dumps(opts), encoding="utf-8")
        managed.write_text("assistant\n", encoding="utf-8")
        stage_py = base / "stage.py"
        stage_py.write_text(stage_source, encoding="utf-8")
        subprocess.run(
            [sys.executable, str(stage_py), str(opts_path), str(hermes), str(managed)],
            cwd=base,
            check=True,
            capture_output=True,
            text=True,
        )
        plugin_py = base / "plugin.py"
        plugin_py.write_text(plugin_source, encoding="utf-8")
        subprocess.run(
            [sys.executable, str(plugin_py), str(hermes), str(managed)],
            cwd=base,
            check=True,
            capture_output=True,
            text=True,
        )
        root_cfg = yaml.safe_load((hermes / "config.yaml").read_text(encoding="utf-8")) or {}
        assistant_cfg = yaml.safe_load((assistant / "config.yaml").read_text(encoding="utf-8")) or {}
        root_plugin = hermes / "plugins" / "web" / "latticevale-web-extract"
        assistant_plugin = assistant / "plugins" / "web" / "latticevale-web-extract"
        return root_cfg, assistant_cfg, root_plugin.exists(), assistant_plugin.exists()


root_cfg, assistant_cfg, root_plugin, assistant_plugin = run_profile_scenario({}, True)
for cfg in (root_cfg, assistant_cfg):
    assert cfg["web"]["search_backend"] == "searxng"
    assert cfg["web"]["extract_backend"] == "latticevale-local"
    assert cfg["browser"]["cloud_provider"] == "local"
    assert cfg["browser"]["engine"] == "auto"
    assert cfg["auxiliary"]["web_extract"]["timeout"] == 360
    assert "web/latticevale-web-extract" in cfg["plugins"]["enabled"]
assert root_plugin and assistant_plugin

# Repair must preserve explicit browser and auxiliary choices while still updating
# the installer-owned SearXNG/extraction integration.
root_cfg, assistant_cfg, _, _ = run_profile_scenario(
    {}, True,
    initial_browser={"cloud_provider": "browserbase", "engine": "auto"},
    initial_auxiliary={"web_extract": {"timeout": 75}},
)
for cfg in (root_cfg, assistant_cfg):
    assert cfg["browser"]["cloud_provider"] == "browserbase"
    assert cfg["auxiliary"]["web_extract"]["timeout"] == 75

# Other deliberate browser selections/routing remain authoritative on repair.
for browser_cfg in (
    {"cloud_provider": "browser-use", "engine": "auto"},
    {"cloud_provider": "camofox", "engine": "auto"},
    {"cloud_provider": "custom-browser", "engine": "auto", "executable_path": "/custom/chromium"},
    {"backend": "custom-backend", "engine": "auto"},
):
    root_cfg, assistant_cfg, _, _ = run_profile_scenario({}, True, initial_browser=browser_cfg)
    for cfg in (root_cfg, assistant_cfg):
        for key, value in browser_cfg.items():
            assert cfg["browser"][key] == value
        assert cfg["browser"].get("cloud_provider") != "local"

root_cfg, assistant_cfg, _, _ = run_profile_scenario(
    {}, True, initial_tool_gateway={"browser": "gateway"}
)
for cfg in (root_cfg, assistant_cfg):
    assert cfg["tool_gateway"]["browser"] == "gateway"
    assert cfg["browser"].get("cloud_provider") != "local"

# Legacy/direct cloud credentials are evidence of an intentional cloud choice even if
# cloud_provider has not yet been written into config.yaml.
for env_line in ("BROWSER_USE_API_KEY=test", "BROWSERBASE_API_KEY=test", "BROWSERBASE_PROJECT_ID=test", "CAMOFOX_URL=http://localhost:9377", "BROWSER_CDP_URL=http://127.0.0.1:9222"):
    root_cfg, assistant_cfg, _, _ = run_profile_scenario({}, True, env_lines=[env_line])
    for cfg in (root_cfg, assistant_cfg):
        assert cfg["browser"].get("cloud_provider") != "local"

# A second repair pass over LatticeVale defaults is idempotent.
root_cfg, assistant_cfg, _, _ = run_profile_scenario({}, True)
root2, assistant2, _, _ = run_profile_scenario(
    root_cfg.get("web", {}), True,
    initial_browser=root_cfg.get("browser"),
    initial_auxiliary=root_cfg.get("auxiliary"),
    initial_tool_gateway=root_cfg.get("tool_gateway"),
)
assert root2["web"] == root_cfg["web"]
assert root2["browser"] == root_cfg["browser"]
assert root2["auxiliary"] == root_cfg["auxiliary"]
assert assistant2["web"] == assistant_cfg["web"]
assert assistant2["browser"] == assistant_cfg["browser"]
assert assistant2["auxiliary"] == assistant_cfg["auxiliary"]

root_cfg, assistant_cfg, root_plugin, assistant_plugin = run_profile_scenario({"extract_backend": "tavily"}, True)
for cfg in (root_cfg, assistant_cfg):
    assert cfg["web"]["search_backend"] == "searxng"
    assert cfg["web"]["extract_backend"] == "tavily"
    assert "web/latticevale-web-extract" not in cfg["plugins"]["enabled"]
assert not root_plugin and not assistant_plugin

root_cfg, assistant_cfg, root_plugin, assistant_plugin = run_profile_scenario({"backend": "firecrawl", "extract_backend": "latticevale-local"}, True)
for cfg in (root_cfg, assistant_cfg):
    assert cfg["web"]["search_backend"] == "searxng"
    assert cfg["web"]["backend"] == "firecrawl"
    assert "extract_backend" not in cfg["web"]
assert not root_plugin and not assistant_plugin

root_cfg, assistant_cfg, root_plugin, assistant_plugin = run_profile_scenario(
    {"backend": "custom", "search_backend": "searxng", "extract_backend": "latticevale-local"},
    False,
)
for cfg in (root_cfg, assistant_cfg):
    assert cfg["web"] == {"backend": "custom"}
assert not root_plugin and not assistant_plugin


# Recover the provider source literal embedded in the generated-plugin heredoc.
match = re.search(r"provider_code=(?P<literal>[^\n]+)\nfor home in homes:", CONFIGURE)
assert match, "generated web-extract provider payload missing"
provider_source = ast.literal_eval(match.group("literal"))

# Stub Hermes' ABC and URL-safety helpers so the generated provider can be
# imported without a full Hermes checkout. The real runtime helpers are part of
# the pinned Hermes image and are separately asserted in source.
agent = types.ModuleType("agent")
web_search_provider = types.ModuleType("agent.web_search_provider")
class WebSearchProvider: pass
web_search_provider.WebSearchProvider = WebSearchProvider
sys.modules["agent"] = agent
sys.modules["agent.web_search_provider"] = web_search_provider

tools = types.ModuleType("tools")
url_safety = types.ModuleType("tools.url_safety")
def _fake_normalize(url):
    return str(url).strip()
def _fake_sensitive(url):
    return "token" if "token=" in str(url) else None
def _fake_safe(url):
    value = str(url).lower()
    return not any(x in value for x in ("127.0.0.1", "[::1]", "localhost", "169.254.169.254"))
class _DummyClient:
    def __enter__(self): return self
    def __exit__(self, *args): return False
def _fake_client(**kwargs):
    return _DummyClient()
url_safety.normalize_url_for_request = _fake_normalize
url_safety.sensitive_query_param_name = _fake_sensitive
url_safety.is_safe_url = _fake_safe
url_safety.create_ssrf_safe_client = _fake_client
sys.modules["tools"] = tools
sys.modules["tools.url_safety"] = url_safety

namespace = {}
exec(compile(provider_source, "latticevale-web-extract/provider.py", "exec"), namespace)
Provider = namespace["LatticeValeLocalExtractProvider"]
provider = Provider()
assert provider.name == "latticevale-local"
assert provider.is_available() is True
assert provider.supports_search() is False
assert provider.supports_extract() is True

validate = namespace["_normalized_safe_url"]
for blocked in (
    "http://127.0.0.1/",
    "http://[::1]/",
    "http://localhost/",
    "file:///etc/passwd",
    "http://user:pass@example.com/",
    "https://example.com/?token=secret",
):
    try:
        validate(blocked)
    except ValueError:
        pass
    else:
        raise AssertionError(f"private/invalid/sensitive URL was accepted: {blocked}")

extract_text = namespace["_extract_text"]
title, content = extract_text(
    "<html><head><title> Example </title><style>secret-style</style></head>"
    "<body><h1>Hello</h1><script>secret-script</script><p>Useful text.</p></body></html>",
    "text/html; charset=utf-8",
)
assert title == "Example"
assert "Hello" in content and "Useful text." in content
assert "secret-style" not in content and "secret-script" not in content
_, json_text = extract_text('{"ok":true,"items":[1,2]}', "application/json")
assert '"ok": true' in json_text

print("v14.4.7+ web extraction fixtures: PASS")
