# Памятка: PowerShell, Nekobox и Codex

Дата: 2026-03-22

## Что настраиваем

Эта памятка нужна, чтобы с нуля настроить:

- Nekobox как локальный прокси на `127.0.0.1:2080`
- proxy-переменные в Windows и PowerShell
- удобные команды `proxy-on`, `proxy-off`, `proxy-status`, `ip`
- Codex через тот же прокси
- проверку: запрос идёт через прокси или напрямую

Ниже описан основной вариант для HTTP-прокси. Если у тебя на этом порту только SOCKS5, смотри отдельный раздел в конце.

## Быстрый результат

После настройки у тебя будет такой сценарий работы:

1. Открываешь PowerShell.
2. Проверяешь `proxy-status`.
3. При необходимости включаешь `proxy-on` или выключаешь `proxy-off`.
4. Проверяешь внешний IP командой `ip`.
5. Codex и shell используют тот же прокси.

## Шаг 1. Убедиться, что Nekobox запущен

Перед настройкой Nekobox должен уже работать и слушать локальный прокси на:

`127.0.0.1:2080`

В этой инструкции используется именно HTTP-прокси на этом адресе.

## Шаг 2. Записать постоянные proxy-переменные Windows

Эти команды создают пользовательские переменные окружения. Новые окна PowerShell и многие CLI-программы будут использовать прокси автоматически.

```powershell
setx HTTP_PROXY  http://127.0.0.1:2080
setx HTTPS_PROXY http://127.0.0.1:2080
setx ALL_PROXY   http://127.0.0.1:2080
setx NO_PROXY    localhost,127.0.0.1,::1
```

Что означает каждая переменная:

- `HTTP_PROXY` и `HTTPS_PROXY` задают прокси для HTTP и HTTPS
- `ALL_PROXY` нужен для программ, которые используют только его
- `NO_PROXY` перечисляет адреса, которые не надо пускать через прокси

Обычно эти переменные начинают действовать в новых окнах PowerShell.

## Шаг 3. Проверить текущие proxy-переменные

Открой новый PowerShell и выполни:

```powershell
Get-ChildItem Env: | Where-Object Name -match 'PROXY'
```

Или коротко:

```powershell
echo "HTTP_PROXY=$env:HTTP_PROXY"
echo "HTTPS_PROXY=$env:HTTPS_PROXY"
echo "ALL_PROXY=$env:ALL_PROXY"
echo "NO_PROXY=$env:NO_PROXY"
```

Ожидаемый результат:

```text
HTTP_PROXY=http://127.0.0.1:2080
HTTPS_PROXY=http://127.0.0.1:2080
ALL_PROXY=http://127.0.0.1:2080
NO_PROXY=localhost,127.0.0.1,::1
```

## Шаг 4. Настроить PowerShell profile

Проверить путь активного профиля:

```powershell
$PROFILE
```

Проверить, существует ли он:

```powershell
Test-Path $PROFILE
```

Если профиля нет, создай его:

```powershell
New-Item -ItemType Directory -Force (Split-Path $PROFILE)
New-Item -ItemType File -Force $PROFILE
```

В твоём случае PowerShell использует профиль в OneDrive:

`C:\Users\ealos\OneDrive\Документы\PowerShell\Microsoft.PowerShell_profile.ps1`

Это важно: править нужно именно путь из `$PROFILE`, а не просто папку `Documents` наугад.

## Шаг 5. Добавить удобные команды в PowerShell profile

Добавь в профиль такой блок:

```powershell
function Set-ProxyOn {
    $proxy = 'http://127.0.0.1:2080'
    $noProxy = 'localhost,127.0.0.1,::1'
    $env:HTTP_PROXY = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:ALL_PROXY = $proxy
    $env:NO_PROXY = $noProxy
    Write-Host "Proxy enabled: $proxy"
}

function Set-ProxyOff {
    Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:NO_PROXY -ErrorAction SilentlyContinue
    Write-Host 'Proxy disabled for current shell'
}

function Show-ProxyStatus {
    Write-Host "HTTP_PROXY=$env:HTTP_PROXY"
    Write-Host "HTTPS_PROXY=$env:HTTPS_PROXY"
    Write-Host "ALL_PROXY=$env:ALL_PROXY"
    Write-Host "NO_PROXY=$env:NO_PROXY"
}

function Show-ExternalIp {
    curl.exe -s https://api.ipify.org
    Write-Host ""
}

Set-Alias proxy-on Set-ProxyOn
Set-Alias proxy-off Set-ProxyOff
Set-Alias proxy-status Show-ProxyStatus
Set-Alias ip Show-ExternalIp
```

Что дают эти команды:

- `proxy-on` включает прокси в текущем shell
- `proxy-off` выключает прокси в текущем shell
- `proxy-status` показывает текущие proxy-переменные
- `ip` показывает внешний IP


