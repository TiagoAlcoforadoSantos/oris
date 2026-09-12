"""
Funções de segurança relacionadas à senha do usuário.

Usa a biblioteca `bcrypt` diretamente (já era dependência do projeto
desde a Fase 1) — não introduz nenhuma dependência nova.

REGRAS SEGUIDAS:
- A senha em texto puro NUNCA é armazenada em nenhum lugar.
- `gerar_hash_senha` é usada ao criar/atualizar a senha de um usuário.
- `verificar_senha` é usada apenas no momento do login, para comparar
  a senha informada com o hash já salvo — nunca comparando texto
  puro contra texto puro.
"""

import bcrypt


def gerar_hash_senha(senha: str) -> str:
    """Gera o hash bcrypt de uma senha em texto puro.

    O resultado (uma string) é o que deve ser salvo no campo
    `senha_hash` do model Usuario — nunca a senha original.
    """
    if not senha:
        raise ValueError("A senha não pode ser vazia.")

    senha_bytes = senha.encode("utf-8")
    hash_bytes = bcrypt.hashpw(senha_bytes, bcrypt.gensalt())
    return hash_bytes.decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Verifica se `senha` (texto puro, digitada no login) corresponde
    ao `senha_hash` armazenado no banco.

    Retorna True/False. Nunca lança exceção para hash inválido/
    corrompido — nesse caso apenas retorna False, para não vazar
    detalhes de erro para quem está tentando logar.
    """
    if not senha or not senha_hash:
        return False

    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Hash em formato inesperado/corrompido — trata como senha inválida
        return False
