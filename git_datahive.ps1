param(
    [Parameter(Position=0)]
    [ValidateSet('init','update','branch')]
    [string]$Command = 'update',
    [Parameter(Position=1)]
    [string]$Arg
)

$ErrorActionPreference = 'Stop'

# ---------- Config ----------
$REMOTE_URL  = 'https://github.com/DanielDelfim/datahive.git'
$MAIN_BRANCH = 'main'
$GIT_USERNAME = 'Daniel M. Delfim'
$GIT_EMAIL    = 'seu-email@exemplo.com'

function Test-Git {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Git não encontrado no PATH.'
    }
}

function Initialize-Repo {
    if (-not (Test-Path '.git')) {
        Write-Host '[INFO] Repositório Git não inicializado. Executando git init ...'
        git init | Out-Null
    } else {
        Write-Host '[OK] Repositório Git detectado.'
    }
}

function Set-MainBranch {
    $cur = (git rev-parse --abbrev-ref HEAD 2>$null)
    if ($null -ne $cur) { $cur = $cur.Trim() } else { $cur = '' }
    if ($cur -ne $MAIN_BRANCH -and $cur -ne '') {
        Write-Host "[INFO] Definindo branch principal como $MAIN_BRANCH ..."
        git branch -M $MAIN_BRANCH | Out-Null
    } else {
        Write-Host "[OK] Branch atual: $MAIN_BRANCH"
    }
}

function Set-Remote {
    $remotes = (git remote 2>$null)
    if ($null -eq $remotes -or $remotes.Count -eq 0) {
        Write-Host "[INFO] Adicionando remoto 'origin' -> $REMOTE_URL"
        git remote add origin $REMOTE_URL | Out-Null
    } else {
        Write-Host "[OK] Remoto 'origin' detectado."
    }
}

function Set-Basics {
    if (-not (Test-Path '.gitignore')) {
        Write-Host '[INFO] Criando .gitignore básico...'
@'
__pycache__/
*.py[cod]
.venv/
.idea/
.vscode/
.pytest_cache/
.mypy_cache/
.DS_Store
Thumbs.db
.streamlit/secrets.toml
.streamlit/.secrets/
tokens/
**/tokens/
.env
.env.*
*.env
data/
**/raw/
**/pp/
**/backup/
logs/
*.log
'@ | Out-File -Encoding utf8 -FilePath .gitignore -Force
    }
    if (-not (Test-Path 'README.md')) {
        '# Datahive' | Out-File -Encoding utf8 -FilePath README.md -Force
    }
    if (-not (Test-Path 'LICENSE')) {
@'
MIT License

Copyright (c) 2025 Daniel M. Delfim

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'@ | Out-File -Encoding utf8 -FilePath LICENSE -Force
    }
}

function Set-GitUser {
    git config --global user.name  "$GIT_USERNAME"
    git config --global user.email "$GIT_EMAIL"
    Write-Host "[OK] git config global atualizado para $GIT_USERNAME <$GIT_EMAIL>"
}

function Start-Init {
    Test-Git
    Initialize-Repo
    Set-MainBranch
    Set-Remote
    Set-Basics
    Set-GitUser

    Write-Host '[INFO] Adicionando arquivos...'
    git add .

    Write-Host '[INFO] Primeiro commit...'
    git commit -m 'chore: bootstrap do projeto Datahive'
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[WARN] Nada para commitar (working tree clean).'
    }

    Write-Host "[INFO] Enviando para GitHub (origin $MAIN_BRANCH)..."
    git push -u origin $MAIN_BRANCH
    if ($LASTEXITCODE -ne 0) {
        throw 'Falha no push. Verifique credenciais/permissões no repositório.'
    }
    Write-Host '[OK] Primeiro push concluído.'
}

function Update-Repo {
    Test-Git
    Ensure-Repo
    Set-MainBranch
    Ensure-Remote

    Write-Host '[INFO] git pull --rebase ...'
    git pull --rebase origin $MAIN_BRANCH
    if ($LASTEXITCODE -ne 0) { throw 'git pull --rebase falhou. Resolva conflitos e tente novamente.' }

    Write-Host '[INFO] Adicionando alterações...'
    git add -A
    if ($LASTEXITCODE -ne 0) { throw 'git add -A falhou.' }

    $msg = if ($Arg) { $Arg } else { 'chore: atualização cotidiana' }
    Write-Host "[INFO] Commitando: $msg"
    git commit -m "$msg"
    if ($LASTEXITCODE -ne 0) {
        Write-Host '[WARN] Nada para commitar.'
    }

    Write-Host '[INFO] Fazendo push...'
    git push origin $MAIN_BRANCH
    if ($LASTEXITCODE -ne 0) { throw 'git push falhou.' }

    Write-Host '[OK] Atualização concluída.'
}

function New-Branch {
    if (-not $Arg) { throw "Informe o nome do branch. Ex.: .\git_datahive.ps1 branch feat/reposicao-60d" }
    Test-Git
    Ensure-Repo

    Write-Host "[INFO] Criando e mudando para branch $Arg ..."
    git checkout -b $Arg
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar branch.' }

    Write-Host '[INFO] Publicando branch...'
    git push -u origin $Arg
    if ($LASTEXITCODE -ne 0) { throw 'Falha no push do novo branch.' }

    Write-Host "[OK] Branch '$Arg' criado e publicado."
}

switch ($Command) {
    'init'   { Start-Init }
    'update' { Update-Repo }
    'branch' { New-Branch }
}
