# IMPERA — Sistema de Automação ClickUp + RedTrack

Repositório central para automações IMPERA com GitHub Actions (CI/CD).

## 📊 Componentes

- **Briefing Diário**: Panorama operacional (10h seg-sáb)
- **Auto Envio Tráfego**: Sincronização COPY → GT (*/10 min seg-sáb)
- **Relatórios Semanais**: Produção e RedTrack (domingo 12:03)
- **Relatórios Setorizados**: Copy/Edição/Tráfego/GPDR (domingo 23:00)
- **Relatórios Mensais**: Arquivo Morto e Copywriters (1º 09:07)

## 🚀 Cloud Deployment

Cron jobs rodam em GitHub Actions (grátis, 99.9% uptime).
Webhooks rodando localmente (ou em Render para 24/7).

## 🔐 Configuração

### 1. GitHub Secrets

Adicione em `Settings → Secrets and variables → Actions`:

```
CLICKUP_API_TOKEN      = pk_...
REDTRACK_API_KEY       = ...
TELEGRAM_BOT_TOKEN     = ...
TELEGRAM_CHAT_ID       = ...
```

### 2. Rodar Localmente

```bash
pip install -r requirements.txt

# Briefing
python3 Scripts/briefing_diario.py

# Auto Envio
python3 Scripts/auto_envio_trafego.py --monitor

# Relatórios
python3 Scripts/relatorio_semanal_impera.py
```

## 📅 Agendamento

| Quando | O Quê | Status |
|--------|-------|--------|
| 10h seg-sáb | Briefing Diário | ✅ GitHub Actions |
| */10 min seg-sáb | Auto Envio Tráfego | ✅ GitHub Actions |
| Domingo 12:03 | Relatórios Semanais | ✅ GitHub Actions |
| Domingo 23:00 | Relatórios Setorizados | ✅ GitHub Actions |
| 1º 09:07 | Relatórios Mensais | ✅ GitHub Actions |

## 🧪 Testes

Para testar manualmente:

1. Ir em `Actions`
2. Selecionar `IMPERA — Automação Completa`
3. Clicar em `Run workflow`
4. Escolher tarefa (all/briefing/auto-envio/etc)
5. Executar

## 📊 Monitoramento

Logs disponíveis em: `Actions → Workflow runs`

Cada execução mostra:
- Status (✅/❌)
- Tempo de execução
- Output dos scripts
- Erros (se houver)

## 🔗 Links

- **ClickUp**: https://app.clickup.com
- **RedTrack**: https://redtrack.com.br
- **Obsidian**: ~/Obsidian/IMPERA/
- **Scripts**: ~/Scripts/

## 📞 Support

Se algo falhar:
1. Verificar logs em `Actions`
2. Validar secrets em `Settings → Secrets`
3. Rodar script localmente para debug
4. Verificar credenciais em `~/.zshrc`

---

Criado em: 25/05/2026
Mantido por: Iago Almeida (GPDR)
