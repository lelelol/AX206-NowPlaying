"""Publica a mídia em reprodução no Windows para o AIDA64.

Registro HKCU\\Software\\FinalWire\\AIDA64\\ImportValues:
  Str1/4-7 = título e Str2/8 = artista em vários tamanhos (só o que cabe fica preenchido),
  Str3 = Tocando/Pausado/Nada tocando
  (no AIDA: SREGVALSn). Geometria e fontes vêm de patch_layout.py.
Capa: cover.png ao lado deste script.
"""
import asyncio, io, os, sys, winreg
from PIL import Image, ImageChops, ImageFont
from patch_layout import COVER_SIZE as SIZE, TEXT_W, TITLE, ARTIST
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as Manager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
)
from winrt.windows.storage.streams import DataReader

INTERVAL = 1.0      # s entre leituras
DIR = os.path.dirname(os.path.abspath(__file__))
COVER = os.path.join(DIR, "cover.png")
KEY = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\FinalWire\AIDA64\ImportValues")
_reg = {}


def set_reg(name, value):
    if _reg.get(name) != value:
        winreg.SetValueEx(KEY, name, 0, winreg.REG_SZ, value)
        _reg[name] = value


def wrap(text, spec):
    """Quebra em linhas que cabem em TEXT_W px; a última ganha reticências se sobrar texto.
    Devolve (linhas, coube) — coube=False se precisou cortar texto ou partir palavra."""
    font = ImageFont.truetype(spec["font"], round(spec["pt"] * 96 / 72))
    fits = lambda t: font.getlength(t) <= TEXT_W
    words, lines, ok = (text or "").split(), [], True
    for n in range(len(spec["lines"])):
        last = n == len(spec["lines"]) - 1
        line = ""
        while words and fits((line + " " + words[0]).strip()):
            line = (line + " " + words.pop(0)).strip()
        if not line and words:  # palavra maior que a linha inteira
            ok = False
            line, words[0] = words[0], ""
            while not fits(line): words[0] = line[-1] + words[0]; line = line[:-1]
            words = [w for w in words if w]
        if last and words:
            ok = False
            while line and not fits(line + "…"): line = line[:-1]
            line = line.rstrip() + "…"
        lines.append(line)
    return dict(zip(spec["lines"], lines)), ok


def fit(text, specs):
    """Usa o maior tamanho (specs vêm do maior pro menor) em que o texto cabe inteiro; os outros ficam vazios."""
    out, chosen = {}, None
    for spec in specs:
        lines, ok = wrap(text, spec)
        if chosen is None and (ok or spec is specs[-1]):
            chosen = lines
        out.update(lines if lines is chosen else dict.fromkeys(lines, ""))
    return out


def set_lines(text, specs):
    for name, line in fit(text, specs).items():
        set_reg(name, line)


def square(img):
    # tira faixas lisas embutidas (vídeo vertical em miniatura 16:9) e recorta ao centro
    bg = Image.new("RGB", img.size, img.getpixel((0, img.height // 2)))
    box = ImageChops.difference(img, bg).convert("L").point(lambda v: v > 24 and 255).getbbox()
    if box and (box[2] - box[0]) * (box[3] - box[1]) > img.width * img.height * 0.2:
        img = img.crop(box)
    s = min(img.size)
    l, t = (img.width - s) // 2, (img.height - s) // 2
    return img.crop((l, t, l + s, t + s))


def save_cover(data):
    img = square(Image.open(io.BytesIO(data)).convert("RGB")) if data else Image.new("RGB", (1, 1))
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    tmp = COVER + ".tmp"
    img.save(tmp, "PNG")
    os.replace(tmp, COVER)  # troca atômica: o AIDA nunca lê arquivo pela metade


async def read_thumb(ref):
    if not ref:
        return None
    stream = await ref.open_read_async()
    reader = DataReader(stream.get_input_stream_at(0))
    n = await reader.load_async(stream.size)
    buf = bytearray(n)
    reader.read_bytes(buf)
    return bytes(buf)


async def main():
    mgr = await Manager.request_async()
    last = None
    while True:
        try:
            sessions = list(mgr.get_sessions())
            s = next((x for x in sessions if x.get_playback_info().playback_status == Status.PLAYING), None) \
                or mgr.get_current_session()
            if s:
                p = await s.try_get_media_properties_async()
                playing = s.get_playback_info().playback_status == Status.PLAYING
                set_reg("Str3", "Tocando" if playing else "Pausado")
                key = (s.source_app_user_model_id, p.title, p.artist)
                if key != last:  # só trabalha quando a faixa muda
                    set_lines(p.title, TITLE)
                    set_lines(p.artist, ARTIST)
                    save_cover(await read_thumb(p.thumbnail))
                    last = key
            elif last != ():
                set_lines("", TITLE); set_lines("", ARTIST); set_reg("Str3", "Nada tocando")
                save_cover(None)
                last = ()
        except Exception as e:  # sessão some no meio da leitura etc.: tenta de novo no próximo ciclo
            print("erro:", e)
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    if sys.argv[1:] == ["test"]:
        big, mid, small = (s["lines"] for s in TITLE)
        short = fit("Abracadabra", TITLE)          # curto -> só a versão grande
        assert short[big[0]] == "Abracadabra" and not any(short[k] for k in mid + small), short
        two = fit("Criadora batiza o filho com nome", TITLE)  # médio -> 2 linhas média
        assert not two[big[0]] and all(two[k] for k in mid) and not any(two[k] for k in small), two
        long = fit("Renekton digitou pro meu Kayn top...Já sabem né ?? #leagueoflegends #game #jbsniper #gamer", TITLE)
        assert long[small[-1]].endswith("…") and not any(long[k] for k in big + mid), long
        assert fit("x" * 200, TITLE)[small[-1]].endswith("…")
        assert not any(fit("", TITLE).values())
        print("ok"); sys.exit()
    asyncio.run(main())
