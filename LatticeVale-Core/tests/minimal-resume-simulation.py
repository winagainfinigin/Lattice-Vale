#!/usr/bin/env python3
from pathlib import Path
import json, os, subprocess, tempfile, textwrap

ROOT=Path(__file__).resolve().parents[1]
TEST_TMP_BASE='/dev/shm' if Path('/dev/shm').is_dir() and os.access('/dev/shm', os.W_OK) else None

with tempfile.TemporaryDirectory(dir=TEST_TMP_BASE) as td:
    stack=Path(td)/'stack'; stack.mkdir()
    # Stage the same canonical architecture inputs that the real 14.6 bootstrap
    # places in ~/hermes-stack. Resume simulations must exercise the current stack
    # contract rather than a pre-14.6 partial copy.
    for source_rel in (
        'compatibility.conf',
        'stack/configure-stack.sh', 'stack/compose.yaml',
        'stack/latticevale_arch.py', 'stack/hardware-capabilities.py',
        'stack/backend-capabilities.py', 'stack/runtime-policy.py',
        'stack/diagnostics.py', 'stack/checkpoint-metadata.json',
    ):
        src=ROOT/source_rel
        (stack/src.name).write_bytes(src.read_bytes())
    (stack/'configure-stack.sh').chmod(0o755)
    # The production script must reject root, but CI/audit containers may themselves run as root.
    # Neutralize only the copied test script's root guard so the recovery state machine can
    # be exercised without changing the production installer or depending on runuser signal handling.
    if os.geteuid() == 0:
        test_cfg = stack/'configure-stack.sh'
        text = test_cfg.read_text(encoding='utf-8')
        guard = "if [[ $EUID -eq 0 ]]; then echo 'Run this script as the normal Ubuntu user, not root.' >&2; exit 1; fi"
        assert guard in text
        test_cfg.write_text(text.replace(guard, ': # root guard neutralized in test copy only', 1), encoding='utf-8')
        test_cfg.chmod(0o755)
    opts={
        'schema':16,'installerVersion':'14.3.0','timezone':'Etc/UTC','dashboard':False,'multiAgent':False,'workers':[],'ollamaAcceleration':'cpu','containerResourceLimits':False,
        'kanban':False,'matrix':False,'tailscale':False,'tailscaleDashboard':False,'tailscaleMatrix':False,
        'searxng':False,'qmd':False,'honcho':False,'hermesLocalAI':False,'localTextModel':'qwen3.5:4b','localEmbeddingModel':'qwen3-embedding:4b','obsidian':False,'unattendedUpdates':False,
        'autoStart':False,'windowsShortcuts':False,'resetCheckpoints':False,'forceProviderSetup':False,'forceProfileSetup':False,
        'rebuildMatrixIdentity':False,'installerMode':'resume'
    }
    (stack/'install-options.json').write_text(json.dumps(opts),encoding='utf-8')
    cfg=stack/'data/hermes/config.yaml'; cfg.parent.mkdir(parents=True)
    cfg.write_text('model:\n  default: test/model\n',encoding='utf-8')

    fakebin=Path(td)/'bin'; fakebin.mkdir(); log=Path(td)/'docker.log'
    docker=fakebin/'docker'
    docker.write_text(textwrap.dedent(f'''\
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> {str(log)!r}
        if [[ "$1" == "inspect" ]]; then exit 1; fi
        if [[ "$1" == "network" && "$2" == "inspect" ]]; then exit 1; fi
        if [[ "$1" == "ps" ]]; then
          exit 0
        fi
        if [[ "$1" == "compose" ]]; then
          if [[ "$2" == "ps" && "$*" == *"--status running hermes"* ]]; then echo hermes; fi
          exit 0
        fi
        if [[ "$1" == "exec" ]]; then
          # The production installer requires exact s6 supervisor state before
          # mutating a gateway. This simulation models a healthy default gateway,
          # so its fake docker CLI must return realistic s6-svstat output instead
          # of a successful command with an empty/ambiguous response.
          if [[ "$*" == *"/command/s6-svstat"* && "$*" == *"/run/service/gateway-default"* ]]; then
            echo 'up (pid 4242) 1 seconds'
            exit 0
          fi
          if [[ "$*" == *"config get model.default"* ]]; then echo test/model; fi
          if [[ "$*" == *"--version"* ]]; then echo 'Hermes test'; fi
          exit 0
        fi
        if [[ "$1" == "pull" ]]; then exit 0; fi
        if [[ "$1" == "rm" ]]; then exit 0; fi
        exit 0
    '''),encoding='utf-8'); docker.chmod(0o755)

    fakesleep=fakebin/'sleep'
    fakesleep.write_text('#!/usr/bin/env bash\nexit 0\n',encoding='utf-8'); fakesleep.chmod(0o755)

    fakecurl=fakebin/'curl'
    fakecurl.write_text(textwrap.dedent('''\
        #!/usr/bin/env bash
        # Simulate a healthy localhost HTTP endpoint. curl -w callers need a status code.
        if [[ "$*" == *"%{http_code}"* ]]; then printf '200'; fi
        exit 0
    ''')); fakecurl.chmod(0o755)

    env=os.environ.copy(); env['PATH']=str(fakebin)+os.pathsep+env['PATH']; env['USER']='tester'
    first_out=stack/'test-first.out'; first_err=stack/'test-first.err'
    with first_out.open('w') as out, first_err.open('w') as err:
        first=subprocess.run(['bash','./configure-stack.sh'],cwd=stack,env=env,text=True,stdout=out,stderr=err,timeout=240)
    first_text=first_out.read_text()+"\n"+first_err.read_text()
    assert first.returncode==0, first_text
    state=json.loads((stack/'.installer-state.json').read_text())
    assert state['status']=='complete' and state['currentStage'] is None
    assert all((state['stages'].get(s) or {}).get('status')=='done' for s in (
        'prepare_config','infrastructure','matrix_bootstrap','provider_setup','profiles','matrix_profiles','matrix_cross_signing','matrix_profile_cross_signing','integrations','reconcile','kanban_gateway','finalize'))
    event_lines=(stack/'logs/installer-events.jsonl').read_text().splitlines()
    assert any(json.loads(x).get('status')=='complete' for x in event_lines)
    pulls_before=sum(1 for x in log.read_text().splitlines() if x.startswith('pull '))
    assert pulls_before>=1

    # Targeted repair regression: a later stage may need to execute even when all
    # earlier stages live-verify and are skipped. provider_setup must therefore
    # reload HERMES_IMAGE from persisted .env rather than depend on infrastructure
    # having executed in the same shell process.
    state=json.loads((stack/'.installer-state.json').read_text())
    state['status']='broken'
    state['currentStage']='provider_setup'
    state['stages']['provider_setup']['status']='broken'
    state['lastErrorStage']='provider_setup'
    state['lastError']='simulated targeted provider repair'
    (stack/'.installer-state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')

    repair_out=stack/'test-repair.out'; repair_err=stack/'test-repair.err'
    with repair_out.open('w') as out, repair_err.open('w') as err:
        repair=subprocess.run(['bash','./configure-stack.sh'],cwd=stack,env=env,text=True,stdout=out,stderr=err,timeout=240)
    repair_text=repair_out.read_text()+"\n"+repair_err.read_text()
    assert repair.returncode==0, repair_text
    assert 'Configure and verify default Hermes provider/model' in repair_out.read_text()
    assert 'unbound variable' not in repair_text.lower(), repair_text
    pulls_after_repair=sum(1 for x in log.read_text().splitlines() if x.startswith('pull '))
    assert pulls_after_repair==pulls_before+1, (pulls_before,pulls_after_repair)

    second_out=stack/'test-second.out'; second_err=stack/'test-second.err'
    with second_out.open('w') as out, second_err.open('w') as err:
        second=subprocess.run(['bash','./configure-stack.sh'],cwd=stack,env=env,text=True,stdout=out,stderr=err,timeout=240)
    second_text=second_out.read_text()+"\n"+second_err.read_text()
    assert second.returncode==0, second_text
    assert second_out.read_text().count('OK - already complete')==12, second_out.read_text()
    pulls_after=sum(1 for x in log.read_text().splitlines() if x.startswith('pull '))
    assert pulls_after==pulls_after_repair, (pulls_after_repair,pulls_after)

print('MINIMAL RESUME SIMULATION: PASS')
print('- first run completes all twelve stages against a mocked healthy runtime')
print('- targeted provider repair works while earlier stages live-verify and skip')
print('- final rerun live-verifies and skips all twelve completed stages')
print('- structured event log is written without terminal transcript capture')
