@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

rem ====== SEMPRE ENTRAR NA PASTA DO PROJETO ======
cd /d C:\Apps\Datahive

rem ====== CONFIG ======
set "REMOTE_URL=https://github.com/DanielDelfim/datahive.git"
set "MAIN_BRANCH=main"

rem ====== DISPATCHER ======
if /I "%~1"=="init"   goto do_init
if /I "%~1"=="update" goto do_update
if /I "%~1"=="branch" goto do_branch
echo.
echo Datahive — Git Helper
echo Uso (pode chamar via 2 cliques e passar argumentos depois):
echo   %~nx0 init
echo   %~nx0 update  [mensagem de commit opcional]
echo   %~nx0 branch  NOME_DO_BRANCH
echo.
goto end

rem ====== HELPERS ======
:die
set "ERR=%~1"
if not defined ERR set "ERR=erro desconhecido"
echo [ERRO] %ERR%
goto end

:ensure_git
git --version >nul 2>&1 || (call :die "Git nao encontrado no PATH." & goto :eof)
goto :eof

:ensure_repo
if not exist ".git" (
  echo [INFO] git init ...
  git init || (call :die "Falha ao inicializar repo." & goto :eof)
)
goto :eof

:ensure_main
git branch -M "%MAIN_BRANCH%" 2>nul
goto :eof

:ensure_origin
git remote get-url origin >nul 2>&1 || git remote add origin "%REMOTE_URL%" || (call :die "Falha ao adicionar origin." & goto :eof)
goto :eof

:ensure_basics
if not exist ".gitignore" (
  echo [INFO] criando .gitignore ...
  > .gitignore (
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
  )
)
if not exist ".gitattributes" (
  echo [INFO] criando .gitattributes ...
  > .gitattributes (
    echo * text=auto
    echo *.bat  text eol=crlf
    echo *.cmd  text eol=crlf
    echo *.ps1  text eol=crlf
    echo *.sh   text eol=lf
    echo *.py   text eol=lf
    echo *.md   text eol=lf
    echo *.json text eol=lf
    echo *.yml  text eol=lf
    echo *.yaml text eol=lf
    echo *.png  -text
    echo *.jpg  -text
    echo *.jpeg -text
    echo *.gif  -text
    echo *.pdf  -text
    echo *.zip  -text
    echo *.exe  -text
  )
)
git add --renormalize . >nul 2>&1
goto :eof

rem ====== INIT ======
:do_init
call :ensure_git
call :ensure_repo
call :ensure_main
call :ensure_origin
call :ensure_basics

echo [INFO] commit inicial (ok se nao houver mudancas)
git add .
git commit -m "chore: bootstrap do projeto Datahive"
if errorlevel 1 echo [WARN] Nada para commitar.

echo [INFO] push origin %MAIN_BRANCH%
git push -u origin "%MAIN_BRANCH%" || (call :die "push falhou (credenciais/permissao?)" & goto end)
echo [OK] init concluido.
goto end

rem ====== UPDATE ======
:do_update
call :ensure_git
call :ensure_repo
call :ensure_main
call :ensure_origin

echo [INFO] pull --rebase
git pull --rebase origin "%MAIN_BRANCH%" || (call :die "pull --rebase falhou (conflitos?)" & goto end)

echo [INFO] add/commit/push
git add -A || (call :die "git add -A falhou." & goto end)

set "MSG=%*"
if not defined MSG set "MSG=chore: atualizacao cotidiana"
for /f "tokens=1,* delims= " %%a in ("%MSG%") do (
  if /I "%%~a"=="update" (set "MSG=%%~b")
)

git commit -m "%MSG%"
if errorlevel 1 echo [WARN] Nada para commitar.
git push origin "%MAIN_BRANCH%" || (call :die "git push falhou." & goto end)
echo [OK] update concluido.
goto end

rem ====== BRANCH ======
:do_branch
set "NEWBR=%~2"
if not defined NEWBR (call :die "Informe o nome do branch. Ex.: %~nx0 branch feat/reposicao-60d" & goto end)

call :ensure_git
call :ensure_repo

git checkout -b "%NEWBR%" || (call :die "Falha ao criar branch." & goto end)
git push -u origin "%NEWBR%" || (call :die "Falha no push do novo branch." & goto end)
echo [OK] Branch '%NEWBR%' criado e publicado.
goto end

:end
echo.
echo [INFO] Script finalizado. Pressione qualquer tecla para sair.
pause >nul
endlocal
