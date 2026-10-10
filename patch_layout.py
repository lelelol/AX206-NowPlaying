"""Monta a tela única do AX206: layout original + player no lugar do cartão de FPS.
Parte sempre da página 1 do backup original (idempotente). Rodar com o AIDA64 FECHADO.

  python patch_layout.py           -> grava no aida64.ini
  python patch_layout.py preview   -> gera preview.png aproximado (valores atuais do registro)
"""
import re, sys

INI = r"C:\Program Files\FinalWire\AIDA64 Business\aida64.ini"
BACKUP = r"C:\Users\Leandro\Documents\AIDA64-backup-AX206-2026-10-10\aida64.ini"
DIR = r"C:\Users\Leandro\AIDA64-NowPlaying"
COVER = DIR + r"\cover.png"
ASSETS = r"C:\Program Files\FinalWire\AIDA64 Business\AX206 LCD"
WHITE, GREY = 16777215, 7500402  # cores BGR do layout atual

# Player no cartão de baixo à esquerda (10..313 x 220..309). Geometria compartilhada com nowplaying.py.
COVER_SIZE = 77
COVER_X, COVER_Y = 17, 226
TEXT_X, TEXT_W = 104, 201
# Versões empilhadas no mesmo lugar, da maior pra menor: nowplaying.py preenche só a maior que cabe inteira.
TITLE = [dict(font="calibrib.ttf", pt=20, lines=("Str5",), y=247, step=0),
         dict(font="calibrib.ttf", pt=16, lines=("Str6", "Str7"), y=239, step=22),
         dict(font="calibrib.ttf", pt=13, lines=("Str1", "Str4"), y=242, step=19)]
ARTIST = [dict(font="calibri.ttf", pt=13, lines=("Str8",), y=283, step=0),
          dict(font="calibri.ttf", pt=11, lines=("Str2",), y=284, step=0)]


def is_fps(item):  # itens do cartão de FPS que saem (número, ícone, rótulo e gráfico)
    return "SRTSSFPS" in item or "Fps-Icon" in item or "<LBL>FPS</LBL>" in item


def sensor(id_, x, y, size, color=WHITE, wid=TEXT_W, font="Calibri", bold="000", unit=""):
    return (f"<ID>{id_}</ID><WID>{wid}</WID><TXTSIZ>{size}</TXTSIZ><FNTNAM>{font}</FNTNAM><SHDCOL>0</SHDCOL><SHDDIS>1</SHDDIS><SHDDEP>1</SHDDEP>"
            f"<SHWLBL>0</SHWLBL><LBL>{id_}</LBL><LBLCOL>{GREY}</LBLCOL><LBLBIS>000</LBLBIS>"
            f"<SHWVAL>1</SHWVAL><VALCOL>{color}</VALCOL><VALBIS>{bold}</VALBIS>"
            f"<SHWUNT>{1 if unit else 0}</SHWUNT><UNT>{unit}</UNT><UNTCOL>{GREY}</UNTCOL><UNTBIS>000</UNTBIS><UNTWID>40</UNTWID><SHWBAR>0</SHWBAR>"
            f"<ITMX>{x}</ITMX><ITMY>{y}</ITMY>")


def img(path, x, y):
    return f"<ID>IMG</ID><URL></URL><IMGFIL>{path}</IMGFIL><ITMX>{x}</ITMX><ITMY>{y}</ITMY>"


def text_lines(spec, color, bold):
    return [sensor("SREGVALS" + s[3:], TEXT_X, spec["y"] + i * spec["step"], spec["pt"], color=color, bold=bold)
            for i, s in enumerate(spec["lines"])]


NEW_ITEMS = [
    img(ASSETS + r"\Fps-Icon.png", 18, 22),                  # FPS sobe para o canto, ao lado do relógio
    sensor("SRTSSFPS", 42, 17, 16, wid=80, unit=" FPS"),
    img(COVER, COVER_X, COVER_Y),
    sensor("SREGVALS3", TEXT_X, 225, 10, color=GREY),        # Tocando / Pausado / Nada tocando
    *[it for spec in TITLE for it in text_lines(spec, WHITE, "100")],
    *[it for spec in ARTIST for it in text_lines(spec, GREY, "000")],
]
SETTINGS = {"HWMonLCDAutoPageCycle": "0", "HotKeySwitchLCDPage1": "", "HotKeySwitchLCDPage2": ""}


def read(path):
    return [l.rstrip("\r") for l in open(path, encoding="utf-16").read().split("\n")]


