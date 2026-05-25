#!/usr/bin/env python3
"""
Batch: Criação de 205 tarefas — 18/Mai/2026
Emagrecimento (21) + Memória (160) + Visão (24)
"""
import sys, os, time, json
sys.path.insert(0, os.path.expanduser("~/Scripts"))
from clickup_criar_tarefa import (
    create_task, add_checklist, CHECKLIST_COPY, CHECKLIST_EDITOR,
)

DELAY = 0.3  # segundos entre API calls

def build_task_list():
    tasks = []

    # === EMAGRECIMENTO [EM][OF05][FB] — 21 tasks ===
    for c_num, start_v in [(12, 7), (16, 1), (27, 1), (30, 1), (31, 1), (35, 1), (83, 1)]:
        for v in range(start_v, start_v + 3):
            tasks.append({
                'name': f'[EM][OF05][FB]C{c_num} V{v}',
                'nicho': 'EM', 'fonte': 'FB',
            })

    # === MEMÓRIA [MM][OF01][FB] — 160 tasks ===

    # 100 VAR VID de AD163 (V2 a V101)
    for v in range(2, 102):
        tasks.append({
            'name': f'[MM][OF01][FB]AD163 V{v}',
            'nicho': 'MM', 'fonte': 'FB',
        })

    # 25 IMG novas (AD126-IMG a AD150-IMG)
    for ad in range(126, 151):
        tasks.append({
            'name': f'[MM][OF01][FB]AD{ad}-IMG V1',
            'nicho': 'MM', 'fonte': 'FB',
        })

    # 20 VID novos com 2 hooks (AD131 a AD150, V1-V2)
    for ad in range(131, 151):
        tasks.append({
            'name': f'[MM][OF01][FB]AD{ad} V1-V2',
            'nicho': 'MM', 'fonte': 'FB',
        })

    # 15 Ripagens (C7 a C21)
    for c in range(7, 22):
        tasks.append({
            'name': f'[MM][OF01][FB]C{c}',
            'nicho': 'MM', 'fonte': 'FB',
        })

    # === VISÃO [VS][OF01][FB] — 24 tasks ===

    # 12 VAR VID de C15 (V1 a V12)
    for v in range(1, 13):
        tasks.append({
            'name': f'[VS][OF01][FB]C15 V{v}',
            'nicho': 'VS', 'fonte': 'FB',
        })

    # 12 VAR VID de C2 (V1 a V12)
    for v in range(1, 13):
        tasks.append({
            'name': f'[VS][OF01][FB]C2 V{v}',
            'nicho': 'VS', 'fonte': 'FB',
        })

    return tasks


def main():
    tasks = build_task_list()
    total = len(tasks)
    print(f"=== BATCH: {total} tarefas a criar ===\n")

    created = []
    errors = []

    for i, t in enumerate(tasks, 1):
        try:
            result = create_task(
                name=t['name'],
                nicho=t['nicho'],
                fonte=t['fonte'],
            )
            task_id = result['id']
            created.append({'name': t['name'], 'id': task_id})
            print(f"[{i}/{total}] ✅ {t['name']} (ID: {task_id})")
            time.sleep(DELAY)

            # Add checklists
            try:
                add_checklist(task_id, CHECKLIST_COPY)
                time.sleep(DELAY)
                add_checklist(task_id, CHECKLIST_EDITOR)
                time.sleep(DELAY)
            except Exception as e:
                print(f"  ⚠️ Checklist error: {e}")

        except Exception as e:
            errors.append({'name': t['name'], 'error': str(e)})
            print(f"[{i}/{total}] ❌ {t['name']} — {e}")
            time.sleep(1)  # back off on error

    # Summary
    print(f"\n=== RESULTADO ===")
    print(f"Criadas: {len(created)}/{total}")
    print(f"Erros: {len(errors)}")

    if errors:
        print("\nErros:")
        for e in errors:
            print(f"  {e['name']}: {e['error']}")

    # Save log
    log = {'created': created, 'errors': errors, 'total': total}
    log_path = os.path.expanduser("~/Scripts/data/batch_20260518_log.json")
    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"\nLog salvo em: {log_path}")


if __name__ == "__main__":
    main()
