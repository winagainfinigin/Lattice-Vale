from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ps1 = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()

assert version in {'14.3.3','14.3.4','14.3.5','14.3.6','14.3.7','14.3.8','14.3.9','14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7','14.4.8','14.4.81','14.4.82','14.4.83','14.4.84','14.4.85','14.5.0','14.5.1','14.5.2','14.5.3','14.5.4','14.5.42','14.5.43','14.5.44','14.5.45','14.5.46'}
assert '[bool]$AllowExistingRoomSelection = $false' in ps1
assert "$existingMatrixDeployment = $false" in ps1
assert "data/synapse/homeserver.yaml" in ps1
assert "if ($AllowExistingRoomSelection)" in ps1
assert "No existing LatticeVale Matrix/Synapse deployment is available yet." in ps1
assert "LatticeVale will create a new private encrypted room for '$name' after Matrix is installed." in ps1
assert "Complete-WorkerMatrixOptions $workers $matrix $false $true $existingMatrixDeployment" in ps1
assert "Complete-WorkerMatrixOptions $workers $matrix $true $true $existingMatrixDeployment" in ps1
# Existing-room ID prompts must remain reachable only inside the availability guard.
guard = ps1.index('if ($AllowExistingRoomSelection)')
prompt = ps1.index('Use an existing encrypted Matrix room for')
create_notice = ps1.index('No existing LatticeVale Matrix/Synapse deployment is available yet.')
assert guard < prompt < create_notice
print('v14.3.3 Matrix room questionnaire fixtures: PASS')
