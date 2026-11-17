import configparser
from pathlib import Path
import subprocess


SYSTEMD = Path(__file__).parents[1] / 'systemd'


def test_method_service_is_bounded_nonroot_and_installation_does_not_start_it():
    service = (SYSTEMD/'invariance-swarm-alpha-method-designer.service').read_text()
    parsed = configparser.ConfigParser(strict=False, interpolation=None)
    parsed.read_string(service)
    unit = parsed['Service']
    assert unit['User'] == 'omenka'
    assert unit['NoNewPrivileges'] == 'true'
    assert unit['ProtectSystem'] == 'strict'
    assert unit['ProtectHome'] == 'read-only'
    assert unit['MemoryMax'] == '2G'
    assert unit['CPUQuota'] == '100%'
    assert 'SWARM_ENGINEERING_AUTHOR_PROVIDER=codex' in service
    assert 'strategy-author-provider.env' not in service
    assert 'alpha-method-designer.env' in service
    installer = SYSTEMD/'install-alpha-method-designer.sh'
    script = installer.read_text()
    assert 'systemctl enable' not in script
    assert 'systemctl start' not in script
    assert 'systemctl restart' not in script
    assert "env.get('SWARM_CODEX_MODEL') != state['method_model']" in script
    subprocess.run(['bash', '-n', str(installer)], check=True)
