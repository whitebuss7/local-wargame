#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN ÜZERİNDEN 3 KİŞİLİK 3D SAVAŞ OYUNU  v2  (Ursina)

Kurulum (3 bilgisayarın hepsinde):   pip install ursina
Sunucu kuran bilgisayar:             python savas3d.py host Ahmet
Diğer 2 bilgisayar:                  python savas3d.py join 192.168.1.20 Mehmet
(Argümansız çalıştırırsan soru sorar.)
Sadece sunucu (ekransız):            python savas3d.py server

Tüm bilgisayarlar AYNI Wi-Fi/LAN'da olmalı. Windows güvenlik duvarı sorarsa
"Özel ağlar" için izin ver. Port: 5555 (TCP).

OYUN AKIŞI
  Herkes bağlanınca karakterini seçer (1/2/3 ya da tıkla) ve HAZIR'a basar.
  Herkes hazır olunca sunucu kuran oyuncu "OYUNU BAŞLAT"a basar (3 kişi de
  hazırsa oyun otomatik başlar). İlk 10 öldürmeyi yapan kazanır, sonra yeniden
  karakter seçimine dönülür.

KARAKTERLER
  1 KANAT   : [F] ile UÇAR (7 sn, bar), kullanınca 20 sn bekleme
  2 ŞİMŞEK  : ÇOK hızlı koşar; koşarken birine çarparsa onu savurur (20 sn bekleme)
  3 MAYMUN  : 150 can; [F] ile muz fırlatır, muza basan kayar ve 2 sn yerde kalır
              (4 muzdan sonra 20 sn bekleme)

KONTROLLER
  W A S D        hareket          Boşluk   zıpla (kenara doğru basılı tut: tırmanır)
  Sol Shift      sprint           C / Sol Ctrl   çömel (koşarken çömel = kayma)
  Fare           bakış            Sol tık  ateş
  Sağ tık        nişan / SNIPER DÜRBÜNÜ
  1 Tabanca  2 AK-47  3 Pompalı  4 Sniper   (fare tekerleği de çalışır)
  R              şarjör değiştir
  G              bomba: basılı tut = güç, bırak = at
  F              karakter yeteneği (uçuş aç/kapat  ya da  muz fırlat)
  ESC            fareyi serbest bırak / devam
