#!/usr/bin/env python3
from pathlib import Path
import json, os, signal, subprocess, tempfile, textwrap, time

ROOT=Path(__file__).resolve().parents[1]
TEST_TMP_BASE='/dev/shm' if Path('/dev/shm').is_dir() and os.access('/dev/shm', os.W_OK) else None

def reset_child_signals():
    # Detached audit harnesses can inherit SIGINT/SIGTERM as ignored. Reset them in
    # the child before exec so this simulation actually exercises configure-stack.sh's
    # INT/TERM checkpoint trap regardless of how the test runner itself was launched.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

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
        'searxng':True,'qmd':False,'honcho':False,'hermesLocalAI':False,'localTextModel':'qwen3.5:4b','localEmbeddingModel':'qwen3-embedding:4b','obsidian':False,'unattendedUpdates':False,
        'autoStart':False,'windowsShortcuts':False,'resetCheckpoints':False,'forceProviderSetup':False,'forceProfileSetup':False,
        'rebuildMatrixIdentity':False,'installerMode':'resume'
    }
    (stack/'install-options.json').write_text(json.dumps(opts),encoding='utf-8')
    cfg=stack/'data/hermes/config.yaml'; cfg.parent.mkdir(parents=True); cfg.write_text('model:\n  default: test/model\n')

    fakebin=Path(td)/'bin'; fakebin.mkdir(); log=Path(td)/'docker.log'
    docker=fakebin/'docker'
    docker.write_text(textwrap.dedent(f'''\
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> {str(log)!r}
        if [[ "${{HERMES_TEST_SLOW:-0}}" == 1 && "$1 $2 $3" == "compose pull --ignore-buildable" ]]; then sleep 4; fi
        if [[ "$1" == "inspect" ]]; then exit 1; fi
        if [[ "$1" == "network" && "$2" == "inspect" ]]; then exit 1; fi
        if [[ "$1" == "ps" ]]; then exit 0; fi
        if [[ "$1" == "compose" ]]; then
          if [[ "$2" == "ps" && "$*" == *"--status running hermes"* ]]; then echo hermes; fi
          exit 0
        fi
        if [[ "$1" == "exec" ]]; then
          # Model the exact healthy default-gateway supervisor state required by
          # production before LatticeVale performs a gateway lifecycle mutation.
          if [[ "$*" == *"/command/s6-svstat"* && "$*" == *"/run/service/gateway-default"* ]]; then
            echo 'up (pid 4242) 1 seconds'
            exit 0
          fi
          [[ "$*" == *"config get model.default"* ]] && echo test/model
          [[ "$*" == *"--version"* ]] && echo 'Hermes test'
          exit 0
        fi
        exit 0
    ''')); docker.chmod(0o755)
    fakecurl=fakebin/'curl'
    fakecurl.write_text(textwrap.dedent('''\
        #!/usr/bin/env bash
        # Simulate a healthy localhost HTTP endpoint. curl -w callers need a status code.
        if [[ "$*" == *"%{http_code}"* ]]; then printf '200'; fi
        exit 0
    ''')); fakecurl.chmod(0o755)

    # Keep one lightweight mocked infrastructure service selected so stage_infrastructure
    # always executes the deliberately slowed Compose pull used as the SIGINT target.
    env=os.environ.copy(); env['PATH']=str(fakebin)+os.pathsep+env['PATH']; env['USER']='tester'; env['HERMES_TEST_SLOW']='1'

    interrupt_out=stack/'test-interrupt.out'; interrupt_err=stack/'test-interrupt.err'
    out_f=interrupt_out.open('w'); err_f=interrupt_err.open('w')
    proc=subprocess.Popen(['bash','./configure-stack.sh'],cwd=stack,env=env,text=True,stdout=out_f,stderr=err_f,start_new_session=True,preexec_fn=reset_child_signals)
    deadline=time.time()+60
    while time.time()<deadline:
        st=json.loads((stack/'.installer-state.json').read_text()) if (stack/'.installer-state.json').exists() else {}
        docker_log=log.read_text(encoding='utf-8') if log.exists() else ''
        # Wait until the mocked long-running pull is actually in progress. Signalling as
        # soon as the stage checkpoint appears races Bash process/command substitution
        # setup and can exercise a shell parser edge case instead of LatticeVale's
        # intended interruption/checkpoint behavior.
        if st.get('currentStage')=='infrastructure' and 'compose pull --ignore-buildable' in docker_log:
            break
        time.sleep(.1)
    else:
        os.killpg(proc.pid, signal.SIGKILL); raise AssertionError('did not reach the slow infrastructure pull')
    os.killpg(proc.pid, signal.SIGINT)
    proc.wait(timeout=30); out_f.close(); err_f.close()
    out=interrupt_out.read_text(); err=interrupt_err.read_text()
    # Kill any test-only descendants still in the process group.
    try: os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    assert proc.returncode in (130,-signal.SIGINT), (proc.returncode,out,err)
    state=json.loads((stack/'.installer-state.json').read_text())
    assert state['currentStage']=='infrastructure', state
    assert state['stages']['infrastructure']['status']=='broken', state['stages']['infrastructure']
    assert state['stages']['prepare_config']['status']=='done'

    env['HERMES_TEST_SLOW']='0'
    resume_out=stack/'test-resume.out'; resume_err=stack/'test-resume.err'
    with resume_out.open('w') as out_f2, resume_err.open('w') as err_f2:
        resumed=subprocess.run(['bash','./configure-stack.sh'],cwd=stack,env=env,text=True,stdout=out_f2,stderr=err_f2,timeout=180)
    resume_text=resume_out.read_text()+"\n"+resume_err.read_text()
    assert resumed.returncode==0, resume_text
    state=json.loads((stack/'.installer-state.json').read_text())
    assert state['status']=='complete' and state['currentStage'] is None
    assert 'OK - already complete' in resume_out.read_text()

print('INTERRUPTION/RESUME SIMULATION: PASS')
print('- SIGINT during infrastructure is checkpointed as broken')
print('- completed earlier stage is preserved')
print('- next run resumes/reconciles and finishes successfully')
