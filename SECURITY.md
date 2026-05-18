# Security Policy

## Supported Use

`simply-ops-prism` is a local template for daily ops-audit daemons. It is not a
hosted service and does not collect telemetry.

Supported surface:

- the installer and local smoke test;
- the producer/collector schema;
- the example LaunchAgent template;
- public detector examples.

Private detector logic, real host names, secrets, production logs, OAuth files,
cookies, trading systems, and personal knowledge bases are intentionally out of
scope for this public template.

## Reporting A Vulnerability

Open a GitHub issue with:

- affected file or command;
- expected behavior;
- observed behavior;
- minimal reproduction steps;
- whether any secret or private path was printed.

Do not include real credentials, tokens, cookies, wallet keys, private hostnames,
or private logs in the issue. Replace them with placeholders such as
`<TOKEN>`, `<HOST>`, or `<PRIVATE_PATH>`.

## Secret Handling

This repo should contain only fake examples and local template code. If you find
a real credential, private path, or private workflow detail in the public tree,
report it as a security issue and stop using that release until it is removed.

## Safe Defaults

- The installer smoke test runs in temporary sandbox directories.
- The LaunchAgent uses the `com.example.*` namespace.
- Runtime inbox and cache paths are outside the repository.
- No public workflow should push, deploy, delete, or publish automatically.