### Как добавить это в профиль вручную или почти автоматически

Редактор не обязателен. Профиль можно править прямо из PowerShell.

Открыть профиль вручную в Блокноте:

`powershell
notepad $PROFILE
`

Если файла ещё нет:

`powershell
New-Item -ItemType Directory -Force (Split-Path $PROFILE)
New-Item -ItemType File -Force $PROFILE
notepad $PROFILE
`

Если нужно не открывать редактор, а просто дописать блок в профиль прямо из PowerShell:

`powershell
@'
function Set-ProxyOn {
    $proxy = 'http://127.0.0.1:2080'
    $noProxy = 'localhost,127.0.0.1,::1'
    $env:HTTP_PROXY = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:ALL_PROXY = $proxy
    $env:NO_PROXY = $noProxy
    Write-Host "Proxy enabled: $proxy"
}

function Set-ProxyOff {
    Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
    Remove-Item Env:NO_PROXY -ErrorAction SilentlyContinue
    Write-Host 'Proxy disabled for current shell'
}

function Show-ProxyStatus {
    Write-Host "HTTP_PROXY=$env:HTTP_PROXY"
    Write-Host "HTTPS_PROXY=$env:HTTPS_PROXY"
    Write-Host "ALL_PROXY=$env:ALL_PROXY"
    Write-Host "NO_PROXY=$env:NO_PROXY"
}

function Show-ExternalIp {
    curl.exe -s https://api.ipify.org
    Write-Host ""
}

Set-Alias proxy-on Set-ProxyOn
Set-Alias proxy-off Set-ProxyOff
Set-Alias proxy-status Show-ProxyStatus
Set-Alias ip Show-ExternalIp
'@ | Add-Content $PROFILE
`

Это не создаёт никаких отдельных профилей. Команда просто дописывает блок в тот профиль, путь к которому сейчас лежит в $PROFILE.

Если нужно полностью заменить содержимое профиля, а не дописать его в конец, используй Set-Content вместо Add-Content.


### Редактирование профиля через Notepad++

Если у тебя установлен Notepad++, профиль PowerShell можно открывать через него.

Открыть профиль по полному пути к программе:

```powershell
& "C:\Program Files\Notepad++\notepad++.exe" $PROFILE
```

Если Notepad++ уже прописан в `PATH`, можно короче:

```powershell
notepad++ $PROFILE
```

Чтобы добавить Notepad++ в пользовательский `PATH`:

```powershell
[Environment]::SetEnvironmentVariable(
  'Path',
  $env:Path + ';C:\Program Files\Notepad++',
  'User'
)
```

Важно: текущее окно PowerShell после этого не обновит `PATH` автоматически. Есть два варианта:

- открыть новое окно PowerShell
- или временно обновить `PATH` в текущем окне:

```powershell
$env:Path += ';C:\Program Files\Notepad++'
```

Проверка:

```powershell
Get-Command notepad++
```

Если не хочется зависеть от `PATH`, можно добавить в профиль отдельную функцию:

```powershell
function psp {
    & "C:\Program Files\Notepad++\notepad++.exe" $PROFILE
}
```

После этого профиль можно открывать короткой командой:

```powershell
psp
```
## Шаг 6. Подгрузить профиль и проверить команды

Если профиль создан или изменён, подгрузи его вручную:

```powershell
. $PROFILE
```

Проверка:

```powershell
Get-Command proxy-on
Get-Command proxy-off
Get-Command proxy-status
Get-Command ip
```

Если команды находятся, профиль работает.

## Шаг 7. Базовые команды для ежедневного использования

Включить прокси в текущем окне PowerShell:

```powershell
proxy-on
```

Выключить прокси в текущем окне:

```powershell
proxy-off
```

Посмотреть текущие значения:

```powershell
proxy-status
```

Посмотреть внешний IP:

```powershell
ip
```

Типовой короткий сценарий:

```powershell
proxy-status
proxy-off
proxy-status
proxy-on
proxy-status
ip
```

## Шаг 8. Проверить, идёт ли трафик через прокси

Самая удобная проверка:

```powershell
curl.exe -v https://api.ipify.org
```

Если в выводе есть строки вроде:

- `Uses proxy env variable`
- `Trying 127.0.0.1:2080`
- `Established connection to 127.0.0.1`

значит запрос действительно идёт через локальный прокси Nekobox.

Проверить только внешний IP:

```powershell
curl.exe -s https://api.ipify.org
```

Сравнить IP через прокси и напрямую:

```powershell
$oldHttp=$env:HTTP_PROXY
$oldHttps=$env:HTTPS_PROXY
$oldAll=$env:ALL_PROXY

$env:HTTP_PROXY=$null
$env:HTTPS_PROXY=$null
$env:ALL_PROXY=$null

curl.exe -s https://api.ipify.org

$env:HTTP_PROXY=$oldHttp
$env:HTTPS_PROXY=$oldHttps
$env:ALL_PROXY=$oldAll
```

