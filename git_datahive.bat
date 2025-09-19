@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ===============================================
REM Datahive — Git Helper
REM Usage:
REM   git_datahive.bat init       -> Primeiro push (bootstrap)
REM   git_datahive.bat update     -> Atualização diária (pull --rebase, commit, push)
REM   git_datahive.bat branch XYZ -> Cria branch 'XYZ' e faz push upstream
REM ===============================================

REM ---- Configurações padrão (edite se desejar) ----
set "REMOTE_URL=https://github.com/DanielDelfim/datahive.git"
set "MAIN_BRANCH=main"
set "GIT_USERNAME=DanielDelfim"
set "GIT_EMAIL=dmdelfim@gmail.com"

REM ---- Funções auxiliares ----
:check_git
git --version >NUL 2>&1
if errorlevel 1 (
  echo [ERRO] Git nao encontrado no PATH. Instale o Git e tente novamente.
  exit /b 1
)
exit /b 0

:ensure_repo
if not exist ".git" (
  echo [INFO] Repositorio Git nao inicializado. Executando 'git init'...
  git init || (echo [ERRO] Falha ao inicializar repositório. & exit /b 1)
) else (
  echo [OK] Repositorio Git detectado.
)
exit /b 0

:ensure_main_branch
for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD 2^>NUL') do set "CUR_BRANCH=%%b"
if not defined CUR_BRANCH set "CUR_BRANCH="
if /I "!CUR_BRANCH!"=="!MAIN_BRANCH!" (
  echo [OK] Branch atual: !CUR_BRANCH!
) else (
  echo [INFO] Definindo branch principal como !MAIN_BRANCH! ...
  git branch -M "!MAIN_BRANCH!" 2>NUL
)
exit /b 0

:ensure_remote
for /f "tokens=*" %%r in ('git remote 2^>NUL') do set "HAS_REMOTE=%%r"
if not defined HAS_REMOTE (
  echo [INFO] Adicionando remoto 'origin' -> !REMOTE_URL!
  git remote add origin "!REMOTE_URL!" || (echo [ERRO] Falha ao adicionar remoto. & exit /b 1)
) else (
  echo [OK] Remoto 'origin' detectado.
)
exit /b 0

:ensure_basics
if not exist ".gitignore" (
  echo [INFO] Criando .gitignore padrao...
  (
    echo __pycache__/
    echo *.py[cod]
    echo .venv/
    echo .idea/
    echo .vscode/
    echo .pytest_cache/
    echo .mypy_cache/
    echo .DS_Store
    echo Thumbs.db
    echo .streamlit/secrets.toml
    echo .streamlit/.secrets/
    echo tokens/
    echo **/tokens/
    echo .env
    echo .env.*
    echo *.env
    echo data/
    echo **/raw/
    echo **/pp/
    echo **/backup/
    echo logs/
    echo *.log
  ) > .gitignore
)

if not exist "README.md" (
  echo [INFO] Criando README.md vazio...
  echo # Datahive> README.md
)

if not exist "LICENSE" (
  echo [INFO] Criando LICENSE (MIT) padrao...
  (
    echo MIT License
    echo.
    echo Copyright ^(c^) 2025 Daniel M. Delfim
    echo.
    echo Permission is hereby granted, free of charge, to any person obtaining a copy
    echo of this software and associated documentation files ^(the "Software"^), to deal
    echo in the Software without restriction, including without limitation the rights
    echo to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    echo copies of the Software, and to permit persons to whom the Software is
    echo furnished to do so, subject to the following conditions:
    echo.
    echo The above copyright notice and this permission notice shall be included in all
    echo copies or substantial portions of the Software.
    echo.
    echo THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    echo IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    echo FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    echo AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    echo LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    echo OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    echo SOFTWARE.
  ) > LICENSE
)
exit /b 0

:config_user
REM Configura usuario global (edite as variaveis no topo se quiser usar aqui)
git config --global user.name "%GIT_USERNAME%"
git config --global user.email "%GIT_EMAIL%"
echo [OK] git config global atualizado: %GIT_USERNAME% ^<%GIT_EMAIL%^>
exit /b 0

:do_init
call :check_git || exit /b 1
call :ensure_repo || exit /b 1
call :ensure_main_branch || exit /b 1
call :ensure_remote || exit /b 1
call :ensure_basics || exit /b 1

echo [INFO] Adicionando arquivos...
git add . || (echo [ERRO] git add falhou. & exit /b 1)

echo [INFO] Primeiro commit...
git commit -m "chore: bootstrap do projeto Datahive" || (
  echo [WARN] Talvez nao haja mudancas para commit. Prosseguindo...
)

echo [INFO] Enviando para GitHub (origin %MAIN_BRANCH%)...
git push -u origin "%MAIN_BRANCH%"
if errorlevel 1 (
  echo [ERRO] Falha no push. Verifique suas credenciais ou permissao no repo.
  exit /b 1
)
echo [OK] Primeiro push concluido.
exit /b 0

:do_update
call :check_git || exit /b 1
call :ensure_repo || exit /b 1
call :ensure_main_branch || exit /b 1
call :ensure_remote || exit /b 1

echo [INFO] Atualizando do remoto com rebase...
git pull --rebase origin "%MAIN_BRANCH%" || (
  echo [ERRO] git pull --rebase falhou. Resolva conflitos e tente novamente.
  exit /b 1
)

echo [INFO] Adicionando alteracoes...
git add -A || (echo [ERRO] git add -A falhou. & exit /b 1)

set "MSG=%*"
if "%MSG%"=="" set "MSG=chore: atualizacao cotidiana"

REM Remove a primeira palavra (update) da mensagem, se veio dos args
for /f "tokens=1,* delims= " %%a in ("%MSG%") do (
  if /I "%%a"=="update" (set "MSG=%%b")
)

if "%MSG%"=="" set "MSG=chore: atualizacao cotidiana"

echo [INFO] Commitando: %MSG%
git commit -m "%MSG%"
if errorlevel 1 (
  echo [WARN] Nada para commitar ^(working tree clean^). Prosseguindo...
)

echo [INFO] Enviando para GitHub...
git push origin "%MAIN_BRANCH%" || (
  echo [ERRO] git push falhou. Verifique o remoto/permissoes.
  exit /b 1
)

echo [OK] Atualizacao concluida.
exit /b 0

:do_branch
set "NEWBR=%~2"
if "%NEWBR%"=="" (
  echo [ERRO] Informe o nome do branch. Ex.: git_datahive.bat branch feat/reposicao-60d
  exit /b 1
)

call :check_git || exit /b 1
call :ensure_repo || exit /b 1

echo [INFO] Criando e mudando para branch %NEWBR% ...
git checkout -b "%NEWBR%" || (
  echo [ERRO] Falha ao criar branch.
  exit /b 1
)

echo [INFO] Fazendo push upstream...
git push -u origin "%NEWBR%" || (
  echo [ERRO] Falha no push do novo branch.
  exit /b 1
)

echo [OK] Branch '%NEWBR%' criado e publicado.
exit /b 0

REM ---- Dispatcher ----
if /I "%~1"=="init"    goto do_init
if /I "%~1"=="update"  goto do_update
if /I "%~1"=="branch"  goto do_branch

echo.
echo Datahive — Git Helper
echo Uso:
echo   %~nx0 init
echo   %~nx0 update  [mensagem de commit opcional]
echo   %~nx0 branch  NOME_DO_BRANCH
echo.
echo Exemplo:
echo   %~nx0 init
echo   %~nx0 update "feat: modulo de reposicao 60d"
echo   %~nx0 branch feat/reposicao-60d
echo.
exit /b 0
