Param(
  [int]$Count = 8,
  [string]$Repos = "FROWNINGdev/FROWNINGdev",
  [switch]$AutoMerge
)

# Load GH_TOKEN from .env
if (Test-Path -LiteralPath ".env") {
  $env:GH_TOKEN = (Get-Content .env | ForEach-Object {
    if ($_ -match '^GH_TOKEN=(.+)$') { $Matches[1] }
  })
}

if (-not $env:GH_TOKEN) {
  Write-Error "GH_TOKEN не найден. Добавьте GH_TOKEN=... в файл .env"
  exit 1
}

$auto = ""
if ($AutoMerge) { $auto = "--auto-merge" }

for ($i = 1; $i -le $Count; $i++) {
  Write-Host "[" $i "/" $Count "] Создаю PR..."
  python scripts/auto_contribution.py --repos $Repos $auto
  Start-Sleep -Seconds 3
}

Write-Host "Готово. Проверьте бейдж Pull Shark через несколько минут/часов."


