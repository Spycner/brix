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
    $projects = Find-SqlfluffProjects -Root $root -RequireDbt:$RequireDbt

    if (-not $projects -or $projects.Count -eq 0) {
        $configType = if ($RequireDbt) { '.sqlfluff + dbt_project.yml' } else { '.sqlfluff' }
        Write-Host "No $configType projects found"
        return 0
    }

    Write-Host "Found $($projects.Count) project(s) with .sqlfluff config"

    $exitCode = 0

    foreach ($projectDir in $projects) {
        Write-Host "`n=== Running sqlfluff $Mode in $projectDir ==="

        # Build sqlfluff command arguments
        $args = @($Mode, '--processes', '0', '--disable-progress-bar')
        if ($Mode -eq 'fix') {
            $args += '--show-lint-violations'
        }

        Push-Location $projectDir
        try {
            & sqlfluff @args
            $result = $LASTEXITCODE
            if ($result -gt $exitCode) {
                $exitCode = $result
            }
        }
        finally {
            Pop-Location
        }
    }

    return $exitCode
}

# Main execution
$result = Invoke-Sqlfluff -Mode $Mode -RequireDbt:$RequireDbt
exit $result
