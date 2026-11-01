"""
Gera database/seed_etapa03.sql — massa de dados FICTÍCIA para demonstrar
a Etapa 03 (consultas, gráficos e estatística).

Determinístico (seed fixa): rodar de novo gera exatamente o mesmo SQL.

    python scripts/gerar_seed_etapa03.py
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(2026)

SAIDA = Path(__file__).resolve().parent.parent / "database" / "seed_etapa03.sql"
HASH_DEMO = "$2b$12$FyFrwG68GWFHAJzpCHQeY.Wax1Apnodv2crJ760KZ17wUrJlXerrG"  # Oris@2026
AGORA = datetime(2026, 10, 31, 12, 0, 0)

USUARIOS = [
    ("Admin Demonstração", "admin.demo@oris.example", "ADMINISTRADOR"),
    ("Gestão da Informação Demo", "gi.demo@oris.example", "GESTAO_INFORMACAO"),
    ("Responsável Saúde Bucal Demo", "rsb.demo@oris.example", "RESPONSAVEL_SAUDE_BUCAL"),
    ("Responsável Saúde Bucal Demo 2", "rsb2.demo@oris.example", "RESPONSAVEL_SAUDE_BUCAL"),
    ("Gestor Demonstração", "gestor.demo@oris.example", "GESTOR"),
]

# (nome, tipo, bairro, situacao) — nomes fictícios inspirados em bairros do Recife
UNIDADES = [
    ("USF Alto do Mandu", "Unidade de Saúde da Família", "Casa Amarela", "ATIVA"),
    ("USF Vila Arraes", "Unidade de Saúde da Família", "Várzea", "ATIVA"),
    ("USF Córrego do Jenipapo", "Unidade de Saúde da Família", "Macaxeira", "ATIVA"),
    ("USF Ibura de Baixo", "Unidade de Saúde da Família", "Ibura", "ATIVA"),
    ("USF UR-05", "Unidade de Saúde da Família", "Ibura", "ATIVA"),
    ("USF Jordão Alto", "Unidade de Saúde da Família", "Jordão", "MANUTENCAO"),
    ("USF Sítio Grande", "Unidade de Saúde da Família", "Imbiribeira", "ATIVA"),
    ("USF Pina", "Unidade de Saúde da Família", "Pina", "ATIVA"),
    ("USF Coque", "Unidade de Saúde da Família", "Joana Bezerra", "ATIVA"),
    ("USF Santo Amaro I", "Unidade de Saúde da Família", "Santo Amaro", "ATIVA"),
    ("USF Nova Descoberta", "Unidade de Saúde da Família", "Nova Descoberta", "ATIVA"),
    ("USF Alto José Bonifácio", "Unidade de Saúde da Família", "Morro da Conceição", "INATIVA"),
    ("USF Torrões", "Unidade de Saúde da Família", "Torrões", "ATIVA"),
    ("USF Sancho", "Unidade de Saúde da Família", "Sancho", "ATIVA"),
    ("USF Cohab Lagoa Encantada", "Unidade de Saúde da Família", "Cohab", "ATIVA"),
    ("USF Bongi", "Unidade de Saúde da Família", "Bongi", "ATIVA"),
    ("UBS Casa Amarela", "Unidade Básica de Saúde", "Casa Amarela", "ATIVA"),
    ("UBS Afogados", "Unidade Básica de Saúde", "Afogados", "ATIVA"),
    ("UBS Boa Viagem", "Unidade Básica de Saúde", "Boa Viagem", "ATIVA"),
    ("UBS Areias", "Unidade Básica de Saúde", "Areias", "MANUTENCAO"),
    ("CEO Centro", "Centro de Especialidades Odontológicas", "Boa Vista", "ATIVA"),
    ("CEO Afogados", "Centro de Especialidades Odontológicas", "Afogados", "ATIVA"),
    ("CEO Campo Grande", "Centro de Especialidades Odontológicas", "Campo Grande", "ATIVA"),
    ("CEO Ibura", "Centro de Especialidades Odontológicas", "Ibura", "ATIVA"),
    ("Policlínica Arnaldo Marques", "Policlínica", "Ibura", "ATIVA"),
    ("Policlínica Lessa de Andrade", "Policlínica", "Madalena", "ATIVA"),
    ("Policlínica Gouveia de Barros", "Policlínica", "Boa Vista", "ATIVA"),
    ("Policlínica Amaury Coutinho", "Policlínica", "Campina do Barreto", "ATIVA"),
    ("Laboratório Regional de Prótese Dentária", "Laboratório de Prótese", "Boa Vista", "ATIVA"),
    ("USF Caranguejo Tabaiares", "Unidade de Saúde da Família", "Afogados", "ATIVA"),
    ("USF Vietnã", "Unidade de Saúde da Família", "Cordeiro", "ATIVA"),
    ("USF Brasilit", "Unidade de Saúde da Família", "Várzea", "INATIVA"),
]

# Pares com CNES compartilhado (unidades mistas):
# (Policlínica Gouveia de Barros + CEO Centro) → marcadas corretamente
# (Policlínica Arnaldo Marques + CEO Ibura)    → uma SEM a marcação (consulta C6 detecta)
CNES_COMPARTILHADO = {
    "Policlínica Gouveia de Barros": ("9100021", 1),
    "CEO Centro": ("9100021", 1),
    "Policlínica Arnaldo Marques": ("9100025", 1),
    "CEO Ibura": ("9100025", 0),
}

# Unidades ATIVAS deliberadamente sem equipamento ativo (consulta C3)
SEM_EQUIPAMENTO = {"USF Coque", "USF Bongi", "USF Vietnã", "UBS Boa Viagem"}

SERVICOS_BASICOS = ["Atenção Básica em Saúde Bucal"]
SERVICOS_CEO = ["Endodontia", "Periodontia", "Cirurgia Oral Menor",
                "Estomatologia", "Pacientes com Necessidades Especiais"]
SERVICOS_POLI = ["Odontopediatria", "Radiologia Odontológica", "Urgência Odontológica"]

TIPOS_EQUIP = [
    ("Cadeira odontológica", "Cadeira odontológica completa"),
    ("Autoclave", "Autoclave 21 L"),
    ("Compressor", "Compressor odontológico isento de óleo"),
    ("Fotopolimerizador", "Fotopolimerizador LED"),
    ("Raio-X odontológico", "Aparelho de raio-X intraoral"),
    ("Ultrassom odontológico", "Ultrassom com jato de bicarbonato"),
    ("Amalgamador", "Amalgamador capsular"),
]


def q(valor):
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, datetime):
        return f"'{valor:%Y-%m-%d %H:%M:%S}'"
    return "'" + str(valor).replace("\\", "\\\\").replace("'", "''") + "'"


def dt_aleatoria(dias_max, dias_min=0):
    return AGORA - timedelta(days=random.randint(dias_min, dias_max),
                             hours=random.randint(0, 9), minutes=random.randint(0, 59))


def main():
    out = []
    w = out.append
    w("-- ==========================================================")
    w("-- ORIS — Etapa 03 — Massa de dados FICTÍCIA para demonstração")
    w("-- Gerado por scripts/gerar_seed_etapa03.py (determinístico).")
    w("--")
    w("-- ATENÇÃO: limpa unidades/serviços/equipamentos/alterações antes de")
    w("-- inserir. Use APENAS em banco de desenvolvimento/apresentação.")
    w("-- A tabela usuarios NÃO é apagada (usuários demo entram com INSERT IGNORE)")
    w("-- e a trilha de auditorias é preservada.")
    w("--")
    w("-- Usuários de demonstração (senha de todos: Oris@2026 — troque depois):")
    for nome, email, perfil in USUARIOS:
        w(f"--   {email:<28} {perfil}")
    w("-- Nomes e CNES são fictícios (CNES na faixa 91xxxxx, inexistente no CNES real).")
    w("-- ==========================================================")
    w("")
    w("USE oris_db;")
    w("SET NAMES utf8mb4;")
    w("-- Limpeza (DDL ALTER TABLE faz commit implícito, por isso fica fora da transação)")
    w("DELETE FROM alteracoes;")
    w("DELETE FROM equipamentos;")
    w("DELETE FROM servicos;")
    w("DELETE FROM unidades;")
    w("ALTER TABLE unidades AUTO_INCREMENT = 1;")
    w("ALTER TABLE servicos AUTO_INCREMENT = 1;")
    w("ALTER TABLE equipamentos AUTO_INCREMENT = 1;")
    w("ALTER TABLE alteracoes AUTO_INCREMENT = 1;")
    w("")
    w("START TRANSACTION;")
    w("")
    w("-- Usuários de demonstração")
    for nome, email, perfil in USUARIOS:
        criado = dt_aleatoria(240, 200)
        w("INSERT IGNORE INTO usuarios (nome, email, senha_hash, perfil, ativo, created_at, updated_at) "
          f"VALUES ({q(nome)}, {q(email)}, {q(HASH_DEMO)}, {q(perfil)}, TRUE, {q(criado)}, {q(criado)});")
    w("")

    # ---------------- Unidades ----------------
    w("-- Unidades")
    unidades = []
    for i, (nome, tipo, bairro, situacao) in enumerate(UNIDADES, start=1):
        cnes, mista = CNES_COMPARTILHADO.get(nome, (f"91{i:05d}", 0))
        criado = dt_aleatoria(200, 120)
        atualizado = criado + timedelta(days=random.randint(0, 110))
        unidades.append({"id": i, "nome": nome, "tipo": tipo, "situacao": situacao})
        endereco = f"Rua Fictícia {random.randint(10, 999)}"
        w("INSERT INTO unidades (id, nome, cnes, unidade_e_mista, tipo, endereco, bairro, cidade, uf, "
          "situacao, created_at, updated_at) VALUES "
          f"({i}, {q(nome)}, {q(cnes)}, {mista}, {q(tipo)}, {q(endereco)}, {q(bairro)}, 'Recife', 'PE', "
          f"{q(situacao)}, {q(criado)}, {q(atualizado)});")
    w("")

    # ---------------- Serviços ----------------
    w("-- Serviços")
    servicos = []
    sid = 0

    def add_servico(nome, unidade_id, situacao="ATIVO"):
        nonlocal sid
        sid += 1
        criado = dt_aleatoria(180, 60)
        servicos.append({"id": sid, "unidade_id": unidade_id, "situacao": situacao})
        w("INSERT INTO servicos (id, unidade_id, nome, situacao, created_at, updated_at) VALUES "
          f"({sid}, {q(unidade_id)}, {q(nome)}, {q(situacao)}, {q(criado)}, {q(criado)});")

    for u in unidades:
        if u["tipo"] in ("Unidade de Saúde da Família", "Unidade Básica de Saúde"):
            nomes = list(SERVICOS_BASICOS)
            if random.random() < .3:
                nomes.append("Odontopediatria")
        elif u["tipo"] == "Centro de Especialidades Odontológicas":
            nomes = random.sample(SERVICOS_CEO, random.randint(3, 5))
        elif u["tipo"] == "Policlínica":
            nomes = random.sample(SERVICOS_POLI, random.randint(2, 3))
        else:
            nomes = ["Prótese Dentária"]
        for nome in nomes:
            situacao = "INATIVO" if u["situacao"] == "INATIVA" or random.random() < .08 else "ATIVO"
            add_servico(nome, u["id"], situacao)
    # Serviço sem unidade (permitido desde a migration 0001)
    add_servico("Escovação supervisionada — ação itinerante em escolas", None)
    w("")

    # ---------------- Equipamentos ----------------
    w("-- Equipamentos")
    eid = 0
    serv_por_unidade = {}
    for s in servicos:
        serv_por_unidade.setdefault(s["unidade_id"], []).append(s["id"])

    def add_equip(nome, tipo, unidade_id, servico_id, situacao):
        nonlocal eid
        eid += 1
        criado = dt_aleatoria(170, 30)
        w("INSERT INTO equipamentos (id, unidade_id, servico_id, nome, tipo, situacao, created_at, updated_at) "
          f"VALUES ({eid}, {q(unidade_id)}, {q(servico_id)}, {q(nome)}, {q(tipo)}, {q(situacao)}, "
          f"{q(criado)}, {q(criado)});")

    pesos_qtd = {
        "Unidade de Saúde da Família": (1, 4),
        "Unidade Básica de Saúde": (2, 5),
        "Centro de Especialidades Odontológicas": (5, 10),
        "Policlínica": (3, 7),
        "Laboratório de Prótese": (2, 3),
    }
    for u in unidades:
        minimo, maximo = pesos_qtd[u["tipo"]]
        qtd = random.randint(minimo, maximo)
        for n in range(qtd):
            tipo, descricao = TIPOS_EQUIP[0] if n == 0 else random.choice(TIPOS_EQUIP)
            if u["nome"] in SEM_EQUIPAMENTO or u["situacao"] == "INATIVA":
                situacao = "INATIVO"
            else:
                situacao = "INATIVO" if random.random() < .15 else "ATIVO"
            servico_id = random.choice(serv_por_unidade.get(u["id"], [None]) + [None])
            add_equip(f"{descricao} #{n + 1}", tipo, u["id"], servico_id, situacao)
    # Equipamento sem unidade: consultório odontológico móvel
    add_equip("Unidade Odontológica Móvel (van)", "Unidade móvel", None, None, "ATIVO")
    # Inconsistência herdada de planilha: equipamento da USF Pina ligado a serviço do CEO Centro
    ceo_centro = next(u["id"] for u in unidades if u["nome"] == "CEO Centro")
    usf_pina = next(u["id"] for u in unidades if u["nome"] == "USF Pina")
    add_equip("Ultrassom com jato de bicarbonato (importado de planilha)", "Ultrassom odontológico",
              usf_pina, serv_por_unidade[ceo_centro][0], "ATIVO")
    w("")

    # ---------------- Alterações (fluxo de aprovação) ----------------
    w("-- Alterações (fluxo de aprovação) — usuários referenciados por email")
    solicitantes = ["rsb.demo@oris.example", "rsb2.demo@oris.example", "gi.demo@oris.example",
                    "admin.demo@oris.example"]
    pesos_sol = [5, 4, 2, 1]
    revisores = {"rsb.demo@oris.example": ["gi.demo@oris.example", "admin.demo@oris.example"],
                 "rsb2.demo@oris.example": ["gi.demo@oris.example", "admin.demo@oris.example"],
                 "gi.demo@oris.example": ["admin.demo@oris.example"],
                 "admin.demo@oris.example": ["gi.demo@oris.example"]}
    for _ in range(48):
        sol = random.choices(solicitantes, pesos_sol)[0]
        u = random.choice(unidades)
        operacao = random.choice(["EDITAR", "EDITAR", "ALTERAR_SITUACAO", "CRIAR"])
        criado = dt_aleatoria(175)
        r = random.random()
        status = "PENDENTE" if (r < .15 or (AGORA - criado).days < 3) else ("REJEITADO" if r < .32 else "APROVADO")
        registro_id = None if operacao == "CRIAR" and status != "APROVADO" else u["id"]
        descricao = {"EDITAR": f"Atualização cadastral: {u['nome']}",
                     "ALTERAR_SITUACAO": f"Mudança de situação: {u['nome']}",
                     "CRIAR": "Cadastro de nova unidade"}[operacao]
        if status == "PENDENTE":
            apr, quando = "NULL", "NULL"
        else:
            rev = random.choice(revisores[sol])
            apr = f"(SELECT id FROM usuarios WHERE email = {q(rev)})"
            quando = q(criado + timedelta(hours=random.choice([2, 5, 8, 20, 26, 48, 70])))
        w("INSERT INTO alteracoes (usuario_id, tabela, registro_id, operacao, dados_novos, descricao, "
          "status, created_at, approved_by, approved_at) VALUES "
          f"((SELECT id FROM usuarios WHERE email = {q(sol)}), 'unidades', {q(registro_id)}, "
          f"{q(operacao)}, NULL, {q(descricao)}, {q(status)}, {q(criado)}, {apr}, {quando});")
    w("")
    w("COMMIT;")
    w("")
    SAIDA.write_text("\n".join(out), encoding="utf-8")
    print(f"Gerado: {SAIDA} ({len(out)} linhas)")


if __name__ == "__main__":
    main()
