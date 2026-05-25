# CleanMyMac — Equivalentes em Shell Puro (macOS)

Guia completo de comandos shell equivalentes a todas as funcionalidades do CleanMyMac 5.

---

## 📋 Índice

1. [System Junk (Caches, Logs, Temp)](#system-junk)
2. [Trash Cleanup](#trash-cleanup)
3. [Privacy (Histórico, Cookies, Quarantine)](#privacy)
4. [Performance (LaunchAgents, RAM, DNS)](#performance)
5. [Maintenance (Mail, Spotlight, Disk)](#maintenance)
6. [App Uninstaller + Leftovers](#uninstaller)
7. [Storage & Duplicates](#storage)
8. [Safe Equivalents Chart](#chart)

---

## System Junk

### 1. User Caches (Chrome, Spotify, Browsers, Dev Tools)

```bash
# Limpar todos os caches do usuário
rm -rf ~/Library/Caches/*

# Limpar apenas caches específicos (mais seguro)
rm -rf ~/Library/Caches/Google/Chrome
rm -rf ~/Library/Caches/com.spotify.client
rm -rf ~/Library/Caches/Firefox
rm -rf ~/Library/Caches/Homebrew
rm -rf ~/Library/Caches/pip
rm -rf ~/Library/Caches/npm
rm -rf ~/Library/Caches/ms-playwright
rm -rf ~/Library/Caches/colima
rm -rf ~/Library/Caches/@granolaelectron-updater
```

### 2. System Caches (requer sudo)

```bash
# Caches do sistema
sudo rm -rf /Library/Caches/com.apple.iconservices.store
sudo rm -rf /Library/Caches/com.apple.amsengagementd.classicdatavault
sudo rm -rf /System/Library/Caches/com.apple.coresymbolicationd

# Caches de sessão em /var/folders (temp macOS)
TMPDIR=$(getconf DARWIN_USER_CACHE_DIR)
find "$TMPDIR" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} \; 2>/dev/null
```

### 3. User Logs

```bash
# Limpar logs de usuário
rm -rf ~/Library/Logs/*
rm -rf ~/Library/Logs/DiagnosticReports/*
rm -rf ~/Library/Logs/CrashReporter/*

# Limpar logs específicos
rm -rf ~/Library/Logs/Adobe/*
rm -rf ~/Library/Logs/ClickUp/*
rm -rf ~/Library/Logs/CreativeCloud/*
```

### 4. System Logs (requer sudo)

```bash
# Cuidado: pode afetar diagnóstico de sistema
sudo rm -rf /Library/Logs/CrashReporter/*
sudo rm -rf /Library/Logs/DiagnosticReports/*

# ASL logs (Apple System Logging)
sudo rm -rf /private/var/log/asl/*.asl
```

### 5. Application Support — Language Files Desnecessários

```bash
# Remove idiomas não utilizados (mantém pt-BR, en, Base)
KEEP="pt-BR.lproj|pt.lproj|en.lproj|Base.lproj"
find /Applications -name "*.lproj" -type d | grep -Ev "$KEEP" | xargs rm -rf

# Apenas listar sem deletar (preview)
find /Applications -name "*.lproj" -type d | grep -Ev "$KEEP"
```

### 6. Caches em Containers (Sandboxed Apps)

```bash
# Caches dentro de containers sandbox
rm -rf ~/Library/Containers/*/Data/Library/Caches/*

# Logs em containers
rm -rf ~/Library/Containers/*/Data/Library/Logs/*
```

### 7. Xcode Artifacts (para desenvolvedores)

```bash
# DerivedData (builds temporários)
rm -rf ~/Library/Developer/Xcode/DerivedData/*

# Archives (antigos)
rm -rf ~/Library/Developer/Xcode/Archives/*

# Module Caches
rm -rf ~/Library/Developer/Xcode/UserData/ModuleCache.noindex/*

# Device Support (simuladores antigos)
rm -rf ~/Library/Developer/Xcode/iOS\ DeviceSupport/*
rm -rf ~/Library/Developer/Xcode/macOS\ DeviceSupport/*

# CoreSimulator (simuladores iOS)
rm -rf ~/Library/Developer/CoreSimulator/Devices/*/

# Caches do simulator
rm -rf ~/Library/Developer/CoreSimulator/Caches/*
```

### 8. Mail & Messages

```bash
# Mail: Vacuum o banco de dados (otimiza)
sqlite3 ~/Library/Mail/V*/MailData/"Envelope Index" VACUUM

# Mail: Limpar lixeira
find ~/Library/Mail -path "*/Trash.mbox/*/Messages/*.emlx" -delete

# Messages: Cache de fotos
rm -rf ~/Library/Messages/Attachments/*
```

### 9. Downloads & Documents Antigos

```bash
# Arquivos .dmg não utilizados em Downloads
find ~/Downloads -name "*.dmg" -mtime +30 -delete  # +30 dias

# .zip e instaladores antigos
find ~/Downloads -name "*.zip" -mtime +30 -delete
find ~/Downloads -name "*.pkg" -mtime +30 -delete

# Arquivos ".crdownload" (downloads incompletos)
find ~/Downloads -name "*.crdownload" -delete
```

---

## Trash Cleanup

### 1. Esvaziar Lixeira do Usuário

```bash
# Remover tudo da lixeira
rm -rf ~/.Trash/*
rm -rf ~/.Trash/.DS_Store

# Com preservação de segurança (move para ~/.Trash_backup antes)
mkdir -p ~/.Trash_backup
mv ~/.Trash/* ~/.Trash_backup/ 2>/dev/null
rm -rf ~/.Trash_backup/*
```

### 2. Lixeira de Volumes Externos

```bash
# Limpar .Trashes em volumes montados
find /Volumes -name ".Trashes" -exec rm -rf {}/* \; 2>/dev/null
```

---

## Privacy

### 1. Quarantine Events (Safari, Chrome Downloads)

```bash
# Limpar eventos de quarentena (downloads marcados como unsafe)
rm ~/Library/Preferences/com.apple.LaunchServices.QuarantineEventsV2
# Ou via SQL (mais seguro):
sqlite3 ~/Library/Preferences/com.apple.LaunchServices.QuarantineEventsV2 \
  "DELETE FROM LSQuarantineEvent"
```

### 2. Safari — Histórico, Cookies, Dados

```bash
# Histórico de navegação
rm -rf ~/Library/Safari/History.db
rm -rf ~/Library/Safari/History.db-*

# Cookies
rm -rf ~/Library/Cookies/Cookies.binarycookies

# Downloads
rm -rf ~/Library/Safari/Downloads.plist

# Autofill
rm -rf ~/Library/Safari/AutoFill.plist

# Abas abertas
rm -rf ~/Library/Safari/LastSession.plist
```

### 3. Chrome — Histórico, Cookies, Senhas, Dados

```bash
# Chrome profile path (pode ter vários usuários)
CHROME_PROFILE=~/Library/Application\ Support/Google/Chrome

# Histórico
rm "$CHROME_PROFILE/Default/History"
rm "$CHROME_PROFILE/Default/History-journal"

# Cookies
rm "$CHROME_PROFILE/Default/Cookies"
rm "$CHROME_PROFILE/Default/Cookies-journal"

# Senhas salvas
rm "$CHROME_PROFILE/Default/Login Data"
rm "$CHROME_PROFILE/Default/Login Data-journal"

# IndexedDB (dados de sites)
rm -rf "$CHROME_PROFILE/Default/IndexedDB/*"

# Cache
rm -rf ~/Library/Caches/Google/Chrome
```

### 4. Firefox — Histórico, Cookies, Cache

```bash
# Firefox profile path
FIREFOX_PROFILE=~/Library/Application\ Support/Firefox/Profiles/*.default-release

# Histórico (SQLite)
sqlite3 "$FIREFOX_PROFILE/places.sqlite" "DELETE FROM moz_historyvisits"

# Cookies
rm "$FIREFOX_PROFILE/cookies.sqlite"

# Cache
rm -rf "$FIREFOX_PROFILE/cache2/*"
rm -rf "$FIREFOX_PROFILE/startupCache/*"
```

### 5. Recent Items (Arquivo → Abrir Recentes)

```bash
# Limpar Recent Items
rm -rf ~/Library/Application\ Support/com.apple.sharedfilelist/*
```

### 6. App Permissions (TCC — Micro, Câmera, Contatos)

```bash
# Visualizar permissões de apps (read-only)
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  "SELECT * FROM access"

# Remover permissão específica (use com cautela)
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db \
  "DELETE FROM access WHERE service='kTCCServiceMicrophone' AND client='com.exemplo.app'"
```

---

## Performance

### 1. Flush DNS Cache

```bash
# Limpar cache DNS
sudo dscacheutil -flushcache

# Kill mDNSResponder (reinicia automaticamente)
sudo killall -HUP mDNSResponder
```

### 2. Free Up RAM (Purge)

```bash
# Purge memória purgeable (libera RAM)
sudo purge
```

### 3. Rebuild Launch Services Database

```bash
# Reconstrói database de tipos de arquivo
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -kill -r -domain local -domain system -domain user
```

### 4. LaunchAgents & LaunchDaemons Quebrados

```bash
# Listar broken LaunchAgents
for f in ~/Library/LaunchAgents/*.plist; do
  plutil -lint "$f" > /dev/null 2>&1 || echo "BROKEN: $f"
done

# Remover agentes quebrados
for f in ~/Library/LaunchAgents/*.plist; do
  plutil -lint "$f" > /dev/null 2>&1 || rm "$f"
done

# Similar para /Library/LaunchAgents (requer sudo)
```

### 5. Desabilitar Login Items

```bash
# Listar login items
launchctl list | grep -v "^-"

# Remover um agente de inicialização
launchctl unload ~/Library/LaunchAgents/com.exemplo.agent.plist
```

---

## Maintenance

### 1. Reindex Spotlight

```bash
# Reindexar drive inteiro (pode demorar horas)
sudo mdutil -E /

# Desabilitar Spotlight (não recomendado)
sudo mdutil -a -i off

# Reabilitar
sudo mdutil -a -i on
```

### 2. Time Machine — Thin Local Snapshots

```bash
# Remover snapshots locais antigos (libera espaço)
tmutil thinlocalsnapshots / 9999999999999

# Listar snapshots locais
tmutil listlocalsnapshots /

# Deletar snapshot específico
tmutil deletelocalsnapshots /path/to/snapshot
```

### 3. Mail — Vacuum Database

```bash
# Otimizar banco de dados do Mail (libera espaço)
sqlite3 ~/Library/Mail/V*/MailData/"Envelope Index" VACUUM

# Aplica a todos os accounts
for db in ~/Library/Mail/V*/*/MailData/"Envelope Index"; do
  sqlite3 "$db" VACUUM
done
```

### 4. Fix Disk Permissions (legado, macOS < 11)

```bash
# macOS 10.15 e anteriores
diskutil repairPermissions /

# macOS 11+ não suporta (filesystem appleFS é self-healing)
```

### 5. Repair Disk

```bash
# Executar Disk Utility via CLI
diskutil verifyVolume /

# Reparar (requer boot em modo seguro ou Recovery)
diskutil repairVolume /
```

---

## Uninstaller + Leftovers

### 1. Remover App + Todos os Leftovers

```bash
# Template para remover um app completamente
APP_NAME="NomeDoApp"
BUNDLE_ID="com.exemplo.app"

# 1. Delete app
rm -rf /Applications/"$APP_NAME.app"

# 2. Application Support
rm -rf ~/Library/Application\ Support/"$APP_NAME"
rm -rf ~/Library/Application\ Support/"$BUNDLE_ID"

# 3. Caches
rm -rf ~/Library/Caches/"$BUNDLE_ID"

# 4. Preferences
rm -rf ~/Library/Preferences/"$BUNDLE_ID".plist
rm -rf ~/Library/Preferences/"$BUNDLE_ID"

# 5. Cookies
rm -rf ~/Library/Cookies/"$BUNDLE_ID".binarycookies

# 6. Saved State
rm -rf ~/Library/Saved\ Application\ State/"$BUNDLE_ID".savedState

# 7. Containers (sandboxed apps)
rm -rf ~/Library/Containers/"$BUNDLE_ID"

# 8. Group Containers
rm -rf ~/Library/Group\ Containers/*"$BUNDLE_ID"*

# 9. LaunchAgents
rm -rf ~/Library/LaunchAgents/"$BUNDLE_ID"*
rm -rf ~/Library/LaunchAgents/*"$BUNDLE_ID"*

# 10. Logs
rm -rf ~/Library/Logs/"$APP_NAME"
rm -rf ~/Library/Logs/"$BUNDLE_ID"

# 11. Crash Reports
rm -rf ~/Library/Logs/DiagnosticReports/*"$APP_NAME"*
rm -rf ~/Library/Logs/CrashReporter/*"$APP_NAME"*
```

### 2. Remover Pacotes PKG Instalados

```bash
# Listar todos os pacotes instalados
pkgutil --pkgs

# Obter informações de um pacote
pkgutil --pkg-info com.example.package

# Desinstalar pacote
sudo pkgutil --forget com.example.package

# Remover arquivos do pacote (manual)
pkgutil --files com.example.package | while read f; do
  sudo rm -rf "/$f"
done
```

### 3. Remover Extensões de Kernel Carregadas

```bash
# Listar todas as kernel extensions (kexts)
kextstat

# Descarregar uma kext
sudo kextunload -b com.example.kext

# Remover arquivo kext
sudo rm -rf /Library/Extensions/Example.kext
```

---

## Storage

### 1. Encontrar Arquivos Grandes

```bash
# Top 20 maiores arquivos
find ~ -type f -exec ls -lhS {} \; | head -20

# Arquivos maiores que 500MB
find ~ -type f -size +500M

# Arquivos maiores que 1GB em Downloads
find ~/Downloads -type f -size +1G

# Pastas maiores (du)
du -sh ~/* | sort -rh | head -20
```

### 2. Encontrar Duplicatas (por Hash MD5)

```bash
# Encontrar arquivos duplicados em uma pasta
find ~/Documents -type f -exec md5 {} \; | \
  awk '{print $NF " " $0}' | sort | \
  awk 'p && $1==f {print; next} {f=$1; p=1}' | \
  cut -d' ' -f2-

# Script mais robusto
declare -A seen
find ~/Documents -type f | while read file; do
  hash=$(md5 -q "$file")
  if [[ -v seen[$hash] ]]; then
    echo "Duplicate: $file (original: ${seen[$hash]})"
  else
    seen[$hash]="$file"
  fi
done
```

### 3. Encontrar Arquivos Antigos (não acessados)

```bash
# Arquivos não modificados há 90 dias
find ~ -type f -mtime +90

# Arquivos não acessados há 180 dias
find ~ -type f -atime +180

# Deletar arquivos não acessados há 1 ano
find ~ -type f -atime +365 -delete
```

### 4. Thin Binaries (Remove Intel Slice em Apple Silicon)

```bash
# Verificar arquitetura de um binário
lipo -info /Applications/AppName.app/Contents/MacOS/AppName

# Remove slice x86_64 (fica só arm64)
lipo -remove x86_64 /path/to/binary -output /path/to/binary.thin

# Fazer backup primeiro!
cp /path/to/binary /path/to/binary.backup
lipo -remove x86_64 /path/to/binary -output /path/to/binary
```

---

## Safe Equivalents Chart

| Função CleanMyMac | Shell Equivalente | Segurança | Comando |
|-------------------|-------------------|-----------|---------|
| System Junk → Caches | `rm -rf ~/Library/Caches/*` | ⚠️ Seletivo | Sim |
| System Junk → Logs | `rm -rf ~/Library/Logs/*` | ✅ Seguro | Sim |
| System Junk → Trash | `rm -rf ~/.Trash/*` | ✅ Seguro | Sim |
| Privacy → Quarantine | `rm ~/Library/Preferences/com.apple.LaunchServices.QuarantineEventsV2` | ✅ Seguro | Sim |
| Privacy → Safari History | `rm ~/Library/Safari/History.db*` | ✅ Seguro | Sim |
| Performance → DNS Flush | `sudo dscacheutil -flushcache` | ✅ Seguro | Sim |
| Performance → RAM Purge | `sudo purge` | ✅ Seguro | Sim |
| Maintenance → Spotlight Reindex | `sudo mdutil -E /` | ⚠️ Demora | Sim |
| Maintenance → Mail Vacuum | `sqlite3 ~/Library/Mail/V*/MailData/"Envelope Index" VACUUM` | ✅ Seguro | Sim |
| Uninstaller → App Leftovers | Script acima | ⚠️ Verificar | Sim |
| Storage → Duplicates | `find + md5` | ⚠️ Manual | Sim |

---

## Uso Prático — Scripts Prontos

### Script: Clean Everything Safe (Limpeza Completa Segura)

```bash
#!/bin/bash
# cleanmymac.sh — limpeza segura sem deps externas

set -e

echo "🧹 CleanMyMac Equivalente — Limpeza Segura"
echo "==========================================="

# 1. Caches
echo "▶ Limpando caches..."
rm -rf ~/Library/Caches/Google/Chrome
rm -rf ~/Library/Caches/com.spotify.client
rm -rf ~/Library/Caches/Firefox
rm -rf ~/Library/Caches/Homebrew
rm -rf ~/Library/Caches/pip

# 2. Logs
echo "▶ Limpando logs..."
rm -rf ~/Library/Logs/DiagnosticReports
rm -rf ~/Library/Logs/CrashReporter

# 3. Lixeira
echo "▶ Esvaziando lixeira..."
rm -rf ~/.Trash/*

# 4. DNS
echo "▶ Flushando DNS..."
sudo dscacheutil -flushcache

# 5. RAM
echo "▶ Purgando memória..."
sudo purge

# 6. Mail
echo "▶ Otimizando Mail..."
sqlite3 ~/Library/Mail/V*/MailData/"Envelope Index" VACUUM 2>/dev/null || true

echo ""
echo "✅ Limpeza concluída!"
df -h ~
```

### Script: Uninstall App Cleanly

```bash
#!/bin/bash
# uninstall_app.sh <app_name>

if [ -z "$1" ]; then
  echo "Uso: $0 <nome_do_app>"
  exit 1
fi

APP_NAME="$1"
BUNDLE_ID=$(mdls -name kMDItemCFBundleIdentifier -r /Applications/"$APP_NAME.app")

echo "Desinstalando: $APP_NAME (Bundle: $BUNDLE_ID)"

# Backup
mkdir -p ~/AppUninstallBackups
cp -r /Applications/"$APP_NAME.app" ~/AppUninstallBackups/

# Remove
rm -rf /Applications/"$APP_NAME.app"
rm -rf ~/Library/Application\ Support/"$APP_NAME" ~/Library/Application\ Support/"$BUNDLE_ID"
rm -rf ~/Library/Caches/"$BUNDLE_ID"
rm -rf ~/Library/Preferences/"$BUNDLE_ID".plist
rm -rf ~/Library/Containers/"$BUNDLE_ID"
rm -rf ~/Library/LaunchAgents/*"$BUNDLE_ID"*
rm -rf ~/Library/Logs/"$APP_NAME"

echo "✅ App desinstalado (backup em ~/AppUninstallBackups)"
```

---

## ⚠️ Avisos de Segurança

- **Não rode como `sudo` desnecessariamente** — pode afetar permissões do sistema
- **Sempre faça backup antes de limpezas grandes** — dados deletados são irrecuperáveis
- **Test em dry-run primeiro** — use `find` sem `-delete` antes
- **Evite limpar caches enquanto apps estão abertos** — podem não se recuperar direito
- **macOS Monterey+** — alguns caches são rebuild automático (seguro limpar)

---

## Referências

- [CleanMyMac X — Official](https://cleanmymac.com)
- [macOS Logs Location](https://support.apple.com/en-us/HT201948)
- [Unix Man Pages: find, rm, dscacheutil](https://man.openbsd.org)
- [SQLite3 CLI](https://www.sqlite.org/cli.html)

---

**Última atualização:** 2026-05-19 | Testado em: macOS Sequoia (Apple Silicon)
