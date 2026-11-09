"""Gera database/seed_etapa06.sql: historico FICTICIO de manutencoes (deterministico).

Roda depois de database/seed_etapa03.sql (usa os equipamentos de id 1..N).
Os registros historicos entram CONCLUIDOS/CANCELADOS, entao os triggers
nao alteram a situacao dos equipamentos; as ABERTAS preventivas tambem nao.
"""
import os
import random
from datetime import date, timedelta

random.seed(2026)
N_EQUIP = 119
HOJE = date(2026, 11, 9)
TIPOS_DESC = {
    "PREVENTIVA": ["Revisao periodica", "Calibracao", "Limpeza e lubrificacao", "Troca de filtros"],
    "CORRETIVA": ["Troca de peca danificada", "Reparo do compressor", "Falha eletrica", "Vazamento no circuito"],
}
linhas = []
for _ in range(90):
    equip = random.randint(1, N_EQUIP)
    tipo = random.choices(["PREVENTIVA", "CORRETIVA"], weights=[55, 45])[0]
    abertura = HOJE - timedelta(days=random.randint(5, 300))
    desc = random.choice(TIPOS_DESC[tipo])
    r = random.random()
    if r < 0.82:
        situ, dias = "CONCLUIDA", random.randint(1, 20 if tipo == "CORRETIVA" else 5)
        concl = abertura + timedelta(days=dias)
        custo = round(random.uniform(250, 2800) if tipo == "CORRETIVA" else random.uniform(60, 450), 2)
    elif r < 0.9:
        situ, concl, custo = "CANCELADA", None, 0
    else:
        situ, concl, custo = "ABERTA", None, 0
        tipo = "PREVENTIVA"  # abertas de teste nao desligam equipamento
        abertura = HOJE - timedelta(days=random.randint(1, 20))
    c = f"'{concl}'" if concl else "NULL"
    linhas.append(
        f"INSERT INTO manutencoes (equipamento_id, tipo, descricao, data_abertura, data_conclusao, custo, situacao, created_at, updated_at) "
        f"VALUES ({equip}, '{tipo}', '{desc}', '{abertura}', {c}, {custo}, '{situ}', UTC_TIMESTAMP(), UTC_TIMESTAMP());"
    )

cab = """-- ORIS - Etapa 06 - Historico FICTICIO de manutencoes (gerado por scripts/gerar_seed_etapa06.py)
-- Pre-requisitos: tabela manutencoes e objetos da Etapa 05 criados
-- (python database/aplicar_migracoes.py) e database/seed_etapa03.sql carregado.
-- ATENCAO: limpa manutencoes antes de inserir. Apenas para desenvolvimento/apresentacao.

SET NAMES utf8mb4;
DELETE FROM manutencoes;
ALTER TABLE manutencoes AUTO_INCREMENT = 1;
START TRANSACTION;
"""
destino = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "seed_etapa06.sql")
with open(destino, "w", encoding="utf-8", newline="\n") as f:
    f.write(cab + "\n".join(linhas) + "\nCOMMIT;\n")
print("gerado", destino, len(linhas))
