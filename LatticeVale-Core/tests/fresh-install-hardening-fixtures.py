from pathlib import Path
root=Path(__file__).resolve().parents[1]
ps=(root/'Install-LatticeVale.ps1').read_text()
boot=(root/'linux/bootstrap.sh').read_text()
cfg=(root/'stack/configure-stack.sh').read_text()
version=(root/'VERSION.txt').read_text().strip()
assert version in {'14.3.0','14.3.1','14.3.2','14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0'}
assert "'VERSION.txt'" in ps
assert 'installerVersion = $bundleVersion' in ps
assert '$optionsB64, $bundleVersion, $forceManagedUpdateArg)' in ps
assert 'function Copy-LocalFileToWslRoot' in ps
assert 'RedirectStandardInput' in ps
assert "'root' 'install' @('-d', '-m', '0700'" in ps
assert 'chmod -R 0777' not in ps
assert 'linux_uid="$(id -u "$linux_user")"' in boot
assert 'linux_gid="$(id -g "$linux_user")"' in boot
assert ' -o "$linux_user" -g "$linux_user"' not in boot
assert '$linux_user:$linux_user' not in boot
assert 'installer_version="${3:-v13}"' in boot
assert 'INSTALLER_VERSION="$(opt_text installerVersion)"' in cfg
assert "'installerVersion','installerMode'" in cfg
# Fresh external-provider setup and non-cloned profile setup both require a PTY.
assert 'runuser --pty -u "$linux_user"' in boot
assert 'docker run --rm -it' in cfg
assert 'mapfile -t requested_workers' in cfg
assert 'docker exec -it -u hermes hermes-agent hermes -p "$name" model' in cfg

# v13.10 cross-machine hardening.
assert 'export DOCKER_HOST=unix:///var/run/docker.sock' in boot
assert 'cat > /etc/apt/apt.conf.d/20auto-upgrades' not in boot
assert 'cmp -s "$legacy_periodic" "$legacy_expected"' in boot
assert 'com.docker.compose.project.working_dir' in cfg
assert 'Refusing to reuse an ambiguous pre-existing network.' in cfg
print('FRESH INSTALL HARDENING: PASS')
print('- actual primary UID/GID used; no same-named-group assumption')
print('- exact hotfix version participates in checkpoint identity')
print('- private WSL staging is streamed through stdin; no UNC write/0777 window')
print('- fresh external-provider/profile TTY paths remain interactive')
