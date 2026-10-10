# AIDA64 NowPlaying (AX206)

Mostra a mídia em reprodução (capa, título, artista) na tela AX206 do AIDA64,
junto com os sensores do layout original. O cartão de FPS vira o player.

## Como funciona
- `nowplaying.py` lê a mídia do Windows (Spotify, navegador, etc.) a cada 1 s.
  - Grava título e artista em `HKCU\Software\FinalWire\AIDA64\ImportValues`, que o AIDA lê como `SREGVALSn`.
  - Grava a capa em `cover.png`, que o AIDA recarrega sozinho quando o arquivo muda.
  - O título e o artista ficam em várias versões empilhadas, de tamanhos diferentes. Só a maior que cabe inteira é preenchida, o que funciona como fonte dinâmica.
- `patch_layout.py` monta a tela no `aida64.ini` a partir do preset original (backup).
  Use `python patch_layout.py preview` para gerar uma prévia aproximada.

## Uso
| Script (admin) | Faz |
|---|---|
| `aplicar.ps1`   | fecha o AIDA, aplica o layout, reinicia o USB do AX206 e reabre |
| `reverter.ps1`  | restaura o preset original do backup |
| `reiniciar.ps1` | só reinicia o AIDA e o USB (quando aparecer "LCD init failed") |

Dependências: `python -m pip install --user -r requirements.txt`.
Autoinício: atalho `AIDA64 NowPlaying` na pasta Inicializar, que roda `pythonw nowplaying.py`.
Backup do preset original: `Documents\AIDA64-backup-AX206-2026-10-10` (fora do repo, porque o ini pode conter credenciais).

## Custo medido (i5-14400F, 16 threads)
- Coletor: ~0,004% da CPU total e ~47 MB de RAM. Numa troca de faixa: ~15 ms para a capa e ~2 ms para o ajuste do texto.
- AIDA64 com a tela: ~0,29% da CPU total e ~115 MB de RAM.