"""
import sys

try:
    from ursina import *            # noqa
    try:
        from ursina.color import Color
    except ImportError:
        Color = lambda r, g, b, a=1: color.rgba(r, g, b, a)   # noqa
    HAVE_URSINA = True
except ImportError:
    HAVE_URSINA = False

# NOT: ursina'dan SONRA import ediyoruz ki isimler ezilmesin
import math
import json
import queue
import socket
import threading
import random as rnd
import time as pytime
from types import SimpleNamespace as NS

PORT = 5555
MAX_PLAYERS = 3
KILL_LIMIT = 10

GRAVITY = 22.0
JUMP_V = 8.2
HALF = 0.35
H_STAND = 1.8
H_CROUCH = 1.1
H_SLIP = 0.55
SLIDE_TIME = 0.9

FLY_TIME = 7.0
FLY_CD = 20.0
RAM_CD = 20.0
BAN_MAX = 4
BAN_CD = 20.0
SLIP_TIME = 2.0

PCOLORS = [(0.92, 0.27, 0.27), (0.27, 0.55, 0.95), (0.31, 0.78, 0.39)]
SKIN = (0.92, 0.74, 0.6)

# ----------------------------------------------------------------------
#  KARAKTERLER
# ----------------------------------------------------------------------
CHARS = [
    dict(name="KANAT", hp=100, walk=5.5, sprint=9.0, col=(0.45, 0.75, 1.0),
         desc=["Can: 100", "[F] ile UÇAR", "Uçuş süresi: 7 sn", "Kullanınca 20 sn", "bekleme süresi var"]),
    dict(name="ŞİMŞEK", hp=100, walk=6.4, sprint=15.0, col=(1.0, 0.85, 0.2),
         desc=["Can: 100", "ÇOK hızlı koşar", "Koşarken çarptığı", "düşmanı savurur", "(20 sn bekleme)"]),
    dict(name="MAYMUN", hp=150, walk=5.2, sprint=8.4, col=(0.75, 0.5, 0.28),
         desc=["Can: 150 (en fazla)", "[F] ile muz atar", "Muza basan kayar,", "2 sn yerde kalır", "4 muz = 20 sn bekleme"]),
]

# ----------------------------------------------------------------------
#  SİLAHLAR (sunucu ve istemci ortak)
#  parts: (etiket, konum, boyut, renk, dönüş)   -> silah yerel uzayı: z ileri, orijin = kabze
# ----------------------------------------------------------------------
STEEL = (0.20, 0.21, 0.24)
DARK = (0.09, 0.09, 0.10)
GUNM = (0.15, 0.15, 0.17)
WOOD = (0.47, 0.29, 0.13)
WOOD2 = (0.36, 0.21, 0.09)
OLIVE = (0.23, 0.28, 0.20)
BRASS = (0.85, 0.65, 0.2)
WHITE = (0.9, 0.9, 0.9)
LENS = (0.3, 0.5, 0.9)

WEAPONS = [
    dict(name="Tabanca", dmg=22, cd=0.28, mag=12, res=10 ** 6, reload=1.2, auto=False,
         spread=0.006, bloom=0.0, pellets=1, push=1.0, kick=2.0, hkick=0.25,
         rng=20, minf=0.5, shell='brass', sdelay=0.0, flash=0.7,
         muz=(0, 0.05, 0.17), ej=(0.03, 0.06, 0.0), rh=(0, -0.05, -0.045), lh=(-0.05, -0.085, -0.035),
         ads=(0.0, -0.10, 0.40),
         parts=[
             ('slide', (0, 0.05, 0.03), (0.042, 0.05, 0.26), STEEL, (0, 0, 0)),
             ('', (0, 0.015, 0.04), (0.04, 0.035, 0.24), DARK, (0, 0, 0)),
             ('', (0, -0.065, -0.045), (0.04, 0.13, 0.06), DARK, (12, 0, 0)),
             ('', (0, -0.03, 0.04), (0.03, 0.018, 0.07), DARK, (0, 0, 0)),
             ('slide', (0, 0.083, 0.145), (0.01, 0.014, 0.012), WHITE, (0, 0, 0)),
             ('slide', (0, 0.083, -0.085), (0.03, 0.012, 0.012), DARK, (0, 0, 0)),
             ('', (0, 0.05, 0.165), (0.022, 0.022, 0.02), DARK, (0, 0, 0)),
         ]),
    dict(name="AK-47", dmg=12, cd=0.095, mag=30, res=90, reload=2.0, auto=True,
         spread=0.01, bloom=0.004, pellets=1, push=0.6, kick=1.1, hkick=0.4,
         rng=30, minf=0.5, shell='brass', sdelay=0.0, flash=1.0,
         muz=(0, 0.04, 0.9), ej=(0.035, 0.05, 0.18), rh=(0, -0.07, -0.015), lh=(-0.01, -0.02, 0.5),
         ads=(0.0, -0.11, 0.40),
         parts=[
             ('', (0, 0.025, 0.12), (0.05, 0.07, 0.40), STEEL, (0, 0, 0)),
             ('', (0, 0.068, 0.12), (0.044, 0.016, 0.36), DARK, (0, 0, 0)),
             ('', (0, 0.04, 0.58), (0.022, 0.022, 0.52), DARK, (0, 0, 0)),
             ('', (0, 0.085, 0.50), (0.022, 0.022, 0.40), STEEL, (0, 0, 0)),
             ('', (0, 0.03, 0.46), (0.056, 0.05, 0.30), WOOD, (0, 0, 0)),
             ('', (0, 0.075, 0.64), (0.052, 0.02, 0.15), WOOD2, (0, 0, 0)),
             ('', (0, 0.075, 0.80), (0.012, 0.045, 0.014), DARK, (0, 0, 0)),
             ('', (0, 0.04, 0.86), (0.034, 0.034, 0.07), DARK, (0, 0, 0)),
             ('', (0, 0.082, 0.18), (0.03, 0.02, 0.02), DARK, (0, 0, 0)),
             ('', (0, 0.0, -0.30), (0.045, 0.10, 0.42), WOOD, (-5, 0, 0)),
             ('', (0, -0.085, -0.01), (0.04, 0.12, 0.055), WOOD2, (14, 0, 0)),
             ('', (0, -0.04, 0.07), (0.03, 0.015, 0.1), DARK, (0, 0, 0)),
             ('mag', (0, -0.115, 0.14), (0.034, 0.14, 0.075), DARK, (-6, 0, 0)),
             ('mag', (0, -0.215, 0.165), (0.034, 0.10, 0.075), DARK, (-20, 0, 0)),
             ('', (0.035, 0.04, 0.12), (0.02, 0.02, 0.05), STEEL, (0, 0, 0)),
         ]),
    dict(name="Pompalı", dmg=10, cd=0.85, mag=6, res=24, reload=2.2, auto=False,
         spread=0.07, bloom=0.0, pellets=9, push=7.0, kick=6.0, hkick=0.6,
         rng=8, minf=0.25, shell='red', sdelay=0.45, flash=1.8,
         muz=(0, 0.06, 0.83), ej=(0.03, 0.04, 0.02), rh=(0, -0.05, -0.095), lh=(0, -0.035, 0.4),
         ads=(0.0, -0.105, 0.40),
         parts=[
             ('', (0, 0.03, 0.0), (0.05, 0.07, 0.32), GUNM, (0, 0, 0)),
             ('', (0, 0.06, 0.5), (0.026, 0.026, 0.62), DARK, (0, 0, 0)),
             ('', (0, 0.015, 0.46), (0.03, 0.03, 0.52), STEEL, (0, 0, 0)),
             ('pump', (0, 0.0, 0.4), (0.062, 0.055, 0.24), WOOD, (0, 0, 0)),
             ('', (0, 0.03, -0.34), (0.05, 0.10, 0.42), WOOD, (-4, 0, 0)),
             ('', (0, -0.07, -0.10), (0.04, 0.10, 0.05), WOOD2, (14, 0, 0)),
             ('', (0, 0.09, 0.78), (0.012, 0.02, 0.012), BRASS, (0, 0, 0)),
             ('', (0.027, 0.04, 0.02), (0.01, 0.025, 0.07), DARK, (0, 0, 0)),
         ]),
    dict(name="Sniper", dmg=90, cd=1.5, mag=5, res=15, reload=2.8, auto=False,
         spread=0.07, bloom=0.0, pellets=1, push=8.0, kick=5.0, hkick=0.3,
         rng=400, minf=1.0, shell='brass', sdelay=0.65, flash=1.5,
         muz=(0, 0.04, 1.22), ej=(0.03, 0.05, 0.0), rh=(0, -0.065, -0.09), lh=(0, -0.02, 0.35),
         ads=(0.0, -0.13, 0.40),
         parts=[
             ('', (0, 0.03, 0.05), (0.046, 0.07, 0.42), OLIVE, (0, 0, 0)),
             ('', (0, 0.04, 0.75), (0.026, 0.026, 0.8), DARK, (0, 0, 0)),
             ('', (0, 0.04, 1.17), (0.036, 0.036, 0.10), DARK, (0, 0, 0)),
             ('', (0, 0.108, 0.12), (0.04, 0.04, 0.30), DARK, (0, 0, 0)),
             ('', (0, 0.108, 0.29), (0.052, 0.052, 0.05), DARK, (0, 0, 0)),
             ('', (0, 0.108, -0.04), (0.046, 0.046, 0.04), DARK, (0, 0, 0)),
             ('', (0, 0.108, 0.318), (0.036, 0.036, 0.01), LENS, (0, 0, 0)),
             ('', (0, 0.075, 0.02), (0.03, 0.03, 0.02), DARK, (0, 0, 0)),
             ('', (0, 0.075, 0.2), (0.03, 0.03, 0.02), DARK, (0, 0, 0)),
             ('', (0, 0.0, -0.36), (0.05, 0.10, 0.5), OLIVE, (-3, 0, 0)),
             ('', (0, 0.06, -0.30), (0.04, 0.03, 0.2), WOOD2, (0, 0, 0)),
             ('bolt', (0.04, 0.045, 0.0), (0.05, 0.014, 0.014), STEEL, (0, 0, 0)),
             ('bolt', (0.07, 0.04, 0.0), (0.02, 0.02, 0.02), STEEL, (0, 0, 0)),
             ('mag', (0, -0.075, 0.08), (0.036, 0.1, 0.075), DARK, (0, 0, 0)),
             ('', (0, -0.07, -0.09), (0.04, 0.11, 0.05), OLIVE, (14, 0, 0)),
         ]),
]

# ----------------------------------------------------------------------
#  HARİTA (sabit, herkeste aynı)
# ----------------------------------------------------------------------
BOXES = []        # (minx, miny, minz, maxx, maxy, maxz)
BOX_COL = []
BOX_TEX = []
DECOR = []        # çarpışması olmayan süs nesneleri


def _box(cx, cz, sx, sy, sz, y0=0.0, col=(0.55, 0.55, 0.6), tex='white_cube'):
    BOXES.append((cx - sx / 2, y0, cz - sz / 2, cx + sx / 2, y0 + sy, cz + sz / 2))
    BOX_COL.append(col)
    BOX_TEX.append(tex)


def _decor(model, pos, scale, col, rot=(0, 0, 0)):
    DECOR.append(dict(m=model, p=pos, s=scale, c=col, r=rot))


def _wall(axis, fixed, a0, a1, h, th, gaps=(), col=(0.7, 0.5, 0.4), tex='brick'):
    """axis 'x': duvar x boyunca z=fixed'te; 'z': z boyunca x=fixed'te.
    gaps: (merkez, genişlik, y0, y1) boşluklar (kapı/pencere)."""
    def put(s, e, y0, y1):
        if e - s < 0.01 or y1 - y0 < 0.01:
            return
        c, L = (s + e) / 2, e - s
        if axis == 'x':
            _box(c, fixed, L, y1 - y0, th, y0=y0, col=col, tex=tex)
        else:
            _box(fixed, c, th, y1 - y0, L, y0=y0, col=col, tex=tex)
    cur = a0
    for (c, w, y0, y1) in sorted(gaps, key=lambda g: g[0] - g[1] / 2):
        s, e = c - w / 2, c + w / 2
        put(cur, s, 0, h)
        put(s, e, 0, y0)
        put(s, e, y1, h)
        cur = e
    put(cur, a1, 0, h)


def _house(cx, cz, w, d, h, gn=(), gs=(), gw=(), ge=(), col=(0.7, 0.5, 0.4), roof=(0.45, 0.2, 0.18)):
    th = 0.4
    x0, x1, z0, z1 = cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2
    _wall('x', z1, x0, x1, h, th, gn, col)
    _wall('x', z0, x0, x1, h, th, gs, col)
    _wall('z', x0, z0, z1, h, th, gw, col)
    _wall('z', x1, z0, z1, h, th, ge, col)
    _box(cx, cz, w + 0.6, 0.4, d + 0.6, y0=h, col=roof)


def _stairs(x, z, axis, sg, n, width, col=(0.6, 0.55, 0.5), sh=0.5, sl=1.0):
    for i in range(n):
        off = sg * (i * sl + sl / 2)
        if axis == 'x':
            _box(x + off, z, sl, sh * (i + 1), width, col=col)
        else:
            _box(x, z + off, width, sh * (i + 1), sl, col=col)


def build_map():
    BOXES.clear()
    BOX_COL.clear()
    BOX_TEX.clear()
    DECOR.clear()
    wallc = (0.66, 0.55, 0.45)
    for (cx, cz, sx, sz) in ((0, -30.5, 63, 1), (0, 30.5, 63, 1), (-30.5, 0, 1, 62), (30.5, 0, 1, 62)):
        _box(cx, cz, sx, 12, sz, col=wallc, tex='brick')

    # ---- merkez kule (platform, sütunlar, merdiven, korkuluk) ----
    plat = (0.62, 0.62, 0.68)
    _box(0, 0, 12, 0.5, 12, y0=2.5, col=plat)
    for sx in (-5.5, 5.5):
        for sz in (-5.5, 5.5):
            _box(sx, sz, 1, 2.5, 1, col=(0.4, 0.4, 0.45))
    for i in range(6):
        top = 0.5 * (i + 1)
        _box(0, -11.5 + i, 3, top, 1, col=(0.6, 0.55, 0.45))
        _box(0, 11.5 - i, 3, top, 1, col=(0.6, 0.55, 0.45))
    rail = (0.3, 0.3, 0.35)
    _box(-5.9, 0, 0.2, 0.9, 11.8, y0=3.0, col=rail)
    _box(5.9, 0, 0.2, 0.9, 11.8, y0=3.0, col=rail)
    for zz in (-5.9, 5.9):
        _box(-3.8, zz, 4.4, 0.9, 0.2, y0=3.0, col=rail)
        _box(3.8, zz, 4.4, 0.9, 0.2, y0=3.0, col=rail)
    _decor('cube', (0, 5.0, 0), (0.12, 4.0, 0.12), (0.8, 0.8, 0.8))
    _decor('cube', (0.55, 6.5, 0), (1.0, 0.6, 0.05), (0.85, 0.15, 0.15))

    # ---- ev A (depo) ----
    _house(-20, -19, 10, 8, 3.2,
           gn=[(-22, 1.4, 1.1, 2.2), (-18, 1.4, 1.1, 2.2)], gs=[(-20, 2.4, 0, 2.4)],
           gw=[(-19, 1.4, 1.1, 2.2)], ge=[(-19, 2.4, 0, 2.4)], col=(0.72, 0.5, 0.4))
    _stairs(-24, -7.7, 'z', -1, 7, 1.6)
    _box(-17.5, -21, 1.0, 1.6, 1.0, y0=3.6, col=(0.55, 0.3, 0.25))
    _box(-22, -18, 1.2, 0.8, 1.2, y0=3.6, col=WOOD)
    _box(-22, -21, 1.5, 1.0, 1.5, col=WOOD)
    _box(-18.5, -17.5, 2.2, 0.9, 1.0, col=(0.4, 0.3, 0.2))

    # ---- ev B ----
    _house(20, 19, 9, 8, 3.2,
           gn=[(18, 1.4, 1.1, 2.2), (22, 1.4, 1.1, 2.2)], gs=[(20, 2.4, 0, 2.4)],
           gw=[(19, 2.4, 0, 2.4)], ge=[(19, 1.4, 1.1, 2.2)], col=(0.5, 0.62, 0.7), roof=(0.25, 0.3, 0.4))
    _stairs(22, 7.7, 'z', 1, 7, 1.6)
    _box(20, 22.8, 9.0, 0.6, 0.2, y0=3.6, col=(0.4, 0.45, 0.5))
    _box(24.6, 19, 0.2, 0.6, 8.0, y0=3.6, col=(0.4, 0.45, 0.5))
    _box(22.5, 21, 1.5, 1.0, 1.5, col=WOOD)
    _box(18, 21.5, 2.2, 0.6, 1.1, col=(0.6, 0.6, 0.7))

    # ---- konteynerler ----
    def container(cx, cz, sx, sz, c, y0=0.0):
        _box(cx, cz, sx, 2.6, sz, y0=y0, col=c)
        _decor('cube', (cx, y0 + 1.3, cz), (sx + 0.03, 0.12, sz + 0.03), (0.9, 0.9, 0.9))
    container(-12, 24, 6.0, 2.4, (0.7, 0.2, 0.15))
    container(-10.5, 24, 6.0, 2.4, (0.2, 0.35, 0.7), y0=2.6)
    _box(-8.3, 24, 1.5, 1.2, 1.5, col=WOOD)
    container(8, -24, 2.4, 6.0, (0.2, 0.55, 0.3))
    container(12.5, -24, 2.4, 6.0, (0.85, 0.55, 0.15))
    container(12.5, -24, 2.4, 6.0, (0.5, 0.5, 0.55), y0=2.6)
    _box(8, -20.2, 1.5, 1.2, 1.5, col=WOOD)

    # ---- siperlikler: (x, z, sx, sy, sz) ----
    crates = [
        (-15, -12, 3, 2, 3), (14, -14, 2, 2, 2), (-18, 10, 2.5, 1.5, 2.5),
        (18, 12, 3, 2.5, 3), (-8, 20, 6, 1.2, 1.5), (22, -6, 2, 3, 5),
        (-5, -21, 2, 1, 2), (5, 21, 2, 1, 2), (-24, 2, 2, 1.2, 6),
        (13, 3, 2, 1, 2), (-13, -2, 2, 1, 2), (-26, 22, 2, 2, 2),
    ]
    for i, (x, z, sx, sy, sz) in enumerate(crates):
        k = 0.45 + 0.08 * (i % 4)
        _box(x, z, sx, sy, sz, col=(0.55, k, 0.3))
        _decor('cube', (x, sy + 0.02, z), (sx * 0.92, 0.05, sz * 0.92), (0.35, 0.22, 0.1))
    # kum torbaları
    sand = (0.72, 0.65, 0.45)
    for (x, z, sx, sz) in ((-9, 9, 4, 0.9), (9, -9, 4, 0.9), (9, 9, 0.9, 4), (-9, -9, 0.9, 4)):
        _box(x, z, sx, 1.1, sz, col=sand)
    # kayalar
    for (x, z) in ((-4, -15), (5, 15), (26, 12)):
        _box(x, z, 1.8, 0.9, 1.4, col=(0.45, 0.45, 0.48))
        _decor('cube', (x + 0.2, 0.85, z), (1.3, 0.7, 1.0), (0.5, 0.5, 0.52), (0, 25, 10))
        _decor('cube', (x - 0.3, 0.5, z + 0.2), (1.1, 0.8, 1.0), (0.4, 0.4, 0.43), (0, -30, 5))
    # variller
    for (x, z, c) in ((3, -14, (0.75, 0.15, 0.1)), (3.9, -13.5, (0.9, 0.7, 0.1)), (3.3, -12.8, (0.35, 0.4, 0.45)),
                      (-3.2, 14, (0.9, 0.7, 0.1)), (-4.1, 14.5, (0.75, 0.15, 0.1)),
                      (-17, -3, (0.35, 0.4, 0.45)), (-17.9, -3.4, (0.75, 0.15, 0.1))):
        _box(x, z, 0.8, 1.1, 0.8, col=c)
        _decor('cube', (x, 1.12, z), (0.84, 0.06, 0.84), (0.1, 0.1, 0.1))
        _decor('cube', (x, 0.55, z), (0.86, 0.07, 0.86), (0.12, 0.12, 0.12))
    # ağaçlar
    greens = [(0.2, 0.5, 0.2), (0.25, 0.58, 0.22), (0.18, 0.44, 0.18)]
    trees = [(-27, -9), (25, -19), (-27, 17), (27, 6), (-4, -27), (15, 28), (-20, 28),
             (-14, 13), (15, -8), (-3, 12), (27, -2), (-28, 8)]
    for i, (x, z) in enumerate(trees):
        _box(x, z, 0.5, 4.2, 0.5, col=(0.4, 0.26, 0.13))
        g = greens
        _decor('sphere', (x, 5.3, z), (3.4, 3.0, 3.4), g[i % 3])
        _decor('sphere', (x + 0.8, 4.6, z + 0.5), (2.4, 2.2, 2.4), g[(i + 1) % 3])
        _decor('sphere', (x - 0.7, 6.0, z - 0.4), (2.3, 2.1, 2.3), g[(i + 2) % 3])
    # lambalar
    for (x, z) in ((-10, -10), (10, 10), (-24, -8), (24, 8)):
        _decor('cube', (x, 2.5, z), (0.15, 5.0, 0.15), (0.2, 0.2, 0.22))
        _decor('sphere', (x, 5.1, z), (0.6, 0.6, 0.6), (1.0, 0.95, 0.6))
        _decor('sphere', (x, 5.1, z), (1.4, 1.4, 1.4), (1.0, 0.95, 0.6))
    # patikalar
    dirt = (0.58, 0.5, 0.36)
    _decor('cube', (0, 0.02, 0), (3.2, 0.03, 60), dirt)
    _decor('cube', (0, 0.025, 0), (60, 0.03, 3.2), dirt)
    # çalılar
    r = rnd.Random(11)
    for _ in range(30):
        side = r.choice('NSEW')
        a = r.uniform(-28, 28)
        d = r.uniform(28.6, 29.5)
        x, z = {'N': (a, d), 'S': (a, -d), 'E': (d, a), 'W': (-d, a)}[side]
        if abs(x) > 24 and abs(z) > 24:
            continue
        s = r.uniform(1.0, 2.0)
        _decor('sphere', (x, s * 0.35, z), (s, s * 0.7, s), r.choice(greens))
    # uzak dağlar ve bulutlar
    for i in range(10):
        a = i * math.pi / 5
        _decor('sphere', (math.cos(a) * 140, 8, math.sin(a) * 140), (90, 55, 90),
               (0.42, 0.5, 0.45) if i % 2 else (0.36, 0.44, 0.4))
    for i in range(7):
        a = i * 0.9 + 0.3
        _decor('sphere', (math.cos(a) * 80, 55 + (i % 3) * 6, math.sin(a) * 80), (34, 6, 18), (1, 1, 1))


build_map()

SPAWNS = [(-26, 0, -26), (26, 0, -26), (-26, 0, 26), (26, 0, 26), (0, 0, 0)]
PICKUP_SPOTS = [(-12, 0, 0), (12, 0, 0), (0, 0, -18), (0, 0, 18),
                (-20, 0, -6), (20, 0, 6), (-3, 3.0, -2), (-27, 0, 12), (27, 0, -12)]


# ----------------------------------------------------------------------
#  GEOMETRİ YARDIMCILARI
# ----------------------------------------------------------------------
def ray_aabb(o, d, mn, mx):
    tmin, tmax = 0.0, 1e9
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if o[i] < mn[i] or o[i] > mx[i]:
                return None
        else:
            t1 = (mn[i] - o[i]) / d[i]
            t2 = (mx[i] - o[i]) / d[i]
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return None
    return tmin


def ray_sphere(o, d, c, r):
    ox, oy, oz = o[0] - c[0], o[1] - c[1], o[2] - c[2]
    b = ox * d[0] + oy * d[1] + oz * d[2]
    cc = ox * ox + oy * oy + oz * oz - r * r
    disc = b * b - cc
    if disc < 0:
        return None
    t = -b - math.sqrt(disc)
    if t < 0:
        t = -b + math.sqrt(disc)
        if t < 0:
            return None
    return t


def world_t(o, d, maxd=250.0):
    """Işının haritaya (kutular + zemin) çarptığı en yakın mesafe."""
    best = maxd
    for b in BOXES:
        t = ray_aabb(o, d, (b[0], b[1], b[2]), (b[3], b[4], b[5]))
        if t is not None and t < best:
            best = t
    if d[1] < -1e-9:
        t = -o[1] / d[1]
        if 0 <= t < best:
            best = t
    return best


def sphere_hits(p, r):
    for b in BOXES:
        cx = min(max(p[0], b[0]), b[3])
        cy = min(max(p[1], b[1]), b[4])
        cz = min(max(p[2], b[2]), b[5])
        dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
        if dx * dx + dy * dy + dz * dz < r * r:
            return True
    return False


def boxes_at(x, y, z, h=H_STAND):
    out = []
    for b in BOXES:
        if (x + HALF > b[0] and x - HALF < b[3] and y + h > b[1] and y < b[4]
                and z + HALF > b[2] and z - HALF < b[5]):
            out.append(b)
    return out


def norm3(v):
    L = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return [v[0] / L, v[1] / L, v[2] / L]


def clampf(v, a, b):
    return max(a, min(b, v))


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


# ======================================================================
#  SUNUCU
# ======================================================================
class Conn:
    def __init__(self, sock):
        self.s = sock
        self.lk = threading.Lock()
        self.ok = True

    def send(self, obj):
        if not self.ok:
            return
        try:
            data = (json.dumps(obj, separators=(',', ':')) + '\n').encode()
            with self.lk:
                self.s.sendall(data)
        except OSError:
            self.ok = False


class Server:
    def __init__(self, port=PORT):
        self.port = port
        self.lock = threading.RLock()
        self.conns = {}
        self.pl = {}
        self.phase = 'lobby'
        self.nades = []
        self.nade_id = 0
        self.bans = []
        self.ban_id = 0
        self.pk = {}
        self.pk_id = 0
        self.pk_timer = 2.0
        self.over_t = 0.0
        self.running = True

    # ---------- ağ ----------
    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", self.port))
        s.listen(5)
        self.srv = s
        threading.Thread(target=self.accept_loop, daemon=True).start()
        threading.Thread(target=self.sim_loop, daemon=True).start()

    def accept_loop(self):
        while self.running:
            try:
                sock, addr = self.srv.accept()
            except OSError:
                return
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            c = Conn(sock)
            with self.lock:
                free = [i for i in range(MAX_PLAYERS) if i not in self.conns]
                if not free:
                    c.send({"t": "full"})
                    sock.close()
                    continue
                pid = free[0]
                self.conns[pid] = c
                self.pl[pid] = dict(id=pid, name=f"Oyuncu{pid + 1}", p=[0.0, 0.0, 0.0],
                                    v=[0, 0, 0], yaw=0.0, pitch=0.0, wi=1, hp=100.0, mhp=100.0,
                                    alive=False, sc=False, kills=0, deaths=0,
                                    respawn_t=0.3, inv=0.0,
                                    char=pid % len(CHARS), ready=False, hh=H_STAND,
                                    fl=False, sp=False, slip=0.0,
                                    ram_cd=0.0, bn=BAN_MAX, bn_cd=0.0)
            threading.Thread(target=self.reader, args=(pid, c), daemon=True).start()
            print(f"[sunucu] oyuncu {pid + 1} bağlandı: {addr[0]}")

    def reader(self, pid, c):
        buf = b''
        try:
            while True:
                chunk = c.s.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    with self.lock:
                        try:
                            self.handle(pid, msg)
                        except (KeyError, TypeError, ValueError, IndexError) as e:
                            print("[sunucu] hatalı mesaj:", e)
        except OSError:
            pass
        finally:
            self.drop(pid)

    def drop(self, pid):
        with self.lock:
            if pid in self.conns:
                try:
                    self.conns[pid].s.close()
                except OSError:
                    pass
                del self.conns[pid]
                self.pl.pop(pid, None)
                if not self.pl:
                    self.phase = 'lobby'
                    self.nades.clear()
                    self.bans.clear()
                    self.pk.clear()
                    self.over_t = 0.0
                self.send_lobby()
                print(f"[sunucu] oyuncu {pid + 1} ayrıldı")

    def bcast(self, obj):
        for c in list(self.conns.values()):
            c.send(obj)

    def send_lobby(self):
        self.bcast({"t": "lobby", "ph": self.phase,
                    "host": min(self.conns) if self.conns else -1,
                    "pl": [[i, p['name'], p['char'], p['ready']] for i, p in sorted(self.pl.items())]})

    def all_ready(self):
        return bool(self.pl) and all(p['ready'] for p in self.pl.values())

    def start_game(self):
        self.phase = 'play'
        self.over_t = 0.0
        self.nades.clear()
        self.bans.clear()
        self.pk.clear()
        self.pk_timer = 2.0
        for q in self.pl.values():
            q['kills'] = q['deaths'] = 0
            q['alive'] = False
            q['respawn_t'] = 0.6 + 0.3 * q['id']
        self.send_lobby()
        print("[sunucu] oyun başladı")

    def end_round(self):
        self.phase = 'lobby'
        for q in self.pl.values():
            q['kills'] = q['deaths'] = 0
            q['alive'] = False
            q['ready'] = False
            q['fl'] = False
            q['slip'] = 0.0
        self.nades.clear()
        self.bans.clear()
        self.pk.clear()
        self.bcast({"t": "reset"})
        self.send_lobby()

    # ---------- mesaj işleme ----------
    def handle(self, pid, m):
        p = self.pl.get(pid)
        if p is None:
            return
        t = m.get("t")
        if t == "hello":
            p['name'] = str(m.get("name", p['name']))[:14]
            self.conns[pid].send({"t": "welcome", "id": pid})
            self.send_lobby()
        elif t == "char":
            if self.phase == 'lobby' or not p['ready']:
                p['char'] = int(m['c']) % len(CHARS)
                p['mhp'] = float(CHARS[p['char']]['hp'])
                p['ready'] = False
                self.send_lobby()
        elif t == "ready":
            if not p['ready']:
                p['ready'] = True
                if self.phase == 'play':
                    p['respawn_t'] = 0.2
                self.send_lobby()
                if self.phase == 'lobby' and len(self.pl) == MAX_PLAYERS and self.all_ready():
                    self.start_game()
        elif t == "start":
            if self.phase == 'lobby' and pid == min(self.conns) and self.all_ready():
                self.start_game()
        elif t == "s":
            if p['alive']:
                p['p'] = [float(x) for x in m['p']]
                p['v'] = [float(x) for x in m['v']]
                p['yaw'] = float(m['yaw'])
                p['pitch'] = float(m['pitch'])
                p['wi'] = int(m['w']) % len(WEAPONS)
                p['sc'] = bool(m['sc'])
                p['hh'] = clampf(float(m.get('hh', H_STAND)), 0.4, 1.9)
                p['fl'] = bool(m.get('fl', False))
                p['sp'] = bool(m.get('sp', False))
        elif t == "shoot":
            self.do_shoot(pid, m)
        elif t == "nade":
            if p['alive'] and len(self.nades) < 20 and self.phase == 'play':
                self.nade_id += 1
                self.nades.append(dict(id=self.nade_id, p=[float(x) for x in m['o']],
                                       v=[float(x) for x in m['v']], fuse=2.6, owner=pid))
        elif t == "ban":
            if (p['char'] == 2 and p['alive'] and p['bn'] > 0 and p['bn_cd'] <= 0
                    and self.over_t <= 0 and len(self.bans) < 30):
                p['bn'] -= 1
                if p['bn'] <= 0:
                    p['bn_cd'] = BAN_CD
                self.ban_id += 1
                self.bans.append(dict(id=self.ban_id, p=[float(x) for x in m['o']],
                                      v=[float(x) for x in m['v']], landed=False,
                                      life=25.0, owner=pid))
                self.conns[pid].send({"t": "abil", "bn": p['bn'], "cd": p['bn_cd']})
        elif t == "fall":
            self.damage(pid, clampf(float(m['d']), 0, 200), None, "düşme")
        elif t == "pick":
            k = self.pk.get(m['id'])
            if k and p['alive']:
                d = math.dist(k['p'], p['p'])
                if d < 3.5:
                    del self.pk[m['id']]
                    if k['kind'] == 'health':
                        p['hp'] = min(p['mhp'], p['hp'] + 45)
                    self.bcast({"t": "picked", "id": m['id'], "by": pid, "kind": k['kind']})

    def do_shoot(self, pid, m):
        p = self.pl[pid]
        if not p['alive'] or self.over_t > 0 or p['slip'] > 0 or self.phase != 'play':
            return
        w = WEAPONS[int(m['w']) % len(WEAPONS)]
        o = [float(x) for x in m['o']]
        ends = []
        dmg_acc = {}
        for d in m['ds'][:12]:
            d = norm3([float(x) for x in d])
            best_t = world_t(o, d)
            victim, head = None, False
            for q in self.pl.values():
                if q is p or not q['alive']:
                    continue
                qp, hh = q['p'], q['hh']
                tb = ray_aabb(o, d, (qp[0] - 0.38, qp[1], qp[2] - 0.38),
                              (qp[0] + 0.38, qp[1] + hh * 0.8, qp[2] + 0.38))
                th = ray_sphere(o, d, (qp[0], qp[1] + hh - 0.18, qp[2]), 0.27)
                for tt, hd in ((tb, False), (th, True)):
                    if tt is not None and tt < best_t:
                        best_t, victim, head = tt, q, hd
            ends.append([round(o[0] + d[0] * best_t, 3), round(o[1] + d[1] * best_t, 3),
                         round(o[2] + d[2] * best_t, 3), 1 if victim is not None else 0])
            if victim is not None:
                mult = 1.0 if best_t <= w['rng'] else max(w['minf'], 1 - (best_t - w['rng']) / (w['rng'] * 2.0))
                dm = w['dmg'] * mult * (2 if head else 1)
                a = dmg_acc.setdefault(victim['id'], [0.0, False, d])
                a[0] += dm
                a[1] = a[1] or head
        self.bcast({"t": "shot", "id": pid, "o": o, "ends": ends, "w": int(m['w'])})
        for vid, (dm, head, d) in dmg_acc.items():
            self.conns[pid].send({"t": "hm", "head": head})
            kn = 2.0 + dm * 0.03
            self.bcast({"t": "imp", "id": vid, "v": [d[0] * kn, d[1] * kn * 0.4, d[2] * kn]})
            self.damage(vid, dm, pid, w['name'] + (" (KAFA)" if head else ""), head)

    # ---------- hasar / ölüm ----------
    def damage(self, vid, dmg, attacker, cause, head=False):
        q = self.pl.get(vid)
        if q is None or not q['alive'] or q['inv'] > 0 or self.over_t > 0 or self.phase != 'play':
            return
        q['hp'] -= dmg
        if q['hp'] <= 0:
            q['hp'] = 0
            q['alive'] = False
            q['fl'] = False
            q['slip'] = 0.0
            q['deaths'] += 1
            q['respawn_t'] = 4.0
            if attacker is None or attacker == vid:
                q['kills'] -= 1
                by = -1 if attacker is None else vid
            else:
                self.pl[attacker]['kills'] += 1
                by = attacker
            self.bcast({"t": "dead", "id": vid, "by": by, "cause": cause,
                        "p": q['p'], "head": head})
            if by >= 0 and by != vid and self.pl[by]['kills'] >= KILL_LIMIT:
                self.over_t = 8.0
                self.bcast({"t": "over", "w": by})

    def respawn(self, pid):
        q = self.pl[pid]
        ch = CHARS[q['char']]
        others = [o['p'] for o in self.pl.values() if o is not q and o['alive']]
        best = max(SPAWNS, key=lambda s: min([math.dist(s, o) for o in others] or [999]))
        q.update(p=list(map(float, best)), v=[0, 0, 0], hp=float(ch['hp']), mhp=float(ch['hp']),
                 alive=True, inv=2.5, hh=H_STAND, fl=False, sp=False, slip=0.0,
                 ram_cd=0.0, bn=BAN_MAX, bn_cd=0.0)
        self.bcast({"t": "respawn", "id": pid, "p": q['p'], "ch": q['char'], "mhp": q['mhp']})

    # ---------- simülasyon ----------
    def sim_loop(self):
        dt = 1 / 60
        nxt = pytime.perf_counter()
        tick = 0
        while self.running:
            with self.lock:
                try:
                    self.step(dt)
                    if tick % 2 == 0:
                        self.broadcast_world()
                except Exception as e:      # sunucu döngüsü asla ölmesin
                    print("[sunucu] simülasyon hatası:", repr(e))
            tick += 1
            nxt += dt
            sl = nxt - pytime.perf_counter()
            if sl > 0:
                pytime.sleep(sl)
            else:
                nxt = pytime.perf_counter()

    def step(self, dt):
        for q in self.pl.values():
            if q['inv'] > 0:
                q['inv'] -= dt
            if q['slip'] > 0:
                q['slip'] -= dt
            if q['ram_cd'] > 0:
                q['ram_cd'] -= dt
            if q['bn_cd'] > 0:
                q['bn_cd'] -= dt
                if q['bn_cd'] <= 0:
                    q['bn'] = BAN_MAX
            if not q['alive'] and q['ready'] and self.phase == 'play' and self.over_t <= 0:
                q['respawn_t'] -= dt
                if q['respawn_t'] <= 0:
                    self.respawn(q['id'])
        if self.over_t > 0:
            self.over_t -= dt
            if self.over_t <= 0:
                self.end_round()
        if self.phase != 'play':
            return
        # kasalar
        self.pk_timer -= dt
        if self.pk_timer <= 0:
            self.pk_timer = 7.0
            if len(self.pk) < 5:
                used = [k['spot'] for k in self.pk.values()]
                free = [i for i in range(len(PICKUP_SPOTS)) if i not in used]
                if free:
                    i = rnd.choice(free)
                    self.pk_id += 1
                    kind = rnd.choices(['ammo', 'health', 'bomb'], [45, 30, 25])[0]
                    self.pk[self.pk_id] = dict(kind=kind, spot=i, p=list(PICKUP_SPOTS[i]))
        # bombalar
        for g in self.nades[:]:
            self.step_nade(g, dt)
            g['fuse'] -= dt
            if g['fuse'] <= 0:
                self.nades.remove(g)
                self.explode(g)
        # muzlar
        for b in self.bans[:]:
            self.step_banana(b, dt)
            if b['life'] <= 0:
                self.bans.remove(b)
                continue
            for q in self.pl.values():
                if (not q['alive'] or q['id'] == b['owner'] or q['slip'] > 0 or q['inv'] > 0):
                    continue
                dx, dz = q['p'][0] - b['p'][0], q['p'][2] - b['p'][2]
                if (dx * dx + dz * dz < 0.45 ** 2
                        and q['p'][1] - 0.25 <= b['p'][1] <= q['p'][1] + q['hh']):
                    q['slip'] = SLIP_TIME
                    self.bans.remove(b)
                    self.bcast({"t": "slip", "id": q['id'], "d": SLIP_TIME, "by": b['owner']})
                    break
        self.check_ram()

    def check_ram(self):
        for q in self.pl.values():
            if q['char'] != 1 or not q['alive'] or q['ram_cd'] > 0 or not q['sp'] or q['slip'] > 0:
                continue
            sp = math.hypot(q['v'][0], q['v'][2])
            if sp < 10.0:
                continue
            ux, uz = q['v'][0] / sp, q['v'][2] / sp
            for o in self.pl.values():
                if o is q or not o['alive'] or o['inv'] > 0:
                    continue
                dx, dz = o['p'][0] - q['p'][0], o['p'][2] - q['p'][2]
                if dx * dx + dz * dz < 1.0 and abs(o['p'][1] - q['p'][1]) < 1.5 and dx * ux + dz * uz > 0:
                    q['ram_cd'] = RAM_CD
                    self.bcast({"t": "imp", "id": o['id'], "v": [ux * 26, 9, uz * 26]})
                    self.bcast({"t": "ram", "by": q['id'], "to": o['id'], "cd": RAM_CD})
                    self.damage(o['id'], 12, q['id'], "Çarpma")
                    break

    def step_nade(self, g, dt):
        R = 0.15
        g['v'][1] -= GRAVITY * dt
        for ax in (0, 2, 1):
            old = g['p'][ax]
            g['p'][ax] += g['v'][ax] * dt
            if sphere_hits(g['p'], R):
                g['p'][ax] = old
                g['v'][ax] *= -0.5
                if ax == 1:
                    g['v'][0] *= 0.85
                    g['v'][2] *= 0.85
                    if abs(g['v'][1]) < 1.5:
                        g['v'][1] = 0.0
        if g['p'][1] < R:
            g['p'][1] = R
            if g['v'][1] < 0:
                g['v'][1] = -g['v'][1] * 0.45 if abs(g['v'][1]) > 1.5 else 0.0
            g['v'][0] *= 0.9
            g['v'][2] *= 0.9
        g['p'][0] = clampf(g['p'][0], -29.7, 29.7)
        g['p'][2] = clampf(g['p'][2], -29.7, 29.7)

    def step_banana(self, b, dt):
        if b['landed']:
            b['life'] -= dt
            return
        R = 0.12
        b['v'][1] -= GRAVITY * 0.8 * dt
        for ax in (0, 2, 1):
            old = b['p'][ax]
            b['p'][ax] += b['v'][ax] * dt
            if sphere_hits(b['p'], R):
                b['p'][ax] = old
                if ax == 1 and b['v'][1] < 0:
                    b['landed'] = True
                else:
                    b['v'][ax] *= -0.25
        if b['p'][1] < 0.08:
            b['p'][1] = 0.08
            b['landed'] = True
        b['p'][0] = clampf(b['p'][0], -29.7, 29.7)
        b['p'][2] = clampf(b['p'][2], -29.7, 29.7)
        if b['landed']:
            b['v'] = [0.0, 0.0, 0.0]

    def explode(self, g):
        c = g['p']
        R = 8.0
        for q in self.pl.values():
            if not q['alive']:
                continue
            t = (q['p'][0], q['p'][1] + 0.9, q['p'][2])
            dv = [t[0] - c[0], t[1] - c[1], t[2] - c[2]]
            d = math.sqrt(dv[0] ** 2 + dv[1] ** 2 + dv[2] ** 2)
            if d >= R:
                continue
            f = 1 - d / R
            dirv = [dv[0] / d, dv[1] / d, dv[2] / d] if d > 0.01 else [0, 1, 0]
            if d > 0.5 and world_t(c, dirv, d) < d - 0.3:
                f *= 0.3            # siper arkasında hasar azalır
            if q['inv'] <= 0:
                self.bcast({"t": "imp", "id": q['id'],
                            "v": [dirv[0] * 24 * f, dirv[1] * 24 * f + 10 * f, dirv[2] * 24 * f]})
            self.damage(q['id'], 130 * f, g['owner'], "Bomba")
        for o in self.nades:
            dv = [o['p'][i] - c[i] for i in range(3)]
            d = math.sqrt(sum(x * x for x in dv))
            if 0.01 < d < R:
                f = 1 - d / R
                for i in range(3):
                    o['v'][i] += dv[i] / d * 14 * f
                o['v'][1] += 5 * f
        self.bcast({"t": "exp", "p": c})

    def broadcast_world(self):
        pl = []
        for q in self.pl.values():
            pl.append([q['id'], round(q['p'][0], 3), round(q['p'][1], 3), round(q['p'][2], 3),
                       round(q['yaw'], 2), round(q['pitch'], 2), q['wi'], round(q['hp'], 1),
                       q['alive'], q['sc'], q['kills'], q['deaths'], q['inv'] > 0,
                       q['char'], round(q['hh'], 2), q['fl'], q['slip'] > 0, q['mhp'], q['sp']])
        ng = [[g['id'], round(g['p'][0], 3), round(g['p'][1], 3), round(g['p'][2], 3)] for g in self.nades]
        bn = [[b['id'], round(b['p'][0], 3), round(b['p'][1], 3), round(b['p'][2], 3), b['landed']]
              for b in self.bans]
        pk = [[i, k['kind']] + k['p'] for i, k in self.pk.items()]
        self.bcast({"t": "w", "pl": pl, "ng": ng, "bn": bn, "pk": pk})


# ======================================================================
#  İSTEMCİ AĞ KATMANI
# ======================================================================
class NetClient:
    def __init__(self, host, port, name):
        self.sock = socket.create_connection((host, port), timeout=6)
        self.sock.settimeout(None)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.q = queue.Queue()
        self.lk = threading.Lock()
        self.ok = True
        threading.Thread(target=self.rx, daemon=True).start()
        self.send({"t": "hello", "name": name})

    def send(self, obj):
        if not self.ok:
            return
        try:
            with self.lk:
                self.sock.sendall((json.dumps(obj, separators=(',', ':')) + '\n').encode())
        except OSError:
            self.ok = False

    def rx(self):
        buf = b''
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    if line:
                        try:
                            self.q.put(json.loads(line))
                        except ValueError:
                            pass
        except OSError:
            pass
        self.ok = False
        self.q.put({"t": "disc"})


# ======================================================================
#  İSTEMCİ OYUN (Ursina)
# ======================================================================
if HAVE_URSINA:

    def col(r, g, b, a=1.0):
        return Color(r, g, b, a)

    def dir_from(yaw_deg, pitch_deg):
        y, p = math.radians(yaw_deg), math.radians(pitch_deg)
        return [math.sin(y) * math.cos(p), -math.sin(p), math.cos(y) * math.cos(p)]

    def perturb(d, spread):
        if spread <= 0:
            return d
        r = [d[2], 0.0, -d[0]]
        r = norm3(r) if (abs(r[0]) + abs(r[2])) > 1e-6 else [1, 0, 0]
        u = [d[1] * r[2] - d[2] * r[1], d[2] * r[0] - d[0] * r[2], d[0] * r[1] - d[1] * r[0]]
        a, b = rnd.gauss(0, spread), rnd.gauss(0, spread)
        return norm3([d[i] + r[i] * a + u[i] * b for i in range(3)])

    def limb(parent, a, b, t, c):
        """a'dan b'ye uzanan kalınlığı t olan kutu (kol/bacak)."""
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        L = math.sqrt(dx * dx + dy * dy + dz * dz) or 0.01
        e = Entity(parent=parent, model='cube', color=col(*c), scale=(t, t, L),
                   position=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
        e.rotation_y = math.degrees(math.atan2(dx, dz))
        e.rotation_x = -math.degrees(math.atan2(dy, math.hypot(dx, dz)))
        return e

    def make_arms(parent, rs, ls, rh, lh, sleeve, th=0.075):
        out = []
        for s, h in ((rs, rh), (ls, lh)):
            wr = [s[i] + (h[i] - s[i]) * 0.78 for i in range(3)]
            out.append(limb(parent, s, wr, th, sleeve))
            out.append(limb(parent, wr, h, th * 0.8, SKIN))
            out.append(Entity(parent=parent, model='cube', color=col(*SKIN), position=tuple(h),
                              scale=(th * 1.1, th * 1.0, th * 1.2)))
        return out

    def build_gun(parent, wi):
        w = WEAPONS[wi]
        root = Entity(parent=parent)
        tags = {}
        for (tag, p, s, c, r) in w['parts']:
            e = Entity(parent=root, model='cube', color=col(*c), position=p, scale=s, rotation=r)
            e.bp = Vec3(*p)
            if tag:
                tags.setdefault(tag, []).append(e)
        return root, tags

    def make_flash(parent):
        f = Entity(parent=parent, enabled=False)
        Entity(parent=f, model='sphere', color=col(1, 0.95, 0.7, 1), scale=0.07)
        for rz in (0, 45, 90, 135):
            Entity(parent=f, model='cube', color=col(1, 0.75, 0.25, 1), scale=(0.2, 0.012, 0.012), rotation_z=rz)
        Entity(parent=f, model='cube', color=col(1, 0.6, 0.15, 0.9), scale=(0.035, 0.035, 0.28), z=0.15)
        return f

    # ------------------------------------------------------------------
    #  SES (kod ile üretilen basit efektler; olmazsa sessiz devam eder)
    # ------------------------------------------------------------------
    class SFX:
        def __init__(self):
            self.snd = {}
            self.idx = {}
            self.ok = False
            try:
                import wave
                import struct
                import tempfile
                import os
                from panda3d.core import Filename
                ldr = getattr(application, 'base', None)
                ldr = ldr.loader if ldr is not None else base.loader       # noqa
                d = tempfile.mkdtemp(prefix="savas3d_")
                R = 22050
                rg = rnd.Random(5)

                def nz():
                    return rg.uniform(-1, 1)

                def shot(nk, tk, tf, amp=1.0):
                    return lambda t: amp * (nz() * math.exp(-t * nk) * 0.8
                                            + math.sin(2 * math.pi * tf * t) * math.exp(-t * tk) * 0.6)

                specs = {
                    'shot0': (0.25, shot(28, 20, 140, 0.9)),
                    'shot1': (0.3, shot(22, 16, 100)),
                    'shot2': (0.6, shot(9, 7, 70)),
                    'shot3': (0.9, shot(6, 5, 55)),
                    'reload': (0.2, lambda t: nz() * 0.5 * math.exp(-t * 60) if t < 0.06
                               else (nz() * 0.7 * math.exp(-(t - 0.1) * 70) if t > 0.1 else 0.0)),
                    'boom': (1.2, lambda t: nz() * math.exp(-t * 4) * 0.7
                             + math.sin(2 * math.pi * 45 * t) * math.exp(-t * 3) * 0.8),
                    'hit': (0.08, lambda t: math.sin(2 * math.pi * 1500 * t) * math.exp(-t * 50) * 0.5),
                    'slip': (0.4, lambda t: math.sin(2 * math.pi * (300 + 500 * t) * t) * 0.5 * math.exp(-t * 4)),
                    'click': (0.05, lambda t: nz() * math.exp(-t * 90) * 0.5),
                    'whoosh': (0.5, lambda t: nz() * 0.4 * math.sin(math.pi * t / 0.5)),
                }
                for name, (dur, fn) in specs.items():
                    n = int(R * dur)
                    data = bytearray()
                    for i in range(n):
                        v = clampf(fn(i / R), -1.0, 1.0)
                        data += struct.pack('<h', int(v * 30000))
                    path = os.path.join(d, name + ".wav")
                    with wave.open(path, 'wb') as f:
                        f.setnchannels(1)
                        f.setsampwidth(2)
                        f.setframerate(R)
                        f.writeframes(bytes(data))
                    self.snd[name] = [ldr.loadSfx(Filename.fromOsSpecific(path)) for _ in range(3)]
                    self.idx[name] = 0
                self.ok = True
            except Exception as e:      # noqa
                print("(ses efektleri devre dışı:", repr(e), ")")

        def play(self, name, vol=1.0):
            if not self.ok or name not in self.snd:
                return
            try:
                lst = self.snd[name]
                s = lst[self.idx[name] % len(lst)]
                self.idx[name] += 1
                s.setVolume(clampf(vol, 0.0, 1.0))
                s.play()
            except Exception:           # noqa
                pass

    # ------------------------------------------------------------------
    #  UZAKTAKİ OYUNCU MODELİ
    # ------------------------------------------------------------------
    class Peer:
        def __init__(self, pid):
            self.pid = pid
            c = PCOLORS[pid % 3]
            self.pc = c
            self.root = Entity()
            self.body = Entity(parent=self.root)
            B = self.body
            self.torso = Entity(parent=B, model='cube', color=col(*c), scale=(0.62, 0.75, 0.34), y=1.15)
            Entity(parent=B, model='cube', color=col(0.12, 0.12, 0.16), scale=(0.6, 0.12, 0.36), y=0.8)
            Entity(parent=B, model='sphere', color=col(*SKIN), scale=0.4, y=1.68)
            Entity(parent=B, model='cube', color=col(0.1, 0.1, 0.12), scale=(0.42, 0.12, 0.1), y=1.7, z=0.17)
            self.legs = []
            for sx in (-0.15, 0.15):
                piv = Entity(parent=B, position=(sx, 0.8, 0))
                Entity(parent=piv, model='cube', color=col(0.14, 0.14, 0.2), scale=(0.24, 0.8, 0.26), y=-0.4)
                Entity(parent=piv, model='cube', color=col(0.08, 0.08, 0.08), scale=(0.26, 0.12, 0.36),
                       y=-0.77, z=0.04)
                self.legs.append(piv)
            self.gun_piv = Entity(parent=B, y=1.3)
            self.gun_root = None
            self.arm_ents = []
            self.muzzle = Entity(parent=self.gun_piv)
            self.flash = make_flash(self.muzzle)
            self.acc = []
            self.wings = []
            self.bar = Entity(parent=self.root, model='quad', billboard=True, y=2.3,
                              scale=(0.9, 0.09), color=col(0.1, 0.1, 0.1))
            self.fg = Entity(parent=self.bar, model='quad', origin=(-.5, 0), x=-0.5, z=-0.01,
                             scale=(1, 0.8), color=col(0.3, 0.9, 0.3))
            self.tp = [0, 0, 0]
            self.yaw = 0.0
            self.pitch = 0.0
            self.wi = -1
            self.char = -1
            self.hh = H_STAND
            self.fl = False
            self.sl = False
            self.sp = False
            self.flash_t = 0.0
            self.phase = 0.0
            self.tilt = 0.0
            self.t = 0.0
            self.first = True

        def set_char(self, ch):
            if ch == self.char:
                return
            self.char = ch
            for e in self.acc:
                destroy(e)
            self.acc = []
            self.wings = []
            B = self.body
            self.torso.scale = (0.62, 0.75, 0.34)
            if ch == 0:
                for sg in (-1, 1):
                    piv = Entity(parent=B, position=(sg * 0.2, 1.3, -0.2))
                    Entity(parent=piv, model='cube', color=col(0.95, 0.97, 1.0), scale=(0.8, 0.5, 0.04),
                           position=(sg * 0.4, 0.15, 0))
                    self.wings.append(piv)
                    self.acc.append(piv)
                self.acc.append(Entity(parent=B, model='cube', color=col(0.4, 0.75, 1.0),
                                       scale=(0.43, 0.07, 0.43), y=1.8))
            elif ch == 1:
                self.acc.append(Entity(parent=B, model='cube', color=col(1, 0.85, 0.15),
                                       scale=(0.12, 0.76, 0.36), y=1.15))
                self.acc.append(Entity(parent=B, model='cube', color=col(1, 0.85, 0.15),
                                       scale=(0.44, 0.1, 0.1), y=1.72, z=0.19))
                self.acc.append(Entity(parent=B, model='cube', color=col(0.9, 0.2, 0.15),
                                       scale=(0.45, 0.06, 0.45), y=1.8))
            else:
                self.torso.scale = (0.78, 0.85, 0.4)
                for sg in (-1, 1):
                    self.acc.append(Entity(parent=B, model='sphere', color=col(0.45, 0.28, 0.14),
                                           scale=0.2, position=(sg * 0.24, 1.82, 0)))
                self.acc.append(Entity(parent=B, model='cube', color=col(0.5, 0.35, 0.2),
                                       scale=(0.34, 0.45, 0.15), position=(0, 1.2, -0.28)))
                self.acc.append(Entity(parent=B, model='cube', color=col(1, 0.9, 0.2),
                                       scale=(0.1, 0.5, 0.1), position=(0.1, 1.45, -0.34), rotation_z=20))

        def set_weapon(self, wi):
            if wi == self.wi:
                return
            self.wi = wi
            w = WEAPONS[wi]
            for e in self.arm_ents:
                destroy(e)
            if self.gun_root is not None:
                destroy(self.gun_root)
            gp = (0.27, -0.12, 0.28)
            gr, _ = build_gun(self.gun_piv, wi)
            gr.position = gp
            self.gun_root = gr
            rh = [gp[i] + w['rh'][i] for i in range(3)]
            lh = [gp[i] + w['lh'][i] for i in range(3)]
            self.arm_ents = make_arms(self.gun_piv, (0.38, 0.0, 0.0), (-0.38, 0.0, 0.0), rh, lh,
                                      tuple(v * 0.75 for v in self.pc), 0.14)
            self.muzzle.position = Vec3(gp[0] + w['muz'][0], gp[1] + w['muz'][1], gp[2] + w['muz'][2])
            k = w['flash'] * 1.3
            self.flash.scale = (k, k, k)

        def fire(self):
            self.flash_t = 0.06
            self.flash.rotation_z = rnd.uniform(0, 90)

        def update(self, dt):
            r = self.root
            self.t += dt
            if self.first:
                r.position = Vec3(*self.tp)
                self.first = False
            k = min(1.0, dt * 14)
            cur = r.position
            nx = cur.x + (self.tp[0] - cur.x) * k
            ny = cur.y + (self.tp[1] - cur.y) * k
            nz = cur.z + (self.tp[2] - cur.z) * k
            spd = math.hypot(nx - cur.x, nz - cur.z) / max(dt, 1e-4)
            r.position = Vec3(nx, ny, nz)
            diff = (self.yaw - r.rotation_y + 180) % 360 - 180
            r.rotation_y += diff * k
            self.gun_piv.rotation_x = self.pitch
            self.phase += min(spd, 16) * dt * 1.2
            sw = math.sin(self.phase) * 35 if spd > 0.5 and not self.fl else 0
            self.legs[0].rotation_x = sw
            self.legs[1].rotation_x = -sw
            # yatma (muz) ve çömelme
            self.tilt += ((-82 if self.sl else 0) - self.tilt) * min(1.0, dt * 9)
            self.body.rotation_x = self.tilt
            self.body.y = 0.22 * abs(self.tilt) / 82
            self.body.scale_y = 1.0 if self.sl else clampf(self.hh / H_STAND, 0.55, 1.0)
            # kanatlar
            for i, wp in enumerate(self.wings):
                sg = -1 if i == 0 else 1
                ang = 65 + math.sin(self.t * 18) * 15 if self.fl else 22
                wp.rotation_z = sg * ang
            if self.flash_t > 0:
                self.flash_t -= dt
            self.flash.enabled = self.flash_t > 0

        def destroy(self):
            destroy(self.root)

    # ------------------------------------------------------------------
    #  OYUN
    # ------------------------------------------------------------------
    class Arena(Entity):
        def __init__(self, net, myname):
            super().__init__()
            self.net = net
            self.myname = myname
            S = self.S = NS()
            S.pid = None
            S.roster = {}
            S.lobby = []
            S.phase = 'lobby'
            S.host = -1
            S.entered = False
            S.ready = False
            S.char_sel = 0
            S.char = 0
            S.mhp = 100.0
            S.peers = {}
            S.nade_ents = {}
            S.ban_ents = {}
            S.pk_ents = {}
            S.pk_sent = set()
            S.fx = []
            S.feed = []
            S.t = 0.0
            S.p = [0.0, 0.0, 0.0]
            S.v = [0.0, 0.0, 0.0]
            S.yaw = 0.0
            S.pitch = 0.0
            S.on_ground = False
            S.alive = False
            S.hp = 100.0
            S.hp_prev = 100.0
            S.stamina = 100.0
            S.locked = False
            S.sprint_delay = 0.0
            S.hh = H_STAND
            S.eye_y = H_STAND - 0.15
            S.slide_t = 0.0
            S.slide_dir = (0.0, 1.0)
            S.slide_spd = 0.0
            S.crouch_prev = False
            S.coyote = 0.0
            S.jump_buf = 0.0
            S.flying = False
            S.fly_t = FLY_TIME
            S.ab_cd = 0.0
            S.bn = BAN_MAX
            S.ban_cool = 0.0
            S.nofall = 0.0
            S.slip_t = 0.0
            S.land = 0.0
            S.bob = 0.0
            S.roll = 0.0
            S.strafe = 0.0
            S.wi = 1
            S.ammo = [dict(mag=w['mag'], res=w['res']) for w in WEAPONS]
            S.cool = 0.0
            S.reload_t = 0.0
            S.want_reload = False
            S.grenades = 3
            S.charge = 0.0
            S.bloom = 0.0
            S.kickv = 0.0
            S.vm_kick = 0.0
            S.shots = 0
            S.shot_gap = 1.0
            S.shell_t = 0.0
            S.fire_edge = False
            S.scoped = False
            S.ads = False
            S.ads_k = 0.0
            S.spr_k = 0.0
            S.shake = 0.0
            S.flash = 0.0
            S.hitmark = 0.0
            S.hit_head = False
            S.send_t = 0.0
            S.paused = False
            S.over_msg = ""
            S.scores = {}
            S.death_t = 0.0
            S.muzzle_t = 0.0
            S.dead_by = ""
            S.cross_gap = 0.012
            S.leg_phase = 0.0
            self.sprinting = False
            self.vm_parts = []
            self.vm_tags = {}
            self.sfx = SFX()
            self.build_world()
            self.build_hud()
            self.build_lobby()
            self.pivot = Entity()
            camera.parent = self.pivot
            camera.position = (0, 0, 0)
            camera.rotation = (0, 0, 0)
            camera.fov = 90
            self.vm = Entity(parent=camera, position=(0.22, -0.2, 0.55))
            self.vm_flash = make_flash(self.vm)
            self.vm_muz = Entity(parent=self.vm)
            self.vm_eject = Entity(parent=self.vm)
            self.build_legs()
            self.set_weapon(1)
            self.hud.enabled = False
            mouse.locked = False

        # ------------------ dünya ------------------
        def build_world(self):
            Sky()
            try:
                scene.fog_color = col(0.72, 0.82, 0.95)
                scene.fog_density = (60, 220)
            except Exception:       # noqa
                pass
            Entity(model='plane', scale=(500, 1, 500), color=col(0.22, 0.38, 0.22), y=-0.03)
            Entity(model='plane', scale=(66, 1, 66), texture='grass', texture_scale=(22, 22),
                   color=col(0.55, 0.78, 0.5))
            for b, c, tx in zip(BOXES, BOX_COL, BOX_TEX):
                sx, sy, sz = b[3] - b[0], b[4] - b[1], b[5] - b[2]
                if tx == 'brick':
                    ts = (max(1, round(max(sx, sz) / 2)), max(1, round(sy / 1.2)))
                else:
                    ts = (max(1, round(max(sx, sz))), max(1, round(sy)))
                Entity(model='cube', texture=tx, texture_scale=ts,
                       position=((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2),
                       scale=(sx, sy, sz), color=col(*c))
            for d in DECOR:
                Entity(model=d['m'], position=d['p'], scale=d['s'], color=col(*d['c']), rotation=d['r'])

        # ------------------ HUD ------------------
        def build_hud(self):
            self.hud = Entity(parent=camera.ui)
            hud = self.hud

            def quad(x, y, w, h, c, z=0.0, origin=(0, 0)):
                return Entity(parent=hud, model='quad', position=(x, y, z), scale=(w, h), color=c, origin=origin)

            def txt(s, x, y, sc=1.2, c=None, origin=(-.5, .5)):
                t = Text(parent=hud, text=s, position=(x, y), scale=sc, origin=origin, color=c or color.white)
                t._cache = s
                return t

            self.flash_q = quad(0, 0, 3, 3, col(1, 0, 0, 0), z=0.6)
            self.gr_bg = quad(-0.85, -0.365, 0.2, 0.01, col(0, 0, 0, 0.5), origin=(-.5, 0))
            self.gr_fg = quad(-0.85, -0.365, 0.0, 0.01, col(1, 0.6, 0.2), origin=(-.5, 0))
            self.hp_bg = quad(-0.85, -0.405, 0.34, 0.03, col(0.15, 0, 0, 0.8), origin=(-.5, 0))
            self.hp_fg = quad(-0.85, -0.405, 0.34, 0.03, col(0.3, 0.9, 0.3), origin=(-.5, 0))
            self.st_bg = quad(-0.85, -0.445, 0.34, 0.015, col(0, 0, 0.2, 0.8), origin=(-.5, 0))
            self.st_fg = quad(-0.85, -0.445, 0.34, 0.015, col(0.3, 0.7, 1), origin=(-.5, 0))
            self.ab_bg = quad(-0.85, -0.478, 0.34, 0.02, col(0, 0, 0, 0.7), origin=(-.5, 0))
            self.ab_fg = quad(-0.85, -0.478, 0.34, 0.02, col(0.3, 0.9, 0.5), origin=(-.5, 0))
            self.t_hp = txt("100", -0.50, -0.39, 1.0)
            self.t_ab = txt("", -0.50, -0.468, 0.9, col(0.8, 1, 0.9))
            self.t_weapon = txt("", 0.85, -0.40, 1.5, origin=(.5, .5))
            self.t_ammo = txt("", 0.85, -0.44, 1.2, col(1, 0.9, 0.5), origin=(.5, .5))
            self.t_bomb = txt("", -0.85, -0.34, 1.0, col(0.7, 1, 0.6))
            self.t_feed = txt("", -0.88, 0.47, 1.0)
            self.t_score = txt("", 0.88, 0.47, 1.0, origin=(.5, .5))
            self.t_center = txt("", 0, 0.2, 2.5, origin=(0, 0))
            self.t_dead = txt("", 0, 0.05, 2.0, col(1, 0.4, 0.4), origin=(0, 0))
            self.t_help = txt("", 0, -0.2, 1.2, col(1, 1, 1), origin=(0, 0))
            self.t_char = txt("", -0.88, -0.30, 0.9, col(1, 1, 1))
            # artı (silahın saçılmasına göre açılır)
            self.cross = []
            for (dx, dy, w, h) in ((1, 0, 0.012, 0.002), (-1, 0, 0.012, 0.002),
                                   (0, 1, 0.002, 0.012), (0, -1, 0.002, 0.012)):
                e = quad(dx * 0.012, dy * 0.012, w, h, col(1, 1, 1, 0.9))
                e.dirv = (dx, dy)
                self.cross.append(e)
            self.hit_q = Text(parent=hud, text="X", position=(0, 0), origin=(0, 0), scale=2.0, color=color.white)
            self.hit_q.enabled = False
            # dürbün
            self.scope = []
            blk = col(0, 0, 0, 1)
            self.scope.append(quad(-1.45, 0, 2, 2, blk, z=0.3))
            self.scope.append(quad(1.45, 0, 2, 2, blk, z=0.3))
            self.scope.append(quad(0, 0.95, 4, 1, blk, z=0.3))
            self.scope.append(quad(0, -0.95, 4, 1, blk, z=0.3))
            self.scope.append(quad(0, 0, 0.9, 0.0025, col(0, 0, 0, 0.9), z=0.2))
            self.scope.append(quad(0, 0, 0.0025, 0.9, col(0, 0, 0, 0.9), z=0.2))
            for k in range(1, 5):
                for sgn in (-1, 1):
                    self.scope.append(quad(sgn * k * 0.08, 0, 0.002, 0.02, col(0, 0, 0, 0.9), z=0.2))
                    self.scope.append(quad(0, sgn * k * 0.08, 0.02, 0.002, col(0, 0, 0, 0.9), z=0.2))
            self.scope.append(quad(0, 0, 0.006, 0.006, col(1, 0, 0, 1), z=0.1))
            for e in self.scope:
                e.enabled = False

        def set_text(self, t, s):
            if t._cache != s:
                t.text = s
                t._cache = s

        # ------------------ karakter seçim ekranı ------------------
        def build_lobby(self):
            L = self.lobby = Entity(parent=camera.ui)
            Entity(parent=L, model='quad', scale=(3, 3), color=col(0.03, 0.04, 0.07, 0.8), z=0.5)
            Text(parent=L, text="KARAKTERİNİ SEÇ", position=(0, 0.43), origin=(0, 0), scale=2.6, color=color.white)
            Text(parent=L, text="1 / 2 / 3 ya da tıkla   -   ENTER: HAZIR", position=(0, 0.37),
                 origin=(0, 0), scale=1.0, color=col(0.8, 0.8, 0.8))
            self.sel_frame = Entity(parent=L, model='quad', color=col(1, 0.9, 0.3, 1), scale=(0.335, 0.575), z=0.02)
            xs = (-0.62, -0.28, 0.06)
            self.cards = []
            for i, C in enumerate(CHARS):
                x = xs[i]
                b = Button(parent=L, scale=(0.31, 0.55), position=(x, 0.1), color=col(0.1, 0.12, 0.2, 0.97),
                           on_click=(lambda i=i: self.pick_char(i)))
                self.cards.append(b)
                Text(parent=L, text=f"{i + 1}  {C['name']}", position=(x, 0.3), origin=(0, 0),
                     scale=1.5, color=col(*C['col']), z=-0.02)
                Entity(parent=L, model='quad', color=col(*C['col']), scale=(0.09, 0.09),
                       position=(x, 0.22), z=-0.02)
                Text(parent=L, text="\n".join(C['desc']), position=(x - 0.13, 0.13), origin=(-.5, .5),
                     scale=0.85, color=col(0.9, 0.9, 0.9), z=-0.02)
            self.btn_ready = Button(parent=L, text="HAZIR  (Enter)", scale=(0.3, 0.07), position=(-0.45, -0.3),
                                    color=col(0.1, 0.5, 0.2, 1), on_click=self.on_ready)
            self.btn_start = Button(parent=L, text="OYUNU BAŞLAT  (H)", scale=(0.34, 0.07), position=(-0.1, -0.3),
                                    color=col(0.6, 0.35, 0.1, 1), on_click=self.on_start)
            self.btn_start.enabled = False
            self.t_players = Text(parent=L, text="", position=(0.33, 0.3), origin=(-.5, .5), scale=1.0,
                                  color=color.white)
            self.t_players._cache = ""
            self.t_lob = Text(parent=L, text="", position=(0, -0.4), origin=(0, 0), scale=1.0,
                              color=col(1, 0.9, 0.5))
            self.t_lob._cache = ""
            self._ready_label = "HAZIR  (Enter)"

        def pick_char(self, i):
            S = self.S
            if S.entered:
                return
            S.char_sel = i % len(CHARS)
            S.ready = False
            self.net.send({"t": "char", "c": S.char_sel})

        def on_ready(self):
            S = self.S
            if S.pid is None or S.entered or S.ready:
                return
            S.ready = True
            self.net.send({"t": "ready"})

        def on_start(self):
            S = self.S
            if S.pid is not None and S.pid == S.host and S.phase == 'lobby':
                self.net.send({"t": "start"})

        def update_lobby(self, dt):
            S = self.S
            a = S.t * 0.12
            self.pivot.position = Vec3(math.sin(a) * 42, 16, math.cos(a) * 42)
            self.pivot.look_at(Vec3(0, 2, 0))
            camera.position = Vec3(0, 0, 0)
            camera.fov = 75
            self.vm.enabled = False
            self.legs_root.enabled = False
            self.sel_frame.x = (-0.62, -0.28, 0.06)[S.char_sel % 3]
            self.sel_frame.y = 0.1
            lines = ["OYUNCULAR", ""]
            allr = bool(S.lobby)
            for pid, name, ch, rd in S.lobby:
                me = " (sen)" if pid == S.pid else ""
                lines.append(f"{name}{me}")
                lines.append(f"   {CHARS[ch % 3]['name']}  -  {'HAZIR' if rd else 'seçiyor...'}")
                allr = allr and rd
            lines.append("")
            lines.append(f"Oyuncu sayısı: {len(S.lobby)} / {MAX_PLAYERS}")
            self.set_text(self.t_players, "\n".join(lines))
            lab = "HAZIR ✓  (bekleniyor)" if S.ready else "HAZIR  (Enter)"
            if lab != self._ready_label:
                self.btn_ready.text = lab
                self._ready_label = lab
            host = (S.pid is not None and S.pid == S.host and S.phase == 'lobby')
            self.btn_start.enabled = bool(host and allr)
            if S.over_msg and (S.over_msg.endswith("KOPTU") or S.over_msg.startswith("SUNUCU DOLU")):
                msg = S.over_msg
            elif S.pid is None:
                msg = "Sunucuya bağlanılıyor..."
            elif S.phase == 'play':
                msg = "Oyun devam ediyor - karakterini seç, HAZIR'a bas ve katıl!"
            elif host:
                msg = "Herkes hazır olunca OYUNU BAŞLAT'a bas (3 kişi hazırsa otomatik başlar)"
            else:
                msg = "Sunucuyu kuran oyuncunun oyunu başlatması bekleniyor..."
            self.set_text(self.t_lob, msg)

        # ------------------ ilk kişi bacakları ------------------
        def build_legs(self):
            self.legs_root = Entity()
            self.leg_parts = []
            for sx in (-0.13, 0.13):
                piv = Entity(parent=self.legs_root, position=(sx, 0.9, 0.12))
                leg = Entity(parent=piv, model='cube', color=col(0.14, 0.15, 0.22), scale=(0.2, 0.8, 0.22), y=-0.4)
                shoe = Entity(parent=piv, model='cube', color=col(0.08, 0.08, 0.08), scale=(0.22, 0.12, 0.34),
                              y=-0.86, z=0.05)
                self.leg_parts.append((piv, leg, shoe))
            self.legs_root.enabled = False

        # ------------------ silah ------------------
        def set_weapon(self, wi):
            S = self.S
            S.wi = wi % len(WEAPONS)
            S.reload_t = 0.0
            S.charge = 0.0
            S.shell_t = 0.0
            w = WEAPONS[S.wi]
            for e in self.vm_parts:
                destroy(e)
            self.vm_parts = []
            gr, tags = build_gun(self.vm, S.wi)
            self.vm_parts.append(gr)
            self.vm_tags = tags
            sleeve = tuple(v * 0.6 for v in CHARS[S.char]['col'])
            self.vm_parts += make_arms(self.vm, (0.2, -0.34, -0.62), (-0.3, -0.34, -0.62),
                                       w['rh'], w['lh'], sleeve)
            self.vm_flash.position = Vec3(*w['muz'])
            self.vm_muz.position = Vec3(*w['muz'])
            self.vm_eject.position = Vec3(*w['ej'])

        # ------------------ ağ mesajları ------------------
        def process_net(self):
            for _ in range(100):
                try:
                    m = self.net.q.get_nowait()
                except queue.Empty:
                    break
                self.on_msg(m)

        def name_of(self, i):
            return self.S.roster.get(i, "?") if i >= 0 else "çevre"

        def feed_add(self, s):
            self.S.feed.append([s, 6.0])
            self.S.feed = self.S.feed[-6:]

        def on_msg(self, m):
            S = self.S
            t = m.get("t")
            if t == "welcome":
                S.pid = m['id']
            elif t == "lobby":
                S.phase = m['ph']
                S.host = m['host']
                S.lobby = m['pl']
                S.roster = {r[0]: r[1] for r in m['pl']}
                for r in m['pl']:
                    if r[0] == S.pid:
                        S.char_sel = r[2]
                        S.ready = r[3]
            elif t == "w":
                self.on_world(m)
            elif t == "shot":
                self.on_shot(m)
            elif t == "exp":
                self.explosion_fx(m['p'])
            elif t == "imp":
                if m['id'] == S.pid and S.alive:
                    S.v[0] += m['v'][0]
                    S.v[1] += m['v'][1]
                    S.v[2] += m['v'][2]
                    S.on_ground = False
                    S.slide_t = 0.0
            elif t == "hm":
                S.hitmark = 0.25
                S.hit_head = m['head']
                self.sfx.play('hit', 0.7)
            elif t == "dead":
                vid = m['id']
                if m['by'] == vid:
                    self.feed_add(f"{self.name_of(vid)} kendini patlattı!")
                elif m['by'] < 0:
                    self.feed_add(f"{self.name_of(vid)} düştü")
                else:
                    self.feed_add(f"{self.name_of(m['by'])}  >  {self.name_of(vid)}   [{m['cause']}]")
                self.gibs(m['p'], PCOLORS[vid % 3])
                if vid == S.pid:
                    S.alive = False
                    S.death_t = 0.0
                    S.dead_by = self.name_of(m['by']) if m['by'] >= 0 and m['by'] != vid else ""
                    S.scoped = False
                    S.flying = False
                    S.slide_t = 0.0
                    S.slip_t = 0.0
            elif t == "respawn":
                if m['id'] == S.pid:
                    S.char = m['ch']
                    S.mhp = float(m['mhp'])
                    if not S.entered:
                        S.entered = True
                        self.lobby.enabled = False
                        self.hud.enabled = True
                        mouse.locked = True
                        S.paused = False
                    self.reset_local(m['p'])
            elif t == "picked":
                e = S.pk_ents.pop(m['id'], None)
                if e:
                    destroy(e)
                if m['by'] == S.pid:
                    if m['kind'] == 'ammo':
                        for i, add in ((1, 30), (2, 8), (3, 3)):
                            S.ammo[i]['res'] += add
                    elif m['kind'] == 'bomb':
                        S.grenades = min(6, S.grenades + 2)
            elif t == "slip":
                if m['id'] == S.pid and S.alive:
                    S.slip_t = float(m['d'])
                    S.flying = False
                    S.slide_t = 0.0
                    S.scoped = False
                    yr = math.radians(S.yaw)
                    S.v[0] += math.sin(yr) * 3.0
                    S.v[2] += math.cos(yr) * 3.0
                    S.on_ground = False
                    S.v[1] = max(S.v[1], 2.5)
                    self.sfx.play('slip', 1.0)
                self.feed_add(f"{self.name_of(m['id'])} muz kabuğuna bastı!")
            elif t == "ram":
                if m['by'] == S.pid:
                    S.ab_cd = float(m['cd'])
                    S.shake = max(S.shake, 0.6)
                self.feed_add(f"{self.name_of(m['by'])} {self.name_of(m['to'])} adlı oyuncuyu savurdu!")
                self.sfx.play('whoosh', 0.8)
            elif t == "abil":
                S.bn = int(m['bn'])
                if S.char == 2:
                    S.ab_cd = float(m['cd'])
            elif t == "over":
                S.over_msg = f"{self.name_of(m['w'])} KAZANDI!"
            elif t == "reset":
                S.over_msg = ""
                S.alive = False
                S.entered = False
                S.ready = False
                S.paused = False
                S.flying = False
                S.scoped = False
                self.lobby.enabled = True
                self.hud.enabled = False
                mouse.locked = False
                for pr in S.peers.values():
                    pr.root.enabled = False
            elif t == "full":
                S.over_msg = "SUNUCU DOLU (en fazla 3 oyuncu)"
            elif t == "disc":
                S.over_msg = "SUNUCU İLE BAĞLANTI KOPTU"

        def on_world(self, m):
            S = self.S
            seen = set()
            scores = {}
            for r in m['pl']:
                pid, x, y, z, yaw, pitch, wi, hp, alive, sc, kills, deaths, inv, ch, hh, fl, sl, mhp, sp = r
                scores[pid] = (kills, deaths)
                if pid == S.pid:
                    S.hp = hp
                    S.mhp = float(mhp)
                    continue
                seen.add(pid)
                pr = S.peers.get(pid)
                if pr is None:
                    pr = S.peers[pid] = Peer(pid)
                pr.tp = [x, y, z]
                pr.yaw = yaw
                pr.pitch = pitch
                pr.hh = hh
                pr.fl = bool(fl)
                pr.sl = bool(sl)
                pr.sp = bool(sp)
                pr.set_char(ch)
                pr.set_weapon(wi)
                pr.root.enabled = bool(alive)
                pr.fg.scale_x = max(0.01, hp / max(1.0, mhp))
            for pid in list(S.peers):
                if pid not in seen:
                    S.peers[pid].destroy()
                    del S.peers[pid]
            S.scores = scores
            # bombalar
            ids = set()
            for gid, x, y, z in m['ng']:
                ids.add(gid)
                e = S.nade_ents.get(gid)
                if e is None:
                    e = S.nade_ents[gid] = Entity(model='sphere', scale=0.3, color=col(0.15, 0.3, 0.12))
                e.position = Vec3(x, y, z)
            for gid in list(S.nade_ents):
                if gid not in ids:
                    destroy(S.nade_ents.pop(gid))
            # muzlar
            ids = set()
            for bid, x, y, z, landed in m['bn']:
                ids.add(bid)
                e = S.ban_ents.get(bid)
                if e is None:
                    e = Entity()
                    Entity(parent=e, model='cube', color=col(1, 0.9, 0.15), scale=(0.1, 0.09, 0.3))
                    Entity(parent=e, model='cube', color=col(1, 0.88, 0.1), scale=(0.1, 0.09, 0.16),
                           position=(0, 0.04, 0.2), rotation_x=-30)
                    Entity(parent=e, model='cube', color=col(0.2, 0.15, 0.05), scale=(0.05, 0.05, 0.04),
                           position=(0, 0.08, 0.28))
                    S.ban_ents[bid] = e
                e.position = Vec3(x, y + 0.05, z)
                e.landed = bool(landed)
            for bid in list(S.ban_ents):
                if bid not in ids:
                    destroy(S.ban_ents.pop(bid))
            # kasalar
            ids = set()
            for pk_id, kind, x, y, z in m['pk']:
                ids.add(pk_id)
                if pk_id not in S.pk_ents:
                    c = {'ammo': col(1, 0.85, 0.2), 'health': col(0.2, 1, 0.3),
                         'bomb': col(0.9, 0.3, 0.2)}[kind]
                    e = Entity(model='cube', color=c, scale=0.5, position=(x, y + 0.7, z))
                    e.base_y = y + 0.7
                    e.pos3 = (x, y, z)
                    e.kind = kind
                    S.pk_ents[pk_id] = e
            for pk_id in list(S.pk_ents):
                if pk_id not in ids:
                    destroy(S.pk_ents.pop(pk_id))

        def on_shot(self, m):
            S = self.S
            o = m['o']
            pid = m['id']
            wi = int(m['w']) % len(WEAPONS)
            d0 = math.dist(o, S.p)
            if pid != S.pid:
                self.sfx.play(f'shot{wi}', clampf(1 - d0 / 80, 0.05, 1.0))
                pr = S.peers.get(pid)
                if pr is not None:
                    pr.fire()
                    mp = pr.muzzle.world_position
                    self.smoke((mp[0], mp[1], mp[2]), 0.1, 0.3, 0.8, 0.8, 0.5)
            for e in m['ends']:
                dx, dy, dz = e[0] - o[0], e[1] - o[1], e[2] - o[2]
                L = math.sqrt(dx * dx + dy * dy + dz * dz)
                if L < 0.5:
                    continue
                start = [o[0] + dx / L * 0.9, o[1] + dy / L * 0.9 - 0.15, o[2] + dz / L * 0.9]
                self.tracer(start, e[:3], wi == 3)
                if L < 120:
                    if e[3]:
                        self.blood(e)
                    else:
                        self.spark(e)
                        self.smoke((e[0], e[1], e[2]), 0.12, 0.3, 0.7, 0.5, 0.8)

        # ------------------ efektler ------------------
        def add_fx(self, e, v=None, life=0.5, grav=True, bounce=True, grow=0.0, fade=None, drag=0.0, spin=None):
            S = self.S
            if len(S.fx) > 240:
                old = S.fx.pop(0)
                destroy(old['e'])
            S.fx.append(dict(e=e, v=v, life=life, life0=life, grav=grav, bounce=bounce,
                             grow=grow, fade=fade, drag=drag, spin=spin))

        def tracer(self, a, b, heavy):
            L = math.dist(a, b)
            e = Entity(model='cube', color=col(1, 0.95, 0.6, 1) if not heavy else col(0.8, 0.95, 1, 1),
                       scale=(0.03 if heavy else 0.015, 0.03 if heavy else 0.015, L))
            e.position = Vec3((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
            e.look_at(Vec3(b[0], b[1], b[2]))
            self.add_fx(e, None, 0.07 if not heavy else 0.2, False)

        def spark(self, p):
            for _ in range(3):
                e = Entity(model='cube', color=col(1, 0.8, 0.3), scale=0.05, position=Vec3(p[0], p[1], p[2]))
                v = [rnd.uniform(-2, 2), rnd.uniform(0, 3), rnd.uniform(-2, 2)]
                self.add_fx(e, v, 0.3)

        def blood(self, p):
            for _ in range(5):
                e = Entity(model='cube', color=col(0.7, 0.03, 0.03), scale=rnd.uniform(0.03, 0.07),
                           position=Vec3(p[0], p[1], p[2]))
                v = [rnd.uniform(-2.5, 2.5), rnd.uniform(0, 3), rnd.uniform(-2.5, 2.5)]
                self.add_fx(e, v, 0.6)

        def smoke(self, p, size=0.1, a=0.35, life=0.9, rise=0.8, grow=0.5):
            e = Entity(model='sphere', color=col(0.8, 0.8, 0.8, a), scale=size, position=Vec3(p[0], p[1], p[2]))
            v = [rnd.uniform(-0.3, 0.3), rise * rnd.uniform(0.5, 1.2), rnd.uniform(-0.3, 0.3)]
            self.add_fx(e, v, life, grav=False, bounce=False, grow=grow, fade=(0.8, 0.8, 0.8, a), drag=1.5)

        def gibs(self, p, c):
            for _ in range(16):
                s = rnd.uniform(0.12, 0.3)
                e = Entity(model='cube', color=col(*rnd.choice([c, SKIN, (0.6, 0.05, 0.05)])),
                           scale=s, position=Vec3(p[0], p[1] + 1.0, p[2]))
                v = [rnd.uniform(-5, 5), rnd.uniform(2, 9), rnd.uniform(-5, 5)]
                self.add_fx(e, v, 6.0)

        def explosion_fx(self, p):
            S = self.S
            self.sfx.play('boom', clampf(1 - math.dist(p, S.p) / 90, 0.1, 1.0))
            e = Entity(model='sphere', color=col(1, 0.65, 0.15, 0.9), scale=0.5, position=Vec3(*p))
            e.animate_scale(11, duration=0.25)
            e.fade_out(value=0, duration=0.45)
            destroy(e, delay=0.5)
            e2 = Entity(model='sphere', color=col(1, 1, 0.8, 0.9), scale=0.5, position=Vec3(*p))
            e2.animate_scale(6, duration=0.15)
            e2.fade_out(value=0, duration=0.25)
            destroy(e2, delay=0.3)
            for _ in range(22):
                s = rnd.uniform(0.15, 0.4)
                ee = Entity(model='cube', color=col(*rnd.choice([(0.25, 0.2, 0.15), (0.4, 0.3, 0.2), (1, 0.5, 0.1)])),
                            scale=s, position=Vec3(*p))
                v = [rnd.uniform(-10, 10), rnd.uniform(3, 14), rnd.uniform(-10, 10)]
                self.add_fx(ee, v, 3.0)
            for _ in range(6):
                self.smoke((p[0] + rnd.uniform(-1, 1), p[1] + rnd.uniform(0, 1), p[2] + rnd.uniform(-1, 1)),
                           0.8, 0.5, 2.5, 1.5, 1.2)
            d = math.dist(p, S.p)
            S.shake = max(S.shake, 1.6 * max(0.0, 1 - d / 45))

        def eject_shell(self, w):
            S = self.S
            p = self.vm_eject.world_position
            yr = math.radians(S.yaw)
            rx, rz = math.cos(yr), -math.sin(yr)
            fx, fz = math.sin(yr), math.cos(yr)
            big = w['shell'] == 'red'
            e = Entity(model='cube', color=col(*((0.8, 0.12, 0.1) if big else BRASS)),
                       scale=(0.025, 0.025, 0.06) if big else (0.014, 0.014, 0.04),
                       position=Vec3(p[0], p[1], p[2]))
            sp = rnd.uniform(1.8, 3.0)
            v = [rx * sp - fx * 0.4 + S.v[0] * 0.3, rnd.uniform(1.5, 3.0), rz * sp - fz * 0.4 + S.v[2] * 0.3]
            self.add_fx(e, v, 2.5, spin=(rnd.uniform(-600, 600), rnd.uniform(-600, 600), 0))

        def update_fx(self, dt):
            S = self.S
            alive = []
            for f in S.fx:
                f['life'] -= dt
                if f['life'] <= 0:
                    destroy(f['e'])
                    continue
                e = f['e']
                if f['v'] is not None:
                    v = f['v']
                    if f['grav']:
                        v[1] -= GRAVITY * dt
                    if f['drag']:
                        k = max(0.0, 1 - f['drag'] * dt)
                        v[0] *= k
                        v[1] *= k
                        v[2] *= k
                    e.x += v[0] * dt
                    e.y += v[1] * dt
                    e.z += v[2] * dt
                    if f['bounce']:
                        h = e.scale_y / 2
                        if e.y < h:
                            e.y = h
                            v[1] = -v[1] * 0.4
                            v[0] *= 0.7
                            v[2] *= 0.7
                if f['grow']:
                    s = e.scale_x + f['grow'] * dt
                    e.scale = (s, s, s)
                if f['fade'] is not None:
                    a = max(0.0, f['life'] / f['life0']) * f['fade'][3]
                    e.color = col(f['fade'][0], f['fade'][1], f['fade'][2], a)
                if f['spin'] is not None and e.y > e.scale_y / 2 + 0.01:
                    e.rotation_x += f['spin'][0] * dt
                    e.rotation_y += f['spin'][1] * dt
                alive.append(f)
            S.fx = alive

        # ------------------ yerel oyuncu ------------------
        def reset_local(self, pos):
            S = self.S
            S.p = [float(pos[0]), float(pos[1]), float(pos[2])]
            S.v = [0.0, 0.0, 0.0]
            S.alive = True
            S.hp = S.hp_prev = S.mhp
            S.stamina = 100.0
            S.locked = False
            S.hh = H_STAND
            S.eye_y = H_STAND - 0.15
            S.slide_t = 0.0
            S.flying = False
            S.fly_t = FLY_TIME
            S.ab_cd = 0.0
            S.bn = BAN_MAX
            S.nofall = 0.0
            S.slip_t = 0.0
            S.ammo = [dict(mag=w['mag'], res=w['res']) for w in WEAPONS]
            S.grenades = 3
            S.cool = S.reload_t = 0.0
            S.charge = 0.0
            S.kickv = 0.0
            S.scoped = False
            S.over_msg = ""
            self.set_weapon(1)

        def stop_fly(self):
            S = self.S
            if S.flying:
                S.flying = False
                S.ab_cd = FLY_CD
                S.nofall = 2.5

        def use_ability(self):
            S = self.S
            if not S.alive or S.slip_t > 0 or S.paused:
                return
            if S.char == 0:
                if S.flying:
                    self.stop_fly()
                elif S.ab_cd <= 0:
                    S.flying = True
                    S.fly_t = FLY_TIME
                    S.on_ground = False
                    S.v[1] = max(S.v[1], 4.0)
                    S.slide_t = 0.0
                    self.sfx.play('whoosh', 0.7)
            elif S.char == 2:
                if S.bn > 0 and S.ab_cd <= 0 and S.ban_cool <= 0:
                    S.ban_cool = 0.35
                    d = dir_from(S.yaw, S.pitch + S.kickv)
                    o = self.eye()
                    self.net.send({"t": "ban",
                                   "o": [round(o[0] + d[0] * 0.6, 3), round(o[1] + d[1] * 0.6, 3),
                                         round(o[2] + d[2] * 0.6, 3)],
                                   "v": [round(d[0] * 15 + S.v[0] * 0.5, 3), round(d[1] * 15 + 2.0, 3),
                                         round(d[2] * 15 + S.v[2] * 0.5, 3)]})
                    S.bn -= 1
                    if S.bn <= 0:
                        S.ab_cd = BAN_CD
                    self.sfx.play('whoosh', 0.5)

        def _acc(self, tx, tz, acc, dt):
            S = self.S
            dvx, dvz = tx - S.v[0], tz - S.v[2]
            dl = math.hypot(dvx, dvz)
            mx = acc * dt
            if dl > mx:
                dvx, dvz = dvx / dl * mx, dvz / dl * mx
            S.v[0] += dvx
            S.v[2] += dvz

        def do_move(self, dt, fw, st, sprint_key, crouch_key, jump_held):
            S = self.S
            C = CHARS[S.char]
            slipped = S.slip_t > 0
            if slipped:
                fw = st = 0.0
                sprint_key = crouch_key = jump_held = False
                S.jump_buf = 0.0
            # --- boy (çömelme) ---
            if slipped:
                target = H_SLIP
            elif (crouch_key or S.slide_t > 0) and not S.flying:
                target = H_CROUCH
            else:
                target = H_STAND
            if S.hh > target:
                S.hh = max(target, S.hh - 8.0 * dt)
            elif S.hh < target:
                nh = min(target, S.hh + 8.0 * dt)
                if not boxes_at(S.p[0], S.p[1], S.p[2], nh):
                    S.hh = nh
            crouching = S.hh < 1.45
            # --- zamanlayıcılar ---
            if S.on_ground:
                S.coyote = 0.1
            else:
                S.coyote = max(0.0, S.coyote - dt)
            S.jump_buf = max(0.0, S.jump_buf - dt)
            sp_xz = math.hypot(S.v[0], S.v[2])
            # --- kayma başlat ---
            cedge = crouch_key and not S.crouch_prev
            S.crouch_prev = crouch_key
            if (cedge and S.on_ground and S.slide_t <= 0 and self.sprinting and sp_xz > 6.0
                    and not S.flying and not slipped):
                S.slide_t = SLIDE_TIME
                S.slide_dir = (S.v[0] / sp_xz, S.v[2] / sp_xz)
                S.slide_spd = min(sp_xz * 1.15, 14.0)
            # --- istenen yön ---
            yr = math.radians(S.yaw)
            fx, fz = math.sin(yr), math.cos(yr)
            rx, rz = math.cos(yr), -math.sin(yr)
            wx, wz = fx * fw + rx * st, fz * fw + rz * st
            L = math.hypot(wx, wz)
            if L > 0:
                wx /= L
                wz /= L
            sprinting = bool(sprint_key and fw > 0 and not S.locked and not S.scoped and S.stamina > 0
                             and not crouching and not S.flying and S.slide_t <= 0)
            if sprinting:
                S.stamina -= 9.6 * dt
                S.sprint_delay = 1.0
                if S.stamina <= 0:
                    S.stamina = 0
                    S.locked = True
            else:
                if S.sprint_delay > 0:
                    S.sprint_delay -= dt
                else:
                    S.stamina = min(100.0, S.stamina + 17.0 * dt)
                if S.locked and S.stamina >= 30:
                    S.locked = False
            speed = C['sprint'] if sprinting else C['walk']
            if crouching:
                speed = C['walk'] * 0.5
            if S.scoped:
                speed *= 0.35
            elif S.ads:
                speed *= 0.7
            self.sprinting = sprinting
            S.strafe = st
            if S.flying:
                S.fly_t -= dt
                up = (6.0 if jump_held else 0.0) - (6.0 if crouch_key else 0.0)
                up += -math.sin(math.radians(S.pitch)) * 9.0 * max(0.0, fw)
                up = clampf(up, -9.0, 9.0)
                S.v[1] += (up - S.v[1]) * min(1.0, 5.0 * dt)
                self._acc(wx * 11.0, wz * 11.0, 25.0, dt)
                S.on_ground = False
                if S.fly_t <= 0:
                    self.stop_fly()
            else:
                if S.slide_t > 0:
                    S.slide_t -= dt
                    k = max(0.0, S.slide_t / SLIDE_TIME)
                    spd = 2.5 + (S.slide_spd - 2.5) * k
                    self._acc(S.slide_dir[0] * spd, S.slide_dir[1] * spd, 60.0, dt)
                    if S.jump_buf > 0:
                        S.slide_t = 0.0
                else:
                    acc = 45.0 if S.on_ground else 12.0
                    if slipped:
                        acc = 2.5 if S.on_ground else 6.0
                        speed = 0.0
                    self._acc(wx * speed, wz * speed, acc, dt)
                if S.jump_buf > 0 and S.coyote > 0 and not slipped:
                    S.v[1] = JUMP_V * (0.9 if crouching else 1.0)
                    S.on_ground = False
                    S.coyote = 0.0
                    S.jump_buf = 0.0
                    S.slide_t = 0.0
                S.v[1] = max(S.v[1] - GRAVITY * dt, -45)
            self.collide(dt, jump_held)

        def collide(self, dt, jump_held):
            S = self.S
            h = S.hh
            x, y, z = S.p
            vx, vy, vz = S.v
            was_ground = S.on_ground
            # X
            nx = x + vx * dt
            hit = boxes_at(nx, y, z, h)
            if not hit:
                x = nx
            else:
                top = max(b[4] for b in hit)
                if was_ground and top - y <= 0.55 and not boxes_at(nx, top + 0.001, z, h):
                    x, y = nx, top + 0.001
                elif (jump_held and not S.flying and 0.4 < top - y <= 1.9 and abs(vx) > 0.5
                      and not boxes_at(nx, top + 0.001, z, h)):
                    vy = max(vy, math.sqrt(2 * GRAVITY * (top - y + 0.3)))      # kenara tırmanma
                    vx *= 0.5
                else:
                    vx = 0.0
            # Z
            nz = z + vz * dt
            hit = boxes_at(x, y, nz, h)
            if not hit:
                z = nz
            else:
                top = max(b[4] for b in hit)
                if was_ground and top - y <= 0.55 and not boxes_at(x, top + 0.001, nz, h):
                    z, y = nz, top + 0.001
                elif (jump_held and not S.flying and 0.4 < top - y <= 1.9 and abs(vz) > 0.5
                      and not boxes_at(x, top + 0.001, nz, h)):
                    vy = max(vy, math.sqrt(2 * GRAVITY * (top - y + 0.3)))
                    vz *= 0.5
                else:
                    vz = 0.0
            # Y
            ny = y + vy * dt
            S.on_ground = False
            impact = 0.0
            hit = boxes_at(x, ny, z, h)
            if hit:
                if vy <= 0:
                    tops = [b[4] for b in hit if b[4] <= y + 0.06]
                    if tops:
                        y = max(tops)
                        S.on_ground = True
                        impact = vy
                    vy = 0.0
                else:
                    vy = 0.0
            else:
                y = ny
            if y <= 0:
                if vy < 0:
                    impact = min(impact, vy)
                y = 0.0
                vy = 0.0
                S.on_ground = True
            # harita sınırları
            if abs(x) > 29.65:
                x = clampf(x, -29.65, 29.65)
                vx = 0.0
            if abs(z) > 29.65:
                z = clampf(z, -29.65, 29.65)
                vz = 0.0
            if y > 20:
                y = 20.0
                vy = min(vy, 0.0)
            S.p = [x, y, z]
            S.v = [vx, vy, vz]
            if impact < -6:
                S.land = max(S.land, min(0.22, -impact * 0.01))
            if impact < -14 and S.alive and S.nofall <= 0 and not S.flying:
                self.net.send({"t": "fall", "d": round((-impact - 14) * 6, 1)})
                S.shake = max(S.shake, 0.5)

        def eye(self):
            S = self.S
            return [S.p[0], S.p[1] + S.hh - 0.15, S.p[2]]

        def do_fire(self):
            S = self.S
            w = WEAPONS[S.wi]
            st = S.ammo[S.wi]
            st['mag'] -= 1
            S.cool = w['cd']
            S.shots += 1
            S.shot_gap = 0.0
            sp_xz = math.hypot(S.v[0], S.v[2])
            crouching = S.hh < 1.45
            pitch_e = S.pitch + S.kickv
            d = dir_from(S.yaw, pitch_e)
            spread = w['spread'] * (1 + min(sp_xz, 10) * 0.12) + S.bloom
            if crouching:
                spread *= 0.6
            if not S.on_ground:
                spread *= 2.2
            if S.ads:
                spread *= 0.55
            if w['name'] == 'Sniper':
                spread = 0.0 if S.scoped else 0.06
                if S.scoped and sp_xz > 1.0:
                    spread = 0.02
            ds = [perturb(d, spread) for _ in range(w['pellets'])]
            self.net.send({"t": "shoot", "o": [round(c, 3) for c in self.eye()],
                           "ds": [[round(c, 4) for c in x] for x in ds], "w": S.wi})
            S.bloom = min(0.05, S.bloom + w['bloom'])
            # geri tepme (seri atışta yukarı tırmanır, yana sapar)
            pat = min(S.shots, 12)
            rk = 1.0
            if S.ads:
                rk *= 0.7
            if crouching:
                rk *= 0.8
            vk = w['kick'] * (0.6 + 0.05 * pat) * 0.5 * rk
            S.kickv += vk
            S.pitch -= vk
            S.yaw += (math.sin(S.shots * 0.9) * w['hkick'] + rnd.uniform(-1, 1) * w['hkick'] * 0.4) * rk
            S.vm_kick = min(0.3, S.vm_kick + 0.05 + w['kick'] * 0.02)
            S.v[0] -= d[0] * w['push']
            S.v[1] -= d[1] * w['push']
            S.v[2] -= d[2] * w['push']
            if w['push'] > 3:
                S.on_ground = False
                S.shake = max(S.shake, 0.4)
            # ateş efektleri
            self.sfx.play(f'shot{S.wi}', 1.0)
            self.vm_flash.rotation_z = rnd.uniform(0, 90)
            k = w['flash'] * rnd.uniform(0.85, 1.2)
            self.vm_flash.scale = (k, k, k)
            S.muzzle_t = 0.06
            mp = self.vm_muz.world_position
            for _ in range(2 if w['pellets'] == 1 else 4):
                self.smoke((mp[0], mp[1], mp[2]), 0.07 * w['flash'] ** 0.5, 0.35, 0.9, 0.8, 0.45)
            if w['sdelay'] <= 0:
                self.eject_shell(w)
            else:
                S.shell_t = w['sdelay']

        def throw(self):
            S = self.S
            d = dir_from(S.yaw, S.pitch + S.kickv)
            sp = 7 + 15 * min(1.0, S.charge / 1.2)
            o = self.eye()
            self.net.send({"t": "nade", "o": [o[0] + d[0] * 0.6, o[1] + d[1] * 0.6, o[2] + d[2] * 0.6],
                           "v": [d[0] * sp + S.v[0] * 0.8, d[1] * sp + S.v[1] * 0.5 + 2, d[2] * sp + S.v[2] * 0.8]})
            S.grenades -= 1
            self.sfx.play('whoosh', 0.6)

        def update_local(self, dt):
            S = self.S
            K = held_keys
            C = CHARS[S.char]
            over = S.over_msg.endswith("KAZANDI!")
            can_look = S.alive and not S.paused and not over
            active = can_look and S.slip_t <= 0
            # zamanlayıcılar
            S.slip_t = max(0.0, S.slip_t - dt)
            S.ab_cd = max(0.0, S.ab_cd - dt)
            S.nofall = max(0.0, S.nofall - dt)
            S.ban_cool = max(0.0, S.ban_cool - dt)
            S.land = max(0.0, S.land - dt * 0.6)
            if S.char == 2 and S.bn <= 0 and S.ab_cd <= 0:
                S.bn = BAN_MAX
            if S.char == 0 and not S.flying and S.ab_cd <= 0:
                S.fly_t = FLY_TIME
            w = WEAPONS[S.wi]
            st_ = S.ammo[S.wi]
            rmb = bool(K['right mouse'])
            S.scoped = bool(active and w['name'] == 'Sniper' and rmb and S.reload_t <= 0)
            S.ads = bool(active and w['name'] != 'Sniper' and rmb and S.reload_t <= 0)
            fw = st = 0.0
            sprint = crouch = jump_held = False
            if active:
                fw = K['w'] - K['s']
                st = K['d'] - K['a']
                jump_held = bool(K['space'])
                sprint = bool(K['left shift'])
                crouch = bool(K['c'] or K['left control'])
            if can_look and mouse.locked:
                sens = 40 * (camera.fov / 90.0)
                S.yaw += mouse.velocity[0] * sens
                S.pitch -= mouse.velocity[1] * sens
                S.pitch = max(-89.0, min(89.0, S.pitch))
            self.sprinting = False
            self.do_move(dt, fw, st, sprint, crouch, jump_held)

            S.cool = max(0.0, S.cool - dt)
            S.bloom = max(0.0, S.bloom - 0.12 * dt)
            S.kickv *= math.exp(-8 * dt)
            S.vm_kick *= math.exp(-12 * dt)
            S.shot_gap += dt
            if S.shot_gap > 0.35:
                S.shots = 0
            if S.shell_t > 0:
                S.shell_t -= dt
                if S.shell_t <= 0 and S.alive:
                    self.eject_shell(w)
            if active:
                # şarjör
                if S.reload_t > 0:
                    S.reload_t -= dt
                    if S.reload_t <= 0:
                        take = min(w['mag'] - st_['mag'], st_['res'])
                        st_['mag'] += take
                        st_['res'] -= take
                elif (st_['mag'] == 0 or S.want_reload) and st_['res'] > 0 and st_['mag'] < w['mag']:
                    S.reload_t = w['reload']
                    S.scoped = False
                    S.ads = False
                    self.sfx.play('reload', 0.8)
                S.want_reload = False
                can = S.cool <= 0 and S.reload_t <= 0 and st_['mag'] > 0 and mouse.locked
                if can and ((w['auto'] and K['left mouse']) or S.fire_edge):
                    self.do_fire()
                elif S.fire_edge and st_['mag'] == 0 and st_['res'] <= 0 and S.cool <= 0:
                    self.sfx.play('click', 0.6)
                    S.cool = 0.3
                S.fire_edge = False
                # bomba
                if K['g'] and S.grenades > 0:
                    S.charge = min(1.2, S.charge + dt)
                elif S.charge > 0:
                    if S.grenades > 0:
                        self.throw()
                    S.charge = 0.0
                # kasa toplama
                for pk_id, e in S.pk_ents.items():
                    if pk_id in S.pk_sent:
                        continue
                    ex, ey, ez = e.pos3
                    if abs(ex - S.p[0]) < 1.4 and abs(ez - S.p[2]) < 1.4 and abs(ey - S.p[1]) < 2.0:
                        S.pk_sent.add(pk_id)
                        self.net.send({"t": "pick", "id": pk_id})
            else:
                S.scoped = False
                S.ads = False
                S.fire_edge = False
                S.charge = 0.0
                S.want_reload = False

            sp_xz = math.hypot(S.v[0], S.v[2])
            # kamera
            S.eye_y += ((S.hh - 0.15) - S.eye_y) * min(1.0, dt * 18)
            if S.on_ground and S.alive and S.slip_t <= 0:
                S.bob += sp_xz * dt * (1.1 if self.sprinting else 0.85)
            bk = min(1.0, sp_xz / 6.0) if S.on_ground else 0.0
            bobx = math.sin(S.bob) * 0.025 * bk
            boby = abs(math.sin(S.bob)) * 0.035 * bk
            sway_x = sway_y = 0.0
            if S.scoped:
                sway_x = math.sin(S.t * 1.3) * 0.05
                sway_y = math.sin(S.t * 0.9 + 1) * 0.05
            sh = S.shake
            ox = rnd.uniform(-sh, sh) * 0.06
            oy = rnd.uniform(-sh, sh) * 0.06
            ey = S.eye_y if S.alive else 0.4
            self.pivot.position = Vec3(S.p[0], S.p[1] + ey, S.p[2])
            self.pivot.rotation_y = S.yaw + sway_y
            self.pivot.rotation_x = S.pitch + S.kickv + sway_x
            if not S.alive:
                roll_t = 55.0
            elif S.slip_t > 0:
                roll_t = 70.0
            elif S.slide_t > 0:
                roll_t = 5.0
            else:
                roll_t = -S.strafe * 1.6
            S.roll += (roll_t - S.roll) * min(1.0, dt * 8)
            self.pivot.rotation_z = S.roll
            camera.position = Vec3(ox + bobx, oy + boby - S.land, 0)
            S.shake *= math.exp(-5 * dt)
            tf = 90.0
            if S.scoped:
                tf = 12.0
            elif S.ads:
                tf = 70.0
            elif S.flying or S.slide_t > 0:
                tf = 100.0
            elif self.sprinting:
                tf = 98.0 if S.char != 1 else 106.0
            camera.fov += (tf - camera.fov) * min(1.0, dt * 14)

            # viewmodel
            S.ads_k += ((1.0 if S.ads else 0.0) - S.ads_k) * min(1.0, dt * 12)
            S.spr_k += ((1.0 if (self.sprinting and S.on_ground) else 0.0) - S.spr_k) * min(1.0, dt * 8)
            prog = 0.0
            dip = 0.0
            if S.reload_t > 0:
                prog = 1.0 - S.reload_t / w['reload']
                dip = math.sin(math.pi * prog)
            base = (0.22, -0.2, 0.55)
            ads = w['ads']
            bob = math.sin(S.bob * 2) * 0.01 * bk * (1 - S.ads_k)
            px = base[0] + (ads[0] - base[0]) * S.ads_k + bobx * 0.4
            py = base[1] + (ads[1] - base[1]) * S.ads_k + bob - 0.12 * dip - 0.07 * S.spr_k - S.land * 0.4
            pz = base[2] + (ads[2] - base[2]) * S.ads_k - S.vm_kick
            self.vm.position = Vec3(px, py, pz)
            self.vm.rotation_x = -S.vm_kick * 30 + 40 * dip + 25 * S.spr_k
            self.vm.rotation_y = -14 * S.spr_k
            self.vm.rotation_z = 6 * S.spr_k
            # parça animasyonları
            ph = 0.0
            if S.cool > 0 and w['cd'] > 0.4:
                ph = 1.0 - S.cool / w['cd']
            for tag, ents in self.vm_tags.items():
                for e in ents:
                    off = Vec3(0, 0, 0)
                    if tag == 'mag':
                        off = Vec3(0, -0.2 * dip, 0.02 * dip)
                    elif tag == 'slide':
                        off = Vec3(0, 0, -0.04 * min(1.0, S.vm_kick / 0.12))
                    elif tag == 'pump':
                        if 0.25 < ph < 0.75:
                            off = Vec3(0, 0, -0.12 * math.sin(math.pi * (ph - 0.25) / 0.5))
                    elif tag == 'bolt':
                        if 0.35 < ph < 0.8:
                            off = Vec3(0, 0, -0.1 * math.sin(math.pi * (ph - 0.35) / 0.45))
                    e.position = e.bp + off
            self.vm.enabled = S.alive and not S.scoped and S.slip_t <= 0
            S.muzzle_t = max(0.0, S.muzzle_t - dt)
            self.vm_flash.enabled = S.muzzle_t > 0

            # ilk kişi bacakları
            lr = self.legs_root
            lr.enabled = S.alive and not S.scoped
            lr.position = Vec3(S.p[0], S.p[1], S.p[2])
            lr.rotation_y = S.yaw
            S.leg_phase += min(sp_xz, 16) * dt * 1.2
            sw = math.sin(S.leg_phase) * 38 if (sp_xz > 0.5 and S.on_ground) else 0
            kh = S.hh / H_STAND
            bend = (H_STAND - S.hh) * 45
            for i, (piv, leg, shoe) in enumerate(self.leg_parts):
                piv.y = 0.9 * kh
                piv.rotation_x = (sw if i == 0 else -sw) + bend
                leg.scale_y = 0.8 * kh
                leg.y = -0.4 * kh
                shoe.y = -0.86 * kh

        # ------------------ HUD güncelle ------------------
        def update_hud(self, dt):
            S = self.S
            w = WEAPONS[S.wi]
            st = S.ammo[S.wi]
            C = CHARS[S.char]
            if S.hp < S.hp_prev - 0.5:
                S.flash = min(0.7, 0.25 + (S.hp_prev - S.hp) * 0.01)
                S.shake = max(S.shake, 0.6)
            S.hp_prev = S.hp
            S.flash = max(0.0, S.flash - dt * 1.5)
            self.flash_q.color = col(1, 0, 0, S.flash)
            mhp = max(1.0, S.mhp)
            self.hp_fg.scale_x = 0.34 * clampf(S.hp / mhp, 0.0, 1.0)
            self.hp_fg.color = col(0.3, 0.9, 0.3) if S.hp / mhp > 0.35 else col(0.95, 0.25, 0.2)
            self.st_fg.scale_x = 0.34 * S.stamina / 100.0
            self.st_fg.color = col(1, 0.6, 0.2) if S.locked else col(0.3, 0.7, 1)
            self.gr_fg.scale_x = 0.2 * min(1.0, S.charge / 1.2)
            self.set_text(self.t_hp, f"{int(max(0, S.hp))}")
            self.set_text(self.t_weapon, w['name'])
            res = "∞" if st['res'] > 1000 else str(st['res'])
            self.set_text(self.t_ammo, "ŞARJÖR DEĞİŞİYOR..." if S.reload_t > 0 else f"{st['mag']} / {res}")
            self.set_text(self.t_bomb, f"Bomba (G): {S.grenades}")
            self.set_text(self.t_char, f"{C['name']}   [C] çömel   [Shift+C] kay")
            # yetenek çubuğu
            frac, txt_, c = 1.0, "", col(0.3, 0.9, 0.5)
            if S.char == 0:
                if S.flying:
                    frac, txt_, c = S.fly_t / FLY_TIME, f"UÇUŞ  {S.fly_t:.1f} sn  ([F] ile bitir)", col(0.4, 0.8, 1)
                elif S.ab_cd > 0:
                    frac, txt_, c = 1 - S.ab_cd / FLY_CD, f"UÇUŞ bekleme: {int(S.ab_cd) + 1} sn", col(1, 0.6, 0.2)
                else:
                    txt_ = "UÇUŞ HAZIR  [F]"
            elif S.char == 1:
                if S.ab_cd > 0:
                    frac, txt_, c = 1 - S.ab_cd / RAM_CD, f"ÇARPMA bekleme: {int(S.ab_cd) + 1} sn", col(1, 0.6, 0.2)
                else:
                    txt_ = "ÇARPMA HAZIR (hızlı koşarken çarp)"
            else:
                if S.ab_cd > 0:
                    frac, txt_, c = 1 - S.ab_cd / BAN_CD, f"MUZ bekleme: {int(S.ab_cd) + 1} sn", col(1, 0.6, 0.2)
                else:
                    frac, txt_, c = S.bn / BAN_MAX, f"MUZ  [F]  x{S.bn}", col(1, 0.9, 0.2)
            self.ab_fg.scale_x = 0.34 * clampf(frac, 0.0, 1.0)
            self.ab_fg.color = c
            self.set_text(self.t_ab, txt_)
            # artı: silaha ve harekete göre açılır
            sp_xz = math.hypot(S.v[0], S.v[2])
            gap = 0.006 + w['spread'] * 0.9 + S.bloom * 0.9 + min(sp_xz, 9) * 0.0015
            if not S.on_ground:
                gap += 0.02
            if S.hh < 1.45:
                gap *= 0.7
            if S.ads:
                gap *= 0.6
            gap = min(gap, 0.12)
            S.cross_gap += (gap - S.cross_gap) * min(1.0, dt * 14)
            show_cross = S.alive and not S.scoped
            for e in self.cross:
                e.enabled = show_cross
                e.position = (e.dirv[0] * (S.cross_gap + 0.006), e.dirv[1] * (S.cross_gap + 0.006), 0)
            for e in self.scope:
                e.enabled = S.scoped and camera.fov < 30
            S.hitmark = max(0.0, S.hitmark - dt)
            self.hit_q.enabled = S.hitmark > 0
            if S.hitmark > 0:
                self.hit_q.color = color.red if S.hit_head else color.white
            # feed
            for f in S.feed:
                f[1] -= dt
            S.feed = [f for f in S.feed if f[1] > 0]
            self.set_text(self.t_feed, "\n".join(f[0] for f in S.feed))
            # skor
            lines = []
            for pid in sorted(S.scores):
                k, d = S.scores[pid]
                me = " (sen)" if pid == S.pid else ""
                lines.append(f"{self.name_of(pid)}{me}   {k} / {d}")
            self.set_text(self.t_score, f"İlk {KILL_LIMIT} öldürme kazanır\n" + "\n".join(lines))
            self.set_text(self.t_center, S.over_msg)
            if not S.alive and not S.over_msg:
                self.set_text(self.t_dead, "ÖLDÜN" + (f"  -  {S.dead_by}" if S.dead_by else ""))
            elif S.slip_t > 0:
                self.set_text(self.t_dead, "KAYDIN!")
            else:
                self.set_text(self.t_dead, "")
            if S.paused:
                self.set_text(self.t_help, "DURAKLATILDI - devam etmek için tıkla")
            else:
                self.set_text(self.t_help, "")

        # ------------------ ana döngü ------------------
        def update(self):
            S = self.S
            dt = min(time.dt, 0.05)
            S.t += dt
            self.process_net()
            if not S.entered:
                self.update_lobby(dt)
                for pr in S.peers.values():
                    pr.update(dt)
                self.update_fx(dt)
                return
            self.update_local(dt)
            for pr in S.peers.values():
                pr.update(dt)
            for e in S.pk_ents.values():
                e.rotation_y += 90 * dt
                e.y = e.base_y + math.sin(S.t * 3) * 0.1
            for g in S.nade_ents.values():
                g.rotation_y += 200 * dt
            for b in S.ban_ents.values():
                if not b.landed:
                    b.rotation_x += 420 * dt
                else:
                    b.rotation_x = 0
            self.update_fx(dt)
            self.update_hud(dt)
            S.send_t += dt
            if S.send_t >= 1 / 30 and S.alive and self.net.ok:
                S.send_t = 0.0
                self.net.send({"t": "s", "p": [round(c, 3) for c in S.p], "v": [round(c, 2) for c in S.v],
                               "yaw": round(S.yaw, 2), "pitch": round(S.pitch + S.kickv, 2),
                               "w": S.wi, "sc": bool(S.scoped), "hh": round(S.hh, 2),
                               "fl": bool(S.flying), "sp": bool(self.sprinting or S.slide_t > 0)})

        def input(self, key):
            S = self.S
            if not S.entered:
                if key in ('1', '2', '3'):
                    self.pick_char(int(key) - 1)
                elif key == 'enter':
                    self.on_ready()
                elif key == 'h':
                    self.on_start()
                return
            if key == 'escape':
                S.paused = not S.paused
                mouse.locked = not S.paused
                return
            if S.paused:
                if key == 'left mouse down':
                    S.paused = False
                    mouse.locked = True
                return
            if key == 'left mouse down':
                S.fire_edge = True
            elif key in ('1', '2', '3', '4'):
                self.set_weapon(int(key) - 1)
            elif key == 'scroll up':
                self.set_weapon(S.wi + 1)
            elif key == 'scroll down':
                self.set_weapon(S.wi - 1)
            elif key == 'r':
                S.want_reload = True
            elif key == 'space':
                S.jump_buf = 0.12
            elif key == 'f':
                self.use_ability()


# ======================================================================
#  BAŞLATMA
# ======================================================================
def run_client(host, name):
    if not HAVE_URSINA:
        print("HATA: Ursina kurulu değil.  ->  pip install ursina")
        sys.exit(1)
    try:
        net = NetClient(host, PORT, name)
    except OSError as e:
        print(f"Sunucuya bağlanılamadı ({host}:{PORT}): {e}")
        print("IP adresi doğru mu? Aynı ağda mısınız? Güvenlik duvarı portu engelliyor olabilir.")
        sys.exit(1)
    app = Ursina(title="LAN Savaş 3D", development_mode=False)
    window.exit_button.visible = False
    Arena(net, name)
    app.run()


def main():
    args = sys.argv[1:]
    mode = args[0].lower() if args else None
    if mode is None:
        print("1) Oyun kur (host)\n2) Oyuna katıl (join)\n3) Sadece sunucu")
        mode = {"1": "host", "2": "join", "3": "server"}.get(input("Seçim: ").strip(), "host")
        args = [mode]
        if mode == "join":
            args.append(input("Sunucu IP: ").strip())
        if mode != "server":
            args.append(input("İsmin: ").strip() or "Oyuncu")

    if mode == "server":
        srv = Server()
        srv.start()
        print(f"Sunucu çalışıyor. Diğerleri şunu yazsın:  python savas3d.py join {lan_ip()} <isim>")
        try:
            while True:
                pytime.sleep(1)
        except KeyboardInterrupt:
            return
    elif mode == "host":
        name = args[1] if len(args) > 1 else "Host"
        srv = Server()
        srv.start()
        print(f"Sunucu başladı. Diğer bilgisayarlar şunu yazsın:\n"
              f"   python savas3d.py join {lan_ip()} <isim>")
        run_client("127.0.0.1", name)
    elif mode == "join":
        if len(args) < 2:
            print("Kullanım: python savas3d.py join <sunucu_ip> [isim]")
            return
        run_client(args[1], args[2] if len(args) > 2 else "Oyuncu")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
