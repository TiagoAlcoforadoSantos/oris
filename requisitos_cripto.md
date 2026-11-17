# Requisitos de criptografia

## O que foi alterado

- Uploads de planilhas são recebidos em memória e cifrados antes de serem gravados na pasta temporária `%TEMP%\oris_importacoes`. O app os decifra em memória para ler; após concluir ou falhar o fluxo, remove o arquivo temporário.
- O campo `alteracoes.dados_novos` é cifrado pela aplicação. As telas e o fluxo de aprovação decifram os valores quando necessário. Solicitações antigas em texto simples continuam legíveis até serem migradas.
- A chave `DATA_ENCRYPTION_KEY` é obrigatória fora de testes. Gere uma chave Fernet com:

  ```powershell
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

  Coloque-a no `.env` e mantenha uma cópia segura. Perder ou trocar a chave impede a leitura dos dados já cifrados.
- A criptografia do volume do servidor, do banco inteiro e dos backups não é ativada pelo código; deve ser configurada na infraestrutura que hospeda o MySQL e os backups.

## Como testar

Faça o teste em uma base de desenvolvimento e use uma planilha fictícia com um marcador único, por exemplo `ORIS_TESTE_CRIPTO`.

1. Inicie uma importação e deixe a tela de mapeamento aberta. No PowerShell, confira o arquivo temporário mais recente:

   ```powershell
   $arquivo = Get-ChildItem "$env:TEMP\oris_importacoes" -File |
       Sort-Object LastWriteTime -Descending |
       Select-Object -First 1
   $texto = [System.Text.Encoding]::UTF8.GetString(
       [System.IO.File]::ReadAllBytes($arquivo.FullName)
   )
   $arquivo.Name
   $texto.Contains("ORIS_TESTE_CRIPTO")
   ```

   O arquivo deve existir durante o fluxo e o resultado de `Contains` deve ser `False`. Conclua a importação e confirme que o arquivo temporário foi removido.

2. No DBeaver, conecte ao MySQL configurado no `.env`, abra uma SQL Console e execute:

   ```sql
   SELECT id, tabela, operacao, status,
          LEFT(dados_novos, 15) AS prefixo,
          LOCATE('ORIS_TESTE_CRIPTO', dados_novos) AS texto_plano,
          created_at
   FROM alteracoes
   WHERE dados_novos LIKE 'oris-fernet-v1:%'
   ORDER BY id DESC
   LIMIT 10;
   ```

   As solicitações novas devem mostrar `oris-fernet-v1:` no prefixo e `0` em `texto_plano`. Abra a solicitação na tela **Alterações** do app para confirmar que os dados aparecem legíveis após a decifragem.

3. Para cifrar solicitações antigas, faça backup primeiro e execute com o `.env` e a chave correta:

   ```powershell
   flask --app run.py criptografar-alteracoes-legadas
   ```

4. Para verificar o estado do BitLocker no volume `C:`, execute `manage-bde -status C:` no PowerShell. Esse comando apenas consulta o estado; habilitar criptografia do volume e proteger backups são etapas de infraestrutura separadas.

## Validação automatizada

Os testes focados de importação, alterações, aprovações e configuração da chave passaram: `136 passed`.
