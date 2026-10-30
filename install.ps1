# Magenta Agents installer for Windows (PowerShell 5.1 or 7).
#
#   irm https://raw.githubusercontent.com/devlnull/magenta-agents/main/install.ps1 | iex
#
# Options (environment variables, set them before you run the command):
#   $env:MAGENTA_TARGET = "claude-code" | "opencode" | "codex"   (default claude-code)
#   $env:MAGENTA_REF    = "<branch or tag>"                        (default main)
#   $env:MAGENTA_HOME   = "<folder for the source>"                (default $HOME\.magenta-agents)
#   $env:MAGENTA_REPO   = "<git URL>"
#
# Claude Code on Windows runs hooks with Git Bash. Install Git for Windows and Python 3.9+.
$ErrorActionPreference = "Stop"

$Repo   = if ($env:MAGENTA_REPO)   { $env:MAGENTA_REPO }   else { "https://github.com/devlnull/magenta-agents.git" }
$Ref    = if ($env:MAGENTA_REF)    { $env:MAGENTA_REF }    else { "main" }
$Dir    = if ($env:MAGENTA_HOME)   { $env:MAGENTA_HOME }   else { Join-Path $HOME ".magenta-agents" }
$Target = if ($env:MAGENTA_TARGET) { $env:MAGENTA_TARGET } else { "claude-code" }

function Fail($message) { Write-Error "magenta: $message"; exit 1 }

$Python = $null
foreach ($candidate in @("py -3", "python", "python3")) {
  $parts = $candidate -split " "
  if (Get-Command $parts[0] -ErrorAction SilentlyContinue) {
    $checkArgs = @($parts | Select-Object -Skip 1) + @("-c", "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)")
    & $parts[0] @checkArgs 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $Python = $parts; break }
  }
}
if (-not $Python) { Fail "Python 3.9 or later is necessary. Install it from https://www.python.org or with: winget install Python.Python.3.12" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "git is necessary. Install it with: winget install Git.Git" }

function Run-Python([string[]]$Arguments) {
  $exe = $Python[0]
  $all = @($Python | Select-Object -Skip 1) + $Arguments
  & $exe @all
  if ($LASTEXITCODE -ne 0) { Fail "command failed: $exe $($all -join ' ')" }
}

if (Test-Path (Join-Path $Dir ".git")) {
  Write-Host "magenta: updating $Dir to $Ref"
  git -C $Dir fetch --quiet --depth 1 origin $Ref; if ($LASTEXITCODE -ne 0) { Fail "git fetch failed" }
  git -C $Dir checkout --quiet --force FETCH_HEAD; if ($LASTEXITCODE -ne 0) { Fail "git checkout failed" }
} else {
  Write-Host "magenta: downloading $Repo ($Ref) to $Dir"
  git clone --quiet --depth 1 --branch $Ref $Repo $Dir; if ($LASTEXITCODE -ne 0) { Fail "git clone failed" }
}

$cli = Join-Path $Dir "magenta.py"
Run-Python @($cli, "validate")
Run-Python @($cli, "build")
Run-Python @($cli, "install", "--target", $Target)

Write-Host ""
Write-Host "Magenta is installed for $Target."
Write-Host "Next steps:"
Write-Host "  1. Prepare a repository:  $($Python -join ' ') `"$cli`" init C:\path\to\your\repository"
Write-Host "  2. Start the lead agent:   cd C:\path\to\your\repository; claude --agent magenta-principal"
Write-Host "  3. Ask it:                 `"Run discover-project.`""
Write-Host "Update later: run this installer again. Remove: $($Python -join ' ') `"$cli`" uninstall"
