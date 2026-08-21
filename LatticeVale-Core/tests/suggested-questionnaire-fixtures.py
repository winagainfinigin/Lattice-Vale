from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ps1 = (ROOT / 'Install-LatticeVale.ps1').read_text(encoding='utf-8')
readme = (ROOT.parent / 'docs/README.md').read_text(encoding='utf-8')
instructions = (ROOT.parent / 'docs/Instructions.txt').read_text(encoding='utf-8')
version = (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip()

assert version in {'14.3.10','14.3.11','14.3.12','14.3.13','14.3.14','14.3.15','14.3.16','14.3.17','14.3.18','14.3.19','14.3.20','14.3.21','14.3.22','14.3.23','14.3.24','14.3.25','14.3.26','14.3.27','14.3.28','14.3.29','14.3.30','14.3.31','14.3.36','14.3.37','14.3.38','14.3.40','14.3.41','14.3.42','14.3.43','14.4.0','14.4.1','14.4.2','14.4.3','14.4.4','14.4.5','14.4.6','14.4.7'}
# Fresh-install explicit mode must expose guidance without making Enter select it.
assert 'Read-YesNoExplicit $Question $Default' in ps1
assert 'Read-IntegerExplicit $Question $Min $Max $Default' in ps1
assert 'Read-MenuExplicit $Question $Options $Default' in ps1
assert "' [suggested]'" in ps1
assert 'Pressing Enter alone does not select it.' in ps1
assert '1-65535; suggested: $Default; explicit choice required' in ps1
# Tailscale guidance must surface the intended HTTPS listener choices.
assert "Get-OptionTcpPort $old 'tailscaleDashboardPort' 9443" in ps1
assert "Read-TcpPort 'Dashboard Tailscale HTTPS port' $defaultDashPort" in ps1
assert "Get-OptionTcpPort $old 'tailscaleMatrixPort' 443" in ps1
assert "Read-TcpPort 'Matrix Tailscale HTTPS port' $defaultMatrixPort $disallow" in ps1
# Free-form setup values with safe built-ins show that they are suggestions.
for prompt in (
    'Profile $i name [suggested: $defaultName; Enter accepts]',
    "Short role description for '$name' [suggested: $defaultDescription; Enter accepts]",
    'Local Ollama text model [suggested: $localTextModel; Enter accepts]',
    'Local Ollama embedding model [suggested: $localEmbeddingModel; Enter accepts]',
    'Container timezone [detected/suggested: $defaultTimezone; Enter accepts]',
):
    assert prompt in ps1, prompt
assert 'suggested values are guidance only' in readme.lower()
assert 'suggested values are guidance only' in instructions.lower()
assert 'Windows Obsidian vault folder (explicit Windows-local path required)' in ps1
assert 'no location is assumed or suggested.' in ps1
assert 'Windows Obsidian vault folder [suggested:' not in ps1
print('suggested-questionnaire fixtures: PASS')
