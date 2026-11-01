"""
Módulo de Banco de Dados — Etapa 03 (disciplina de Banco de Dados).

Este pacote é a camada de acesso a dados com **SQL EXPLÍCITO**, no
mesmo espírito do JDBC em Java: a aplicação abre uma conexão com o
SGBD (MySQL/MariaDB) através do driver PyMySQL — que implementa a
especificação Python DB-API 2.0 (PEP 249), o equivalente direto do
JDBC —, monta um `cursor` (≈ `PreparedStatement`), executa comandos
SQL escritos à mão com parâmetros (`%s`, ≈ `?` do JDBC), lê o
resultado (≈ `ResultSet`) e controla a transação com `commit()` /
`rollback()`.

Nenhum ORM é usado aqui. Todo comando que chega ao banco está
escrito literalmente nos arquivos deste pacote:

- conexao.py          → abertura da conexão e controle de transação
- dao_unidades.py     → INSERT/UPDATE/DELETE/SELECT de `unidades`
- dao_servicos.py     → INSERT/UPDATE/DELETE/SELECT de `servicos`
- dao_equipamentos.py → INSERT/UPDATE/DELETE/SELECT de `equipamentos`
- dao_auditoria.py    → INSERT na trilha de auditoria (mesma transação)
- consultas.py        → as consultas analíticas da Etapa 03
- estatistica.py      → consultas que alimentam o painel estatístico
"""
