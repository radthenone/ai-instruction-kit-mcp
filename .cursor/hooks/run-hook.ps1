# Cursor hook launcher (Windows): pipe stdin JSON into Git Bash non-interactively.
# Avoids `bash --login -i` leftover console windows from bare `.sh` paths.
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Script
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$scriptPath = Join-Path $PSScriptRoot $Script
if (-not (Test-Path -LiteralPath $scriptPath)) {
    [Console]::Out.Write('{"permission":"deny","user_message":"Hook: brak pliku skryptu","agent_message":"run-hook.ps1: script not found"}')
    exit 1
}

function Find-GitBash {
    $cmd = Get-Command bash -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) { return $cmd.Source }
    $candidates = @(
        (Join-Path ${env:ProgramFiles} 'Git\bin\bash.exe'),
        (Join-Path ${env:ProgramFiles} 'Git\usr\bin\bash.exe'),
        (Join-Path ${env:LOCALAPPDATA} 'Programs\Git\bin\bash.exe')
    )
    foreach ($path in $candidates) {
        if ($path -and (Test-Path -LiteralPath $path)) { return $path }
    }
    return $null
}

function Read-HookStdin {
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    $stream = [Console]::OpenStandardInput()
    $reader = New-Object System.IO.StreamReader($stream, $utf8, $true)
    $text = $reader.ReadToEnd()
    if ($null -eq $text) { return '' }
    # Windows Cursor may prefix UTF-8 BOM
    return $text.TrimStart([char]0xFEFF)
}

$bash = Find-GitBash
if (-not $bash) {
    [Console]::Out.Write('{"permission":"deny","user_message":"Hook: brak bash (Git for Windows)","agent_message":"run-hook.ps1: Git Bash not found"}')
    exit 1
}

$stdin = Read-HookStdin

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $bash
# Prefer forward slashes for Git Bash on Windows
$bashScript = $scriptPath -replace '\\', '/'
$psi.Arguments = "--noprofile --norc `"$bashScript`""
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true
$psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
$psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)

$proc = [System.Diagnostics.Process]::Start($psi)
$proc.StandardInput.Write($stdin)
$proc.StandardInput.Close()
$stdout = $proc.StandardOutput.ReadToEnd()
$stderr = $proc.StandardError.ReadToEnd()
$proc.WaitForExit()

$out = if ($null -eq $stdout) { '' } else { $stdout.Trim() }
if ([string]::IsNullOrWhiteSpace($out)) {
    $hint = if ($stderr) { ($stderr.Trim() -replace '["\\]', '') } else { 'empty stdout from bash hook' }
    if ($hint.Length -gt 160) { $hint = $hint.Substring(0, 160) }
    $out = "{`"permission`":`"deny`",`"user_message`":`"Hook: brak JSON`",`"agent_message`":`"run-hook.ps1: $hint`"}"
}

[Console]::Out.Write($out)
exit $proc.ExitCode
