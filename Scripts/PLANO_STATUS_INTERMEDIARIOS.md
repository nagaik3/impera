# Plano: Status Intermediários + Automações ClickUp

**Status**: Arquivado (requer crédito de automação - indisponível)

## Objetivo
Contornar limitação ClickUp: não permite transitions para status tipo "done" via API.

## Solução (Requer Crédito de Automação)
```
finalizado (custom)
  ↓ api_put (funciona)
aprovado-trafego (custom) ou aprovado-vturb (custom)
  ↓ automação ClickUp nativa (REQUER CRÉDITO)
enviado para trafego (done) ou enviado para vturb (done)
  ↓ auto_envio_trafego.py (10 min polling)
Cópia em Gestão de Trafego → "aguardando teste"
```

## Passos Manuais (Se Tiver Crédito No Futuro)

### Passo 1: Criar 2 Statuses no ClickUp
Acesse: **List COPY → Settings → Statuses**

Criar (tipo "custom"):
- "aprovado-trafego" (verde)
- "aprovado-vturb" (azul)

### Passo 2: Criar 2 Automações
Acesse: **List COPY → Automations**

**Automação 1:**
```
Trigger: Status changes to "aprovado-trafego"
Action: Change status to "enviado para trafego"
```

**Automação 2:**
```
Trigger: Status changes to "aprovado-vturb"
Action: Change status to "enviado para vturb"
```

### Passo 3: Atualizar Código
`gate_finalizado.py`: Mudar `determine_target_status()` para retornar:
- "aprovado-trafego" (em vez de "enviado para trafego")
- "aprovado-vturb" (em vez de "enviado para vturb")

## Por Que Essa Abordagem
- ✅ API consegue fazer move: custom → custom
- ✅ date_done preservado (ClickUp nativo faz move para "done")
- ✅ auto_envio_trafego.py continua funcionando sem mudanças
- ✅ Sem ambiguidade (2 caminhos claros)

## Limitação Atual
Crédito de automação indisponível. Usar abordagem alternativa: **Script Polling (aprova_para_trafego.py)**.
