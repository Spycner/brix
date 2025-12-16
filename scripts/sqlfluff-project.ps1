#!/usr/bin/env pwsh
<#
.SYNOPSIS
    SQLFluff pre-commit hook that discovers and runs sqlfluff per-project.

.DESCRIPTION
    This script solves the SQLFluff templater limitation where the `templater` setting
    cannot be overridden in subdirectory `.sqlfluff` files. It discovers all directories
    containing `.sqlfluff` files and runs sqlfluff from within each directory.

.PARAMETER Mode
    Either "lint" or "fix".

.PARAMETER RequireDbt
    Only process directories with both .sqlfluff AND dbt_project.yml.

.EXAMPLE
    ./sqlfluff-project.ps1 -Mode lint

.EXAMPLE
    ./sqlfluff-project.ps1 -Mode fix -RequireDbt
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('lint', 'fix')]
    [string]$Mode,

    [switch]$RequireDbt
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Determine how to invoke sqlfluff:
# - If pyproject.toml exists (project context), use 'uv run' to use project dependencies
# - Otherwise (external hook consumer), use sqlfluff directly if available
$script:UseSqlfluffDirect = (-not (Test-Path 'pyproject.toml')) -and
                            [bool](Get-Command 'sqlfluff' -ErrorAction SilentlyContinue)

# Directories to skip when discovering .sqlfluff files
$SkipDirs = @(
    '.venv',
    'venv',
    '.git',
    'node_modules',
    '__pycache__',
    '.tox',
    '.nox',
    '.eggs',
    'dist',
    'build'
)

function Ensure-DbtProfiles {
    <#
    .SYNOPSIS
        Ensure a default profiles.yml exists for dbt templater.
    #>
    $profileDir = Join-Path $HOME '.dbt'
    $profilePath = Join-Path $profileDir 'profiles.yml'

    if (Test-Path $profilePath) {
        return
    }

    Write-Host "Creating default profiles.yml at $profilePath"

    if (-not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }

    $content = @"
default:
  target: dev
  outputs:
    dev:
      type: databricks
      schema: default
      host: your-workspace.cloud.databricks.com
      http_path: /sql/1.0/warehouses/your-warehouse-id
      token: your-personal-access-token
      threads: 1
"@
    Set-Content -Path $profilePath -Value $content -Encoding UTF8
}

function Find-SqlfluffProjects {
    <#
    .SYNOPSIS
        Find all directories containing .sqlfluff files.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Root,

        [switch]$RequireDbt
    )

    $projects = @()

    Get-ChildItem -Path $Root -Filter '.sqlfluff' -Recurse -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $projectDir = $_.Directory

        # Skip if inside excluded directories
        $pathParts = $projectDir.FullName.Split([IO.Path]::DirectorySeparatorChar)
        $shouldSkip = $false

        foreach ($part in $pathParts) {
            if ($SkipDirs -contains $part) {
                $shouldSkip = $true
                break
            }
            # Skip hidden directories (starting with .)
            if ($part.StartsWith('.') -and $part -ne '.sqlfluff') {
                $shouldSkip = $true
                break
            }
        }

        if ($shouldSkip) {
            return
        }

        # Check for dbt_project.yml if required
        if ($RequireDbt) {
            $dbtProjectPath = Join-Path $projectDir.FullName 'dbt_project.yml'
            if (-not (Test-Path $dbtProjectPath)) {
                return
            }
        }

        $projects += $projectDir.FullName
    }

    return $projects | Sort-Object -Unique
}

function Invoke-Sqlfluff {
    <#
    .SYNOPSIS
        Discover and lint/fix all sqlfluff projects.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateSet('lint', 'fix')]
        [string]$Mode,

        [switch]$RequireDbt
    )

    $root = Get-Location
    $projects = @(Find-SqlfluffProjects -Root $root -RequireDbt:$RequireDbt)

    if (-not $projects -or $projects.Count -eq 0) {
        $configType = if ($RequireDbt) { '.sqlfluff + dbt_project.yml' } else { '.sqlfluff' }
        Write-Host "No $configType projects found"
        return 0
    }

    Write-Host "Found $($projects.Count) project(s) with .sqlfluff config"

    $results = @()

    foreach ($projectDir in $projects) {
        Write-Host "`n=== Running sqlfluff $Mode in $projectDir ==="

        # Build sqlfluff command arguments
        $args = @($Mode, '--processes', '0', '--disable-progress-bar')
        if ($Mode -eq 'fix') {
            $args += '--show-lint-violations'
        }

        Push-Location $projectDir
        try {
            # Capture both stdout and stderr
            if ($script:UseSqlfluffDirect) {
                $output = & sqlfluff @args 2>&1 | Out-String
            } else {
                $output = & uv run sqlfluff @args 2>&1 | Out-String
            }
            $result = $LASTEXITCODE

            # Store result for summary
            $results += [PSCustomObject]@{
                Project  = $projectDir
                ExitCode = $result
                Output   = $output.Trim()
            }

            # Show output immediately for feedback
            if ($output.Trim()) {
                Write-Host $output.Trim()
            }
        }
        finally {
            Pop-Location
        }
    }

    # Print summary
    $failed = @($results | Where-Object { $_.ExitCode -ne 0 })
    $passed = @($results | Where-Object { $_.ExitCode -eq 0 })

    Write-Host "`n"
    Write-Host ("=" * 60)
    Write-Host "SUMMARY: $($passed.Count) passed, $($failed.Count) failed"
    Write-Host ("=" * 60)

    if ($failed.Count -gt 0) {
        Write-Host "`nFailed projects:"
        foreach ($f in $failed) {
            Write-Host "`n--- $($f.Project) (exit code: $($f.ExitCode)) ---"
            if ($f.Output) {
                Write-Host $f.Output
            }
        }
    }

    # Return highest exit code
    $exitCode = ($results | Measure-Object -Property ExitCode -Maximum).Maximum
    if ($null -eq $exitCode) { $exitCode = 0 }
    return $exitCode
}

# Main execution
Ensure-DbtProfiles
$result = Invoke-Sqlfluff -Mode $Mode -RequireDbt:$RequireDbt
exit $result
