# CHANGELOG

<!-- version list -->

## v1.7.0 (2025-12-18)

### Features

- Run deps if necessary on pre-commit hook
  ([`6b2b0c9`](https://github.com/Spycner/brix/commit/6b2b0c9ba046af9689b9a752ccf13165a3dab1b6))


## v1.6.0 (2025-12-16)

### Features

- Cleanup mock profiles created in pre-commit
  ([`86134f5`](https://github.com/Spycner/brix/commit/86134f52c3f4bc93c2910fe65791299216227236))


## v1.5.0 (2025-12-16)

### Chores

- Update brix package version to 1.4.0 and enhance sqlfluff PowerShell script
  ([`cb58eb8`](https://github.com/Spycner/brix/commit/cb58eb854e1e120765ca0fde3053a71cab71ff4c))

### Features

- Ensure mock dbt-profile during test when none exists
  ([`3716b3a`](https://github.com/Spycner/brix/commit/3716b3a94b357a767b38f4daf4029b9ac321562f))


## v1.4.0 (2025-12-11)

### Chores

- Simplify GitHub Actions workflow by removing Python version matrix
  ([`72fff18`](https://github.com/Spycner/brix/commit/72fff18c705fa34efed8b173fd1283d35a46d47b))

- Update dependencies and add end-to-end tests for git installation
  ([`caf7f49`](https://github.com/Spycner/brix/commit/caf7f49e63f52a4f833fdcc0a05788b91a4c1bab))

- Update pre-commit configuration and add GitHub Actions workflow for testing
  ([`0a0fdaf`](https://github.com/Spycner/brix/commit/0a0fdaf368f32c49cc3397607a4daedc3622d2bd))

- Update project configuration and add SQLFluff support
  ([`0826841`](https://github.com/Spycner/brix/commit/0826841bae6506da1dc148770b003e7dff92105e))

### Documentation

- Remove PyPI badge from README for clarity
  ([`2bcab1a`](https://github.com/Spycner/brix/commit/2bcab1a9715ecdd79be42e3dfd2e60efd38045ae))

### Features

- Add dbt package installation step for test fixtures in pre-commit workflow
  ([`217d277`](https://github.com/Spycner/brix/commit/217d277d66631cbd6f0444d591f5aabee2685376))

- Add PowerShell hooks for SQLFluff linting and fixing
  ([`ceecd9a`](https://github.com/Spycner/brix/commit/ceecd9abcb2decb05d524d635cec96516ba5eb63))

- Add SQLFluff pre-commit hooks and scripts for project linting and fixing
  ([`87d4e79`](https://github.com/Spycner/brix/commit/87d4e7986fe7a562c992acff11a8c39c54ed029a))

- Add SQLFluff profiles configuration for testing
  ([`51875c9`](https://github.com/Spycner/brix/commit/51875c95f347b4e80af501196ed77a2750d24754))


## v1.3.0 (2025-11-28)

### Chores

- Update GitHub Actions workflows for documentation
  ([`0a0f61b`](https://github.com/Spycner/brix/commit/0a0f61b810898e95b53cb4352de92e0c8409b663))

### Documentation

- Update log format description in BrixFormatter
  ([`b986ab8`](https://github.com/Spycner/brix/commit/b986ab8b41a0bf517a8ed175b4dcaea3fc6f1223))

### Features

- Add initial documentation and configuration for Brix CLI
  ([`fa5438c`](https://github.com/Spycner/brix/commit/fa5438ccf41f17d622d46e0476a621c97d360596))


## v1.2.0 (2025-11-28)

### Bug Fixes

- Update version check logic and clean up dbt command
  ([`d3274eb`](https://github.com/Spycner/brix/commit/d3274ebb85fdda51c46e6ee1fc9b3de2be905c8d))

### Features

- Add dbt project management commands and structure
  ([`a9a3ff0`](https://github.com/Spycner/brix/commit/a9a3ff0378dbe06ce8abcabce2ff11dd0dee4f5c))

- Add end-to-end testing and enhance dbt project management
  ([`37ca697`](https://github.com/Spycner/brix/commit/37ca69737c445ed3aebd074e247785bfa55a983c))

- Enhance dbt command with project path caching and validation
  ([`da9a53f`](https://github.com/Spycner/brix/commit/da9a53f66e5e9921e907f3d4949daf9b93108ac9))

- Enhance dbt project package management with validation and parallel fetching
  ([`59b7a0d`](https://github.com/Spycner/brix/commit/59b7a0d08371206a9774fcde0241c080090c97a4))

- Implement interactive editing for dbt projects
  ([`39ad0f9`](https://github.com/Spycner/brix/commit/39ad0f925bc5f3cbc584cb1ad6740ca92bd00f82))


## v1.1.0 (2025-11-27)

### Features

- Enhance dbt profile management with Databricks support and output configuration updates
  ([`3da9c3e`](https://github.com/Spycner/brix/commit/3da9c3e3a5a04acfcfb626a7aaa503f6ff998830))

### Refactoring

- Update documentation structure and enhance architecture details
  ([`d9c7137`](https://github.com/Spycner/brix/commit/d9c71375754c048431aef3cd440598c3c8c22b66))


## v1.0.1 (2025-11-27)

### Bug Fixes

- Change code review workflow to trigger on /review command
  ([`1517d73`](https://github.com/Spycner/brix/commit/1517d73a89cd7c4a6a5786c77d349cd325cc00c6))

### Chores

- Update release workflow and configuration
  ([`cfc88ef`](https://github.com/Spycner/brix/commit/cfc88ef8551aed97d11c98f8cdd56a4a32943e61))

### Documentation

- Update CLAUDE.md with new test structure and pre-commit instructions
  ([`8e12b28`](https://github.com/Spycner/brix/commit/8e12b28e0f18cd5ccccab181afa574bf04154a39))

### Refactoring

- Restructure tests to unit/integration and add dbt dependency
  ([`cc78d20`](https://github.com/Spycner/brix/commit/cc78d20045aa6a358d82196adb57708fab3e07f7))


## v1.0.0 (2025-11-26)

- Initial Release
