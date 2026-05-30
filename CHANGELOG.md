# Changelog

## [0.3.0](https://github.com/lokkju/git-spreader/compare/v0.2.3...v0.3.0) (2026-05-30)


### Features

* Add init and config --edit; round-trip author config ([5d11939](https://github.com/lokkju/git-spreader/commit/5d11939805a289307110065f65bff8f8e5f143cd))
* Replace backup ref with a git bundle; validate range ends at HEAD ([b466c1f](https://github.com/lokkju/git-spreader/commit/b466c1f2fec17cd99f1d667d4c80fffe80dd2a48))


### Bug Fixes

* Compress gaps on overflow even with an auto end-date ([f006c2a](https://github.com/lokkju/git-spreader/commit/f006c2aaa0eea83363e6d61e3190866ba5ae2fdb))
* Correct timezone offset for half-hour zones west of UTC ([e2e8f0b](https://github.com/lokkju/git-spreader/commit/e2e8f0bed1ef705289f052c9c20a0f28f46d4b95))
* Enforce strictly-increasing timestamps; document new commands ([91e0ffd](https://github.com/lokkju/git-spreader/commit/91e0ffd59220a3942a5bf6d0b9a4ff7725c73035))
* Make weekend modifier local and move each commit at most once ([f065422](https://github.com/lokkju/git-spreader/commit/f06542272d9c9b6fbb5ee9adf8dc165cc859d17c))
* Match commits by SHA and preserve ancestor history in rewrite ([38e9055](https://github.com/lokkju/git-spreader/commit/38e9055f9b29edd5ad1a654dda8376e279c5264b))