def page1(original):
    return [l for l in original if l.startswith("HWMonLCDItemAXA1=") and not is_fps(l)] + \
           ["HWMonLCDItemAXA1=" + it for it in NEW_ITEMS]


def patch(lines, original):
    first = next(i for i, l in enumerate(lines) if l.startswith("HWMonLCDItemAXA"))
    lines = [l for l in lines if not l.startswith("HWMonLCDItemAXA")]
    lines[first:first] = page1(original)
    return [f"{l.split('=', 1)[0]}={SETTINGS[l.split('=', 1)[0]]}" if l.split("=", 1)[0] in SETTINGS else l for l in lines]


def preview(out=DIR + r"\preview.png"):
    """Aproximação do que o AIDA desenha (pt -> px a 96 dpi; barras e medidores simplificados)."""
    import time, winreg
    from PIL import Image, ImageDraw, ImageFont
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\FinalWire\AIDA64\ImportValues")
    def reg(n):
        try: return winreg.QueryValueEx(key, n)[0]
        except OSError: return ""
    fake = {"STIMENS": time.strftime("%H:%M"), "TCPUPKG": "45", "SCPUCLK": "4700", "FCPU": "1200", "TGPU1": "50",
            "SGPU1CLK": "2600", "FGPU1": "1100", "SMEMUTI": "41", "SUSEDMEM": "13050", "SFREEMEM": "18900", "SRTSSFPS": "144"}
    units = {"TCPUPKG": "°C", "TGPU1": "°C", "SCPUCLK": " MHz", "SGPU1CLK": " MHz", "FCPU": " RPM", "FGPU1": " RPM",
             "SMEMUTI": "%", "SUSEDMEM": " MB", "SFREEMEM": " MB"}
    canvas = Image.new("RGB", (480, 320))
    d = ImageDraw.Draw(canvas)
    def font(f, pt, bold=False):
        name = {"Calibri Light": "calibril.ttf", "Tahoma": "tahoma.ttf"}.get(f, "calibrib.ttf" if bold else "calibri.ttf")
        return ImageFont.truetype(name, round(int(pt) * 96 / 72))
    rgb = lambda bgr: (int(bgr) & 255, int(bgr) >> 8 & 255, int(bgr) >> 16)
    for line in page1(read(BACKUP)):
        f = dict(re.findall(r"<(\w+)>([^<]*)</\1>", line))
        x, y, id_ = int(f["ITMX"]), int(f["ITMY"]), f.get("ID", "")
        if id_ == "IMG":
            im = Image.open(f["IMGFIL"]).convert("RGBA"); canvas.paste(im, (x, y), im)
        elif id_.startswith("[GAUGE]"):
            im = Image.open(f["STAFLS"].split("|")[5]).convert("RGBA"); canvas.paste(im, (x, y), im)
            d.text((x + 50, y + 50), "33", font=font("", f["TXTSIZ"]), fill="white", anchor="mm")
        elif id_ == "LBL":
            d.text((x, y), f["LBL"], font=font(f["FNTNAM"], f["TXTSIZ"]), fill=rgb(f["LBLCOL"]))
        elif f.get("SHWBAR") == "1" and f.get("SHWVAL") != "1" or (id_ and f.get("SHWBAR") == "1" and f.get("TXTSIZ") == "8"):
            d.rectangle((x, y, x + int(f["BARWID"]), y + int(f["BARHEI"]) - 6), fill=(70, 160, 70))
        elif id_:
            val = reg("Str" + id_[8:]) if id_.startswith("SREGVALS") else fake.get(id_, "?")
            fnt = font(f["FNTNAM"], f["TXTSIZ"], f.get("VALBIS", "0")[0] == "1")
            cx = x
            if f.get("SHWLBL") == "1":
                d.text((x, y), f["LBL"], font=fnt, fill=rgb(f["LBLCOL"])); cx = x + 45
            d.text((cx, y), val, font=fnt, fill=rgb(f["VALCOL"]))
            if f.get("SHWUNT") == "1":
                d.text((cx + d.textlength(val, font=fnt), y), f["UNT"] or units.get(id_, ""), font=fnt, fill=(114, 114, 114))
    canvas.save(out)
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["preview"]:
        print(preview()); sys.exit()
    original = read(BACKUP)
    out = patch(read(INI), original)
    kept = [l for l in original if l.startswith("HWMonLCDItemAXA1=") and not is_fps(l)]
    assert all(l in out for l in kept) and not any(l.startswith("HWMonLCDItemAXA2=") for l in out)
    open(INI, "w", encoding="utf-16", newline="\r\n").write("\n".join(out))
    print("ok:", len(kept), "itens originais +", len(NEW_ITEMS), "novos")