Если IP отличаются, значит прокси точно используется.

## Шаг 9. Как временно обойти прокси

Одна команда без прокси:

```powershell
$env:HTTP_PROXY=$null
$env:HTTPS_PROXY=$null
$env:ALL_PROXY=$null
git clone https://example.com/repo.git
```

Вернуть прокси обратно:

```powershell
$env:HTTP_PROXY='http://127.0.0.1:2080'
$env:HTTPS_PROXY='http://127.0.0.1:2080'
$env:ALL_PROXY='http://127.0.0.1:2080'
```

Пустить один адрес мимо прокси:

```powershell
$env:NO_PROXY='localhost,127.0.0.1,example.com'
```

Это означает, что `example.com` будет открываться напрямую, а остальные адреса останутся через прокси.

## Шаг 10. Как убрать proxy-настройки

Очистить только текущее окно PowerShell:

```powershell
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:NO_PROXY -ErrorAction SilentlyContinue
```

Удалить постоянные пользовательские переменные Windows:

```powershell
[Environment]::SetEnvironmentVariable('HTTP_PROXY', $null, 'User')
[Environment]::SetEnvironmentVariable('HTTPS_PROXY', $null, 'User')
[Environment]::SetEnvironmentVariable('ALL_PROXY', $null, 'User')
[Environment]::SetEnvironmentVariable('NO_PROXY', $null, 'User')
```

## Шаг 11. Настроить Codex

Файл конфигурации Codex:

`C:\Users\ealos\.codex\config.toml`

Используемая конфигурация:

```toml
model = "gpt-5.4"
model_reasoning_effort = "high"
approvals_reviewer = "user"
sandbox_mode = "read-only"
approval_policy = "on-request"
personality = "pragmatic"
default_permissions = "corp_proxy"

[windows]
sandbox = "elevated"

[projects.'D:\QWEN']
trust_level = "trusted"

[projects.'\\?\D:\pyRevit\RaisedFloor.extension']
trust_level = "trusted"

[notice.model_migrations]
"gpt-5.3-codex" = "gpt-5.4"

[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]

[features]
multi_agent = true

[sandbox_workspace_write]
network_access = false

[permissions.corp_proxy.network]
enabled = true
mode = "full"
proxy_url = "http://127.0.0.1:2080"
allow_upstream_proxy = true

[shell_environment_policy]
inherit = "core"
set = { HTTP_PROXY = "http://127.0.0.1:2080", HTTPS_PROXY = "http://127.0.0.1:2080", ALL_PROXY = "http://127.0.0.1:2080", NO_PROXY = "localhost,127.0.0.1,::1" }
```

Что здесь важно:

- `default_permissions = "corp_proxy"` делает proxy-профиль профилем по умолчанию
- `[permissions.corp_proxy.network]` направляет subprocess traffic через Nekobox
- `[shell_environment_policy]` прокидывает proxy env в shell и tools

После изменения `config.toml` Codex нужно полностью перезапустить.

## Как понять, что Codex тоже работает через прокси

Практически это выглядит так:

- PowerShell видит proxy-переменные
- `curl.exe -v https://api.ipify.org` показывает подключение к `127.0.0.1:2080`
- Codex после перезапуска продолжает нормально работать с сетевыми действиями

## Вариант для SOCKS5

Если на `127.0.0.1:2080` у Nekobox только SOCKS5, а не HTTP-прокси, используй такой вариант.

В `config.toml`:

```toml
[permissions.corp_proxy.network]
enabled = true
mode = "full"
socks_url = "socks5://127.0.0.1:2080"
allow_upstream_proxy = true
```

Для Windows и PowerShell:

```powershell
setx HTTP_PROXY  socks5://127.0.0.1:2080
setx HTTPS_PROXY socks5://127.0.0.1:2080
setx ALL_PROXY   socks5://127.0.0.1:2080
```

И в функции `Set-ProxyOn` нужно заменить строку:

```powershell
$proxy = 'socks5://127.0.0.1:2080'
```

## Короткий чеклист

1. Запустить Nekobox.
2. Выполнить `setx` для `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`.
3. Проверить `$PROFILE`.
4. Создать PowerShell profile, если его нет.
5. Добавить функции и алиасы для прокси.
6. Выполнить `. $PROFILE`.
7. Проверить `proxy-status`, `ip`, `curl.exe -v https://api.ipify.org`.
8. Настроить `C:\Users\ealos\.codex\config.toml`.
9. Перезапустить Codex.

## Бэкап

Резервная копия конфига Codex:

`C:\Users\ealos\.codex\config.toml.bak-2026-03-22-nekobox`




