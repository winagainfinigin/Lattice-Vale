from pathlib import Path
import re, yaml
root=Path(__file__).resolve().parents[1]
assert (root/'VERSION.txt').read_text().strip() in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}
ps=(root/'Install-LatticeVale.ps1').read_text(encoding='utf-8')
conf=(root/'stack/configure-stack.sh').read_text(encoding='utf-8')
compose_text=(root/'stack/compose.yaml').read_text(encoding='utf-8')
qmd=(root/'stack/qmd-index-cycle.sh').read_text(encoding='utf-8')
compose=yaml.safe_load(compose_text)

# Matrix reaction approvals: explicit and sender-scoped, both configured and verified.
assert 'set_env data/hermes/.env MATRIX_REACTIONS true' in conf
assert 'set_env data/hermes/.env MATRIX_APPROVAL_REQUIRE_SENDER true' in conf
assert "'MATRIX_REACTIONS','MATRIX_APPROVAL_REQUIRE_SENDER'" in conf
assert "values.get('MATRIX_REACTIONS')!='true'" in conf

# Automatic Kanban + conservative cloud-provider pressure limits.
for needle in (
    "kanban['dispatch_in_gateway']=True",
    "kanban['dispatch_interval_seconds']=30",
    "kanban['auto_decompose']=True",
    "kanban['auto_decompose_per_tick']=1",
    "kanban['auto_subscribe_on_create']=True",
    "kanban['max_in_progress']=int(opts.get('kanbanMaxInProgress') or 2)",
    "kanban['max_in_progress_per_profile']=int(opts.get('kanbanMaxInProgressPerProfile') or 1)",
    'HERMES_AUTO_KANBAN_POLICY_START',
    'create exactly one root Kanban card in triage',
):
    assert needle in conf, needle
assert 'kanbanMaxInProgress = 2' in ps
assert 'kanbanMaxInProgressPerProfile = 1' in ps

# Windows-native Obsidian vault; native Windows app is never directed at WSL UNC.
assert 'function Get-RegisteredObsidianVaultPaths' in ps
assert 'function Convert-WindowsLocalPathToWslPath' in ps
assert 'obsidianVaultWindowsPath' in ps and 'obsidianVaultWslPath' in ps
assert r'Do not use \\wsl.localhost or another UNC/network path.' in ps
assert '${OBSIDIAN_VAULT_HOST_PATH:-./vault}:/vault:rw' in compose_text
assert compose_text.count('${OBSIDIAN_VAULT_HOST_PATH:-./vault}:/vault:ro') >= 2
assert 'cp -a -n vault/. "$obsidian_vault_host_path"/' in conf
assert 'function Repair-LegacyObsidianStackVaultMount' in ps
assert "Write-Step 'Reconciling legacy Obsidian vault mounts'" in ps
assert '.latticevale-v14.1.3.bak' in ps and 'backup="${fstab}.latticevale-v14.1.3.bak"' in ps
assert "'umount' @('-l', '--', $vaultPath)" in ps

# Built-in QMD indexer is two-hour owner; exact old manual cron marker is removed.
assert 'QMD_INDEX_INTERVAL: ${QMD_INDEX_INTERVAL:-7200}' in compose_text
assert 'QMD_INDEX_INTERVAL:-7200' in qmd
assert 'HERMES_QMD_REINDEX' in conf
assert "grep -v 'HERMES_QMD_REINDEX'" in conf

# Prior safety fixes remain present.
assert "'-WindowStyle','Hidden'" in ps
assert 'instanceIdleTimeout=-1' in ps
assert 'gateway[\'multiplex_profiles\']=False' in conf
assert not re.search(r'^[^#\n]*docker compose restart hermes', conf, re.M)
assert 'sleep infinity' not in ps.lower()
print('v13.16.6 post-install integration fixtures: PASS')
