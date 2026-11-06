# Fixtures de teste

Páginas do Balanço Patrimonial (consolidado e controladora) do ITR do 3T26 da Gerdau e da Usiminas,
em texto, usadas pelos testes para rodar sem os PDFs inteiros.

- **Fonte:** documentos públicos publicados pelas empresas e na CVM, os mesmos PDFs versionados em
  `data/itrs/`. Uso exclusivo de teste: cópia verbatim e mínima (10 páginas). Ver `docs/USO-DOS-DADOS.md`.
- **Nomes:** `pagina_NN.txt` usa o índice da página no PDF (base 1), o mesmo de `saida/<pdf>/pagina_NN.txt`.
  Só existem as páginas do Balanço; as demais ficam ausentes (os testes completam com páginas vazias).
- **Regenerar / conferir:** `python scripts/gerar_fixtures.py` e `python scripts/gerar_fixtures.py --check`
  (precisa dos PDFs em `data/itrs/`). O `MANIFEST.json` guarda bytes e SHA-256 de cada página e o SHA-256 dos PDFs.
- **Nunca edite à mão:** o teste de hash (`tests/test_fixtures.py`) pega qualquer alteração.
- **`invalidos/`:** JSONs fora do contrato (estáticos), usados pelos testes do contrato (`src/contrato.py`).
- **Fixtures negativas de texto** (dígito trocado, título alterado) são derivadas por mutação em `tmp_path`,
  dentro dos testes, e não ficam salvas aqui.
