# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's **Security advisories**
page for this repository. Do not open a public issue containing API keys,
private Immich URLs, album IDs, asset IDs, filenames, logs with personal data,
or screenshots of private libraries.

Include only the minimum information needed to reproduce the issue. Redact all
credentials and personal media metadata.

Treat local IP addresses, Tailscale IPs and MagicDNS names, reverse-proxy
hostnames, album names, entity IDs, and Home Assistant entry IDs as private
unless you deliberately created them as public examples.

## Credential response

If an API key may have been exposed:

1. Revoke it immediately in Immich.
2. Create a replacement key with only `user.read`, `album.read`, `asset.read`,
   and `asset.view`.
3. Open **Settings → Devices & services → Immich Gallery → Configure**, enter
   the replacement key, and save.
4. Review Home Assistant logs, diagnostics, backups, and issue attachments for
   accidental disclosure.

## Security boundaries

Immich Gallery does not provide a network boundary around Home Assistant or
Immich. Administrators remain responsible for TLS, firewalling, reverse-proxy
configuration, Home Assistant access control, backups, and API-key lifecycle.
