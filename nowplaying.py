"""Publica a mídia em reprodução no Windows para o AIDA64.

Registro HKCU\\Software\\FinalWire\\AIDA64\\ImportValues:
  Str1/4-7 = título, Str2/8 = artista, Str9 = "Nada tocando" em vários tamanhos (só o que cabe fica preenchido),
  Str3 = Tocando/Pausado; pausado por IDLE_AFTER s ou sem mídia -> "Nada tocando"
  (no AIDA: SREGVALSn). Geometria e fontes vêm de patch_layout.py.
Capa: cover.png ao lado deste script.
"""
import asyncio, io, os, sys, time, winreg
from PIL import Image, ImageChops, ImageDraw, ImageFont
from patch_layout import COVER_SIZE as SIZE, TEXT_W, TITLE, ARTIST, IDLE
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as Manager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
)
from winrt.windows.storage.streams import DataReader

INTERVAL = 1.0      # s entre leituras
IDLE_AFTER = 60     # s pausado até virar "Nada tocando"
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


def load_cover(data):
    img = square(Image.open(io.BytesIO(data)).convert("RGB")) if data else Image.new("RGB", (1, 1))
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def play_overlay(img):
    """Escurece a arte e desenha um botão de play no centro (desenhado em 4x para sair suave)."""
    k, s = 4, SIZE * 4
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 90))
    d = ImageDraw.Draw(layer)
    r = s * 0.24
    c = s / 2
    d.ellipse((c - r, c - r, c + r, c + r), fill=(0, 0, 0, 150), outline=(255, 255, 255, 230), width=2 * k)
    t = r * 0.5
    d.polygon([(c - t * 0.7, c - t), (c - t * 0.7, c + t), (c + t, c)], fill=(255, 255, 255, 255))
    layer = layer.resize((SIZE, SIZE), Image.LANCZOS)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def idle_cover():
    """Sem mídia: quadrado cinza escuro com nota musical (desenhado em 4x para sair suave)."""
    s = SIZE * 4
    img = Image.new("RGB", (s, s))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 10, fill=(28, 28, 28), outline=(62, 62, 62), width=4)
    d.text((s / 2, s / 2), "♪", font=ImageFont.truetype("seguisym.ttf", int(s * 0.6)), fill=(110, 110, 110), anchor="mm")
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def save_cover(img, paused=False):
    img = play_overlay(img) if paused else img
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
    last, base, shown, paused_since = None, None, None, None
    while True:
        try:
            sessions = list(mgr.get_sessions())
            s = next((x for x in sessions if x.get_playback_info().playback_status == Status.PLAYING), None) \
                or mgr.get_current_session()
            playing = bool(s) and s.get_playback_info().playback_status == Status.PLAYING
            paused_since = None if playing else (paused_since or time.monotonic())
            if s and not playing and time.monotonic() - paused_since >= IDLE_AFTER:
                s = None  # pausado há muito tempo: mostra "Nada tocando"
            if s:
                p = await s.try_get_media_properties_async()
                set_reg("Str3", "Tocando" if playing else "Pausado")
                key = (s.source_app_user_model_id, p.title, p.artist)
                if key != last:  # só trabalha quando a faixa muda
                    set_reg(IDLE, "")
                    set_lines(p.title, TITLE)
                    set_lines(p.artist, ARTIST)
                    base = load_cover(await read_thumb(p.thumbnail))
                    last = key
                if (key, playing) != shown:  # faixa nova ou play/pause: redesenha a capa
                    save_cover(base, paused=not playing)
                    shown = (key, playing)
            elif last != ():
                set_lines("", TITLE); set_lines("", ARTIST); set_reg("Str3", ""); set_reg(IDLE, "Nada tocando")
                save_cover(idle_cover())
                last, shown = (), None
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
        art = Image.new("RGB", (SIZE, SIZE), (200, 40, 40))
        ov = play_overlay(art)
        c = ov.getpixel((SIZE // 2, SIZE // 2))
        assert min(c) > 200 and ov.getpixel((2, 2))[0] < 200, (c, ov.getpixel((2, 2)))  # play branco, arte escurecida
        print("ok"); sys.exit()
    asyncio.run(main())
