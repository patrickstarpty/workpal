export const DOCS_URL = "http://127.0.0.1:4000/docs";
export const CHANGELOG_URL = "/#/review/changelog";
// Absolute, including on self-hosted deployments: the installers we ship are
// the same binaries either way, and the desktop client can point at a
// self-hosted backend once installed. A self-host-relative /download would
// only serve a copy of this page that still has to reach our release assets.
export const DOWNLOAD_URL = "https://workpal.invalid/download";
