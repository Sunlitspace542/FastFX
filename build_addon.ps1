param(
    [string]$OutputPath = (Join-Path $PSScriptRoot 'dist\fastfx.zip')
)

$addonDirectory = Join-Path $PSScriptRoot 'fastfx'

if (-not (Test-Path -LiteralPath $addonDirectory -PathType Container)) {
    throw "FastFX add-on directory was not found: $addonDirectory"
}

$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Compress-Archive -Path $addonDirectory -DestinationPath $OutputPath -Force
Write-Host "Built Blender add-on ZIP: $OutputPath"
