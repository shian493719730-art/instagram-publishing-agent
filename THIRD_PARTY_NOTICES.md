# Dependencies and references

## Used dependency

The optional SVG renderer uses `@resvg/resvg-js` version **2.6.2**, pinned in
`package-lock.json`. Its package license is **MPL-2.0**. The original package and
its license files are installed by npm; this repository does not vendor or modify
the dependency's source code.

- Package: https://www.npmjs.com/package/@resvg/resvg-js
- Source: https://github.com/yisibl/resvg-js

The Python queue, offline demo, and tests use the Python standard library only.
CI references official GitHub-maintained checkout and Python-setup actions by
full commit SHA.

## Researched reference, not bundled

[Postiz](https://github.com/gitroomhq/postiz-app) was examined as a possible
self-hosted publishing backend and Instagram provider reference. Its repository
uses **AGPL-3.0**. No Postiz code is copied or bundled here, and its stack is not
deployed by this project.

## Official documentation

- [Meta Instagram API collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api)
- [Scheduled tasks](https://learn.chatgpt.com/docs/automations)

The browser prototype does not implement these APIs. Any future official API
adapter must verify current account eligibility, permissions, media specifications,
and publishing limits in the relevant official documentation.

## Project license

No project license has been selected. Public repository visibility does not change
the licenses of its dependencies.
