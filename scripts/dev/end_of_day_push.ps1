<# ======================================================================
 scripts/dev/end_of_day_push.ps1
  → Commit + push de fim de dia, seguro e amigável

 Uso:
   .\scripts\dev\end_of_day_push.ps1
   .\scripts\dev\end_of_day_push.ps1 -Message "ajustes Amazon"
   .\scripts\dev\end_of_day_push.ps1 -NoPush:$true
   .\scripts\dev\end_of_day_push.ps1 -StashFirst:$true

 Parâmetros:
   -Message    : Mensagem extra do commit
   -NoPush     : Se true, não faz push (só commit)
   -StashFirst : Se true, cria um stash (inclui untracked) antes do commit
====================================================================== #>

param(
  [string]$Message = "",
  [bool]$NoPush = $false,
  [bool]$StashFirst = $false
)

function Fail($msg) { Write-Host "ERRO: $msg" -ForegroundColor Red; exit 1 }

# 0) Verifica se é repo git e vai pra raiz
try { $gitTop = (git rev-parse --show-toplevel) 2>$null } catch { $gitTop = $null }
if (-not $gitTop) { Fail "Este diretório não é um repositório Git. Abra o terminal em C:\Apps\Datahive." }
Set-Location $gitTop

# 1) Mostra remoto/branch/status
Write-Host "== Repositório ==" -ForegroundColor Cyan
git remote -v
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -eq "HEAD") { Fail "Você está em 'detached HEAD'. Faça 'git switch <branch>' antes." }
Write-Host ("Branch atual: {0}" -f $branch) -ForegroundColor Yellow
git --no-pager status -s

# 2) Stash de segurança (opcional)
if ($StashFirst) {
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $stashMsg = "eod_auto_backup_$stamp"
  git stash push -u -m $stashMsg | Out-Null
  Write-Host "Stash criado: $stashMsg" -ForegroundColor DarkYellow
}

# 3) Stage de tudo que não está ignorado
git add -A

# 4) Se não há nada staged, informa e segue para push (se houver)
$staged = (git diff --cached --name-only)
if (-not $staged) {
  Write-Host "Nada novo para commitar (index vazio)." -ForegroundColor DarkYellow
} else {
  # 5) Commit com cabeçalho EOD
  $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
  $hostName = $env:COMPUTERNAME
  $user = $env:UserName
  $header = "chore: EOD sync ($ts) [$hostName\$user]"
  $finalMsg = ($Message.Trim()) ? "$header — $Message" : $header
  git commit -m $finalMsg | Out-Null
  Write-Host "Commit criado: $finalMsg" -ForegroundColor Green
}

# 6) Push (a menos que -NoPush)
if ($NoPush) {
  Write-Host "NoPush=true — commit feito (se havia mudanças), sem push." -ForegroundColor DarkYellow
} else {
  # Aviso se estiver na main
  if ($branch -eq "main") {
    Write-Host "ATENÇÃO: você está na 'main'. Deseja mesmo fazer PUSH nela? (Y/N)" -ForegroundColor Yellow
    $ans = Read-Host
    if ($ans -notin @('Y','y','S','s')) {
      Write-Host "Push cancelado pelo usuário." -ForegroundColor DarkYellow
      exit 0
    }
  }

  # Verifica upstream
  $hasUpstream = $true
  try { git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null | Out-Null } catch { $hasUpstream = $false }

  if (-not $hasUpstream) {
    Write-Host "Upstream ausente. Definindo upstream para origin/$branch ..." -ForegroundColor DarkYellow
    git push -u origin $branch
  } else {
    git push
  }
  Write-Host "Push concluído." -ForegroundColor Green
}

# 7) Dica de PR quando não for main
$remoteUrl = (git remote get-url origin) 2>$null
if ($remoteUrl) {
  $remoteUrl = $remoteUrl.Replace(".git","")
  if ($branch -ne "main" -and -not $NoPush) {
    $prUrl = "$remoteUrl/compare/main...$branch?expand=1"
    Write-Host "Abra um Pull Request para unificar com a main:" -ForegroundColor Cyan
    Write-Host "→ $prUrl" -ForegroundColor Cyan
  }
}

# 8) Resumo
Write-Host "`n== Último commit ==" -ForegroundColor Cyan
git --no-pager log -1 --pretty=format:"%C(yellow)%h%Creset %Cgreen%ad%Creset %s" --date=iso
Write-Host ""
