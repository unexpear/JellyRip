# Security Policy

## Supported versions

JellyRip is pre-alpha. Security fixes are applied to the current development line on `main` and the newest tagged release when practical.

## Reporting a vulnerability

Do not open a public issue for a security-sensitive problem.

Report security issues privately with:

- a description of the problem
- affected version or commit
- reproduction steps
- impact assessment
- logs or screenshots if safe to share

If GitHub private vulnerability reporting is enabled for the repository, use that. Otherwise contact the maintainer directly through the repository owner contact path before public disclosure.

## What counts as security-relevant here

Examples include:

- unsafe path handling that can overwrite unintended files
- command execution or injection issues in MakeMKV, ffprobe, PowerShell, or updater flows
- signature verification bypasses in the update path
- unsafe temp-file or installer launch behavior
- leaking secrets, tokens, or sensitive local paths through logs or releases

## Response expectations

Best effort only. This is a solo-maintained pre-alpha utility, so timelines are not guaranteed.

The preferred flow is:

1. private report
2. reproduction and impact review
3. fix and validation
4. release note or advisory when appropriate

## Disclosure

Please allow time for a fix before public disclosure, especially for issues that affect update behavior, file safety, or command execution.
