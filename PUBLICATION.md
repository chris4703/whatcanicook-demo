# Public release preparation

This is a generalized demonstration of What Can I Cook?, prepared from the GitHub source rather than from a running household's database or an uncommitted local checkout.

## Generalization

- Replaced the personal Bonjour hostname and fixed home-network IP examples with localhost defaults and environment-specific setup notes.
- Replaced Mac mini-specific interface and certificate-profile wording with server-neutral language.
- Gave the demo its own Compose project, volume namespace, example ports, and optional macOS forwarder label.
- Made local HTTPS and the large barcode-catalog download opt-in profiles.
- Kept recipe search optional, with a blank example key and no test-time provider calls.
- Preserved provider attribution and third-party scanner license files.

No original deployment data, API keys, recipient lists, certificates, private CA keys, or household inventory is included. Sample provider-contact fields use a reserved example domain. Hardware, network configuration, software versions, and service requirements vary by installation.

## Clean history

The `public-ready` branch is an independent root commit, with no parents from the original repository history. It is isolated from the original `main` branch and does not change the household deployment or its uncommitted local work.

Keep the original repository private if its other refs or historical material should stay private. Changing its default branch does not hide the original branches or history.

To publish separately, create a **new, empty** public repository, without an initial README, `.gitignore`, or license commit. From a clone containing this clean branch:

```sh
# Set PUBLIC_REPOSITORY_URL to the new repository you control.
git push "$PUBLIC_REPOSITORY_URL" public-ready:main
```

Push only this branch, not `--all`, `--mirror`, or the original tags. A new public repository does not require redirecting the original deployment's remote. Choose a license deliberately before inviting code reuse.

## Review limits

The clean tree and its independent history are scanned for credential patterns and reviewed for personal hostnames, contact details, and runtime data. Tests and local browser checks use fresh data with provider calls mocked or disabled. No private configuration is copied from the running pantry.

This does not audit the original repository's Issues, PRs, releases, Actions artifacts, or hidden historical refs. Publishing the source does not make the unauthenticated app suitable for an unrestricted public deployment. Anyone reaching an instance can change its pantry; configured recipe calls can also incur provider costs.

## Preparation verification

The generalized edition passed 19 tests in its Python Docker image, with networking disabled for the test container. Compose validation covered the core-only defaults and both optional profiles. Desktop and mobile browser checks used a fresh demo volume, manual sample inventory, and a blank recipe key; all navigation, manual entry, and the unconfigured-recipe response worked with no JavaScript errors or outbound browser requests. A staged-tree scan and clean-history Gitleaks scan found no credential-pattern matches. Camera access on a physical phone, real provider requests, a full catalog download, and device certificate trust were not exercised.
