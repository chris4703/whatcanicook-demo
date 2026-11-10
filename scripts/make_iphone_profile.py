"""Package an existing public root certificate for manual iPhone installation."""
import argparse
from pathlib import Path
import plistlib
import ssl
import uuid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('certificate', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
certificate = ssl.PEM_cert_to_DER_cert(args.certificate.read_text())
profile = {
    'PayloadType': 'Configuration', 'PayloadVersion': 1,
    'PayloadIdentifier': 'local.whatcanicook.certificate-profile',
    'PayloadUUID': str(uuid.uuid4()).upper(),
    'PayloadDisplayName': 'Pantry — Local HTTPS',
    'PayloadDescription': 'Installs your own Pantry server’s local certificate authority. Enable full trust manually in Certificate Trust Settings after installation.',
    'PayloadOrganization': 'Your household',
    'PayloadRemovalDisallowed': False,
    'PayloadContent': [{
        'PayloadType': 'com.apple.security.root', 'PayloadVersion': 1,
        'PayloadIdentifier': 'local.whatcanicook.root-certificate',
        'PayloadUUID': str(uuid.uuid4()).upper(),
        'PayloadDisplayName': 'Pantry local certificate authority',
        'PayloadCertificateFileName': 'pantry-root.crt',
        'PayloadContent': certificate,
    }],
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(plistlib.dumps(profile))
print('Created', args.output)
