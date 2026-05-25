#!/usr/bin/env python3
"""
Export desconhecidos do JSON de cache do relatório
"""
import os, sys, json
from pathlib import Path

cache_dir = Path(os.path.expanduser('~/Scripts/data'))

# Find the latest relatorio cache
import glob
import os

# Run a quick fetch to get the data
print("Rodando relatório para capturar desconhecidos...\n")
os.system("cd ~/Scripts && source ~/.impera_env && python3 relatorio_copywriters_semanal.py 2>&1 | tee /tmp/relatorio_run.log")

# Read the output
with open('/tmp/relatorio_run.log', 'r') as f:
    output = f.read()

# Extract os números
import re

if 'DESCONHECIDO' in output:
    lines = output.split('\n')
    for line in lines:
        if 'DESCONHECIDO' in line:
            print(f"\n{line}")
