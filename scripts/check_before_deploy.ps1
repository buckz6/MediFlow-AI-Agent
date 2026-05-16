# MediFlow - Pre-Deploy Checklist
# Jalankan: powershell -ExecutionPolicy Bypass -File scripts\check_before_deploy.ps1

$ErrorActionPreference = "Stop"
$pass = 0
$fail = 0

function Check($label, $ok, $msg) {
    if ($ok) {
        Write-Host "  [OK] $label" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  [!!] $label" -ForegroundColor Red
        if ($msg) { Write-Host "       $msg" -ForegroundColor DarkGray }
        $script:fail++
    }
}

function Section($title) {
    Write-Host ""
    Write-Host "── $title " -ForegroundColor Cyan
}

function Read-Env($path) {
    $vars = @{}
    if (-not (Test-Path $path)) { return $vars }
    foreach ($line in Get-Content $path) {
        $line = $line.Trim()
        if ($line -match "^#" -or $line -eq "") { continue }
        $idx = $line.IndexOf("=")
        if ($idx -lt 0) { continue }
        $k = $line.Substring(0, $idx).Trim()
        $v = $line.Substring($idx + 1).Trim()
        $vars[$k] = $v
    }
    return $vars
}

$placeholders = @(
    "your_gemini_api_key_here",
    "your_speechmatics_api_key_here",
    "your_fernet_encryption_key_here",
    "your-domain.com",
    "your_domain_here",
    "<your_gemini_api_key>",
    "<your_speechmatics_api_key>",
    "<your_fernet_key>",
    ""
)

function Is-Placeholder($val) {
    if ($null -eq $val) { return $true }
    return $placeholders -contains $val.Trim()
}

# ─────────────────────────────────────────────
Write-Host ""
Write-Host "  MediFlow - Pre-Deployment Checklist" -ForegroundColor White
Write-Host "  =====================================" -ForegroundColor White

# ── 1. Root .env ──────────────────────────────
Section "1. Root .env"

$envExists = Test-Path ".env"
Check ".env file ada" $envExists "Buat dulu: copy .env.example .env"

if ($envExists) {
    $env = Read-Env ".env"

    $keys = @("GEMINI_API_KEY", "SPEECHMATICS_API_KEY", "MEDIFLOW_ENCRYPTION_KEY", "DOMAIN", "ACME_EMAIL")
    foreach ($k in $keys) {
        $v = $env[$k]
        $ok = (-not (Is-Placeholder $v))
        $hint = "Isi nilai untuk $k di file .env"
        if ($k -eq "ACME_EMAIL" -and $ok) {
            $ok = $v.Contains("@")
            $hint = "ACME_EMAIL harus mengandung karakter @"
        }
        Check "$k diisi" $ok $hint
    }

    $notTracked = $true
    if (Test-Path ".gitignore") {
        $gi = Get-Content ".gitignore" -Raw
        $notTracked = $gi -match "\.env"
    }
    Check ".env ada di .gitignore" $notTracked "Tambahkan .env ke .gitignore agar tidak ter-commit"
}

# ── 2. backend/.env ───────────────────────────
Section "2. backend/.env"

$backendEnvExists = Test-Path "backend\.env"
Check "backend\.env ada" $backendEnvExists "Buat: copy backend\.env.example backend\.env"

if ($backendEnvExists) {
    $benv = Read-Env "backend\.env"
    foreach ($k in @("GEMINI_API_KEY", "SPEECHMATICS_API_KEY", "MEDIFLOW_ENCRYPTION_KEY")) {
        $ok = (-not (Is-Placeholder $benv[$k]))
        Check "$k diisi (backend)" $ok "Isi $k di backend\.env"
    }
}

# ── 3. Model weights ──────────────────────────
Section "3. Model Weights"

$weightsPath = "backend\models\weights\efficientnet_tb.pth"
Check "efficientnet_tb.pth ada" (Test-Path $weightsPath) "Jalankan: python backend\models\run_training.py"

$infoPath = "backend\models\weights\model_info.json"
Check "model_info.json ada" (Test-Path $infoPath) "File ini dibuat otomatis setelah training selesai"

if (Test-Path $infoPath) {
    try {
        $info = Get-Content $infoPath -Raw | ConvertFrom-Json
        $acc = [double]$info.val_accuracy
        if ($acc -le 1.0) { $acc = $acc * 100 }
        $ok = $acc -ge 85
        Check "val_accuracy >= 85% (actual: $([math]::Round($acc,1))%)" $ok "Akurasi terlalu rendah, pertimbangkan training ulang"
    } catch {
        Check "model_info.json bisa dibaca" $false "File JSON tidak valid"
    }
}

# ── 4. Docker files ───────────────────────────
Section "4. Docker dan Config Files"

$files = @(
    @{ path = "docker-compose.yml";    label = "docker-compose.yml" },
    @{ path = "backend\Dockerfile";    label = "backend\Dockerfile" },
    @{ path = "frontend\Dockerfile";   label = "frontend\Dockerfile" },
    @{ path = "nginx\nginx.conf";      label = "nginx\nginx.conf" }
)

foreach ($f in $files) {
    Check $f.label (Test-Path $f.path) "File tidak ditemukan: $($f.path)"
}

# ── 5. GitHub ─────────────────────────────────
Section "5. GitHub Repository"

$gitExists = Test-Path ".git"
Check "Git repository ada" $gitExists "Jalankan: git init"

if ($gitExists) {
    try {
        $remote = git remote get-url origin 2>$null
        $ok = ($null -ne $remote -and $remote -ne "")
        Check "Remote origin ada ($remote)" $ok "Jalankan: git remote add origin https://github.com/username/mediflow"
    } catch {
        Check "Remote origin ada" $false "Jalankan: git remote add origin https://github.com/username/mediflow"
    }
}

# ── Summary ───────────────────────────────────
Write-Host ""
Write-Host "  =====================================" -ForegroundColor White
$total = $pass + $fail

if ($fail -eq 0) {
    Write-Host "  SEMUA $total CHECKS PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Langkah selanjutnya:" -ForegroundColor White
    Write-Host "  1. git add . && git commit -m 'feat: complete MediFlow'" -ForegroundColor DarkGray
    Write-Host "  2. git push origin main" -ForegroundColor DarkGray
    Write-Host "  3. Di Vultr VM: docker-compose up --build -d" -ForegroundColor DarkGray
    Write-Host ""
    exit 0
} else {
    Write-Host "  $pass/$total passed  |  $fail perlu diperbaiki" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Perbaiki semua item [!!] di atas sebelum deploy." -ForegroundColor Red
    Write-Host ""
    exit 1
}