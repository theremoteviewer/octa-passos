#!/usr/bin/env python3
"""Choose Analog Bassdrum and select its engine using actual stock panel events.

Three port runs: LEFT back to the machine chooser, the engine pool selecting
the last row and then the first, and the LAST row left on screen -- the scroll
case.

⚠️ THE MODEL COUNT IS READ FROM control.c, NOT WRITTEN HERE. This gate had
`row count == 2` and reached "909" with a single DOWN, which lands on row 1
only when the list has exactly two rows. With seven rows it lands on row 6,
and the gate failed reporting "hidden MODEL encoder changed engine" -- a true
failure with a misleading name. Deriving the count means adding a machine
updates the gate instead of silently changing what it tests.

⚠️ THE LIST CLAMPS, IT DOES NOT WRAP, AND A KEY PRESS IS NOT ONE ROW. Measured
3 Oct 2026 on the port, four runs against the seven-row list: DOWN held 0.6 s
from row 0 lands on row 6; DOWN held 0.3 s twice lands on row 4; six of those
also land on 6; UP held 0.6 s from row 0 stays on 0; the LEVEL encoder does not
move the selection at all. One model fits all four: the stock list controller
auto-repeats while the key is held and clamps at both ends. So the only
DETERMINISTIC targets are the two ends, and that is what this gate navigates to
-- a middle row would be a timing assumption dressed up as a test. (909 is
covered by the descriptor checks below and, bit-exactly, by
tools/harness/verify_analog_bd_exact.py.)
"""
import json,os,pathlib,re,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/harness'))
sys.path.insert(0,str(ROOT/'tools/emu'))
from ab_fixture import prepare

CONTROL=(ROOT/'modules/analog-bassdrum/control.c').read_text()
def _define(name):
    return int(re.search(rf'^#define {name} (\d+)', CONTROL, re.M)[1])
MODELS=_define('AB_MODELS')      # rows in the engine list
ROWS=_define('AB_ROWS')          # rows the window shows at once
LABELS=re.findall(r'\{"(\d+ [^"]+)",', CONTROL)
assert len(LABELS)==MODELS, (len(LABELS), MODELS)
# Panel key codes are (row - 0x20) * 8 + bit of the UART matrix report, the
# form ot_emu's live script takes (main.cpp liveLine): down = [0x24, 0] = 0x20,
# up = [0x26, 3] = 0x33 (tools/panel/key_map.json, measured).
DOWN, UP = 0x20, 0x33
def key(code, gap=.6, hold=.6):
    return [(gap, f"key {code:#x} down"), (hold, f"key {code:#x} up")]
# Held long enough to auto-repeat past either end of the list, so they land on
# a known row whatever the row count is.
def END(): return key(DOWN, .6, 1.2)
def HOME(): return key(UP, .6, 1.2)


def window_bars(data):
    """[(x, y, w, h, widest run of ink)] for each visible popup window.

    The engine list is the stock sample pool's 110x64 window. A highlighted row
    is a filled rectangle about 105 px across; text never gives a run anywhere
    near that, so one number separates "a row is highlighted on screen" from
    "the selection is off screen". Reads the port's own window planes the way
    lcd_view.composite does.
    """
    import struct as _s
    import lcd_view
    out = []
    if len(data) == 1024:
        return out
    for i in range(lcd_view.WIN_SLOTS):
        e = lcd_view.WIN_TABLE + i * lcd_view.WIN_ENTRY
        x0, y0 = _s.unpack(">ii", data[e + 8:e + 16])
        flags, w, h = _s.unpack(">Iii", data[e + 32:e + 44])
        if not flags & 0x20 or not (0 < w <= 128 and 0 < h <= 64):
            continue
        col = (h + 31) // 32 * 4
        ink = lcd_view.WIN_PLANES + i * 0x400
        planes = [(int.from_bytes(data[ink + x * col:ink + x * col + col], "big"),
                   int.from_bytes(data[ink + lcd_view.WIN_MASK + x * col:
                                       ink + lcd_view.WIN_MASK + x * col + col], "big"))
                  for x in range(w)]
        best = 0
        for y in range(h):
            shift = col * 8 - 1 - (h - 1 - y)
            run = 0
            for a, m in planes:
                run = run + 1 if ((m >> shift) & 1 and (a >> shift) & 1) else 0
                best = max(best, run)
        out.append((x0, y0, w, h, best))
    return out
OUT=pathlib.Path(os.environ.get('AB_UI_OUT',ROOT/'out/analog-bassdrum/ui-gate')).resolve()
def main():
    src=os.environ.get('OT_PROJECT')
    if not src:
        print('[SKIP] Analog Bassdrum panel: set OT_PROJECT to a stock project fixture');return
    OUT.mkdir(parents=True,exist_ok=True)
    fixture=prepare(src,OUT/'project')
    card=OUT/'card.img'
    subprocess.run([sys.executable,str(ROOT/'tools/emu/ot_emu/stage_card.py'),str(fixture),'OCTABAM','RIG','--tree',str(OUT/'tree'),'--out',str(card)],check=True,cwd=ROOT)
    image=OUT/'image.bin';shutil.copy2(os.environ.get('AB_IMAGE',ROOT/'out/mainos_bus.bin'),image)
    sym={l.split()[-1]:int(l.split()[0],16) for l in subprocess.check_output(['m68k-elf-nm',str(ROOT/'out/platform/runtime/runtime.elf')],text=True).splitlines() if len(l.split())==3}
    if os.environ.get('AB_SYMBOLS'): sym=json.loads(pathlib.Path(os.environ['AB_SYMBOLS']).read_text())
    spans=f'0x40170f60,6322={OUT}/part.bin;{sym["desc"]:#x},916={OUT}/desc.bin;0x400d5f4c,4={OUT}/page.bin;0x460e70e0,4={OUT}/pool.bin;0x400bb7d0,4={OUT}/setup.bin;0x460e5e30,28={OUT}/list.bin;0x100a4ece,6322={OUT}/shadow.bin;0x80000830,1={OUT}/live.bin;0x460e738e,16={OUT}/navigation.bin'
    cmd=[os.environ.get('AB_EMU',str(ROOT/'out/emu/ot_emu')),'--image',str(image),'--card',str(card),'--set','OCTABAM','--project','RIG','--load-ms','20000','--dsp','--mem-dump',spans]
    cmd += ["--lcd", str(OUT/"lcd.bin")]
    # T1 -> SRC SETUP -> bottom row -> YES; the former MODEL encoder is inert.
    script=key(0x10)+[(.6,'key 0x2d down'),(.3,'key 0x22 down'),(.3,'key 0x22 up'),(.3,'key 0x2d up')]
    for _ in range(6):script+=key(0x20,.25,.25)
    script+=key(0x31)
    script+=[(.8,'enc 0 16'),(.8,'enc 2 -4')]
    # Close setup, then double-tap T1 with a 210 ms down-to-down gap.
    script+=key(0x32)+[(.6,'key 0x10 down'),(.06,'key 0x10 up'),
                      (.15,'key 0x10 down'),(.06,'key 0x10 up')]
    # Navigate to the machine column and back, as with STATIC/FLEX.
    # A disabled draw bit alone does not stop the stock editor. Select the LAST
    # row, turn the old MODEL encoder backwards, and ensure it stays selected.
    left_script=script+END()+key(0x31)
    left_script += [(.6,'key 0x2d down'),(.3,'key 0x22 down'),(.3,'key 0x22 up'),(.3,'key 0x2d up'),(.8,'enc 0 -16')]
    left_script += key(0x32)+[(.6,'key 0x10 down'),(.06,'key 0x10 up'),(.15,'key 0x10 down'),(.06,'key 0x10 up')]+key(0x34)+[(.8,'quit')]
    script+=key(0x34)
    # Visit FLEX's real sample column, then return to Analog BD's engine column.
    for _ in range(4): script+=key(0x33,.25,.25)
    script+=key(0x21)+key(0x34)
    for _ in range(4): script+=key(0x20,.25,.25)
    script+=key(0x21)
    # Select the last row through the pool, then return and select the first.
    script+=END()+key(0x31)
    script+=[(.6,'key 0x10 down'),(.06,'key 0x10 up'),(.15,'key 0x10 down'),(.06,'key 0x10 up')]
    # Select row 0 from the list, then reopen: the highlight must follow the
    # stored model -- which means scrolling back UP from the end as well.
    script+=HOME()+key(0x31)
    script+=[(.6,'key 0x10 down'),(.06,'key 0x10 up'),(.15,'key 0x10 down'),(.06,'key 0x10 up'),(.8,'quit')]
    # Browse away and cancel; reopening must still select row 0.
    script=script[:-1]+END()+key(0x32)
    script+=[(.6,'key 0x10 down'),(.06,'key 0x10 up'),(.15,'key 0x10 down'),(.06,'key 0x10 up'),(.8,'quit')]
    elapsed=0; left_events=[]
    for delay,event in left_script:
        elapsed+=round(delay*1000)
        left_events.append(f'{elapsed} {event}\n')
    leftfile=OUT/'left-events.txt';leftfile.write_text(''.join(left_events))
    with (OUT/'left-port.log').open('w') as log:
        subprocess.run(cmd+['--live-script',str(leftfile)],cwd=ROOT,
                       stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
    assert int.from_bytes((OUT/'pool.bin').read_bytes(),'big')!=0, 'LEFT did not open machine chooser'
    assert int.from_bytes((OUT/'list.bin').read_bytes()[:4],'big')==0, 'LEFT left engine list open'
    nav=(OUT/'navigation.bin').read_bytes()
    assert (OUT/'part.bin').read_bytes()[0x1da+6]==MODELS-1, \
        ('the inert MODEL encoder changed the engine, or the list did not reach '
         'its last row', (OUT/'part.bin').read_bytes()[0x1da+6], MODELS-1)
    assert int.from_bytes(nav[:4],'big')==5, 'LEFT did not highlight Analog BD'
    assert int.from_bytes(nav[12:16],'big')==0, 'LEFT did not select machine column'
    shutil.copy2(OUT/'lcd.bin',OUT/'left-lcd.bin')
    elapsed=0; events=[]
    for delay,event in script:
        elapsed+=round(delay*1000)
        events.append(f'{elapsed} {event}\n')
    eventfile=OUT/'events.txt';eventfile.write_text(''.join(events))
    with (OUT/'port.log').open('w') as log:
        subprocess.run(cmd+['--live-script',str(eventfile)],cwd=ROOT,
                       stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
    part=(OUT/'part.bin').read_bytes()
    assert part[0x22]==1 and part[60:63]==b'AB\x01', ('Analog BD selection did not land',part[0x22],part[60:63])
    assert int.from_bytes((OUT/'pool.bin').read_bytes(),'big')==0, 'sample pool opened'
    listing=(OUT/'list.bin').read_bytes()
    assert int.from_bytes(listing[:4],'big')!=0, 'engine list did not open'
    assert int.from_bytes(listing[16:20],'big')==0, 'engine list highlight did not follow 808'
    assert int.from_bytes(listing[24:28],'big')==MODELS, ('engine list row count',
                 int.from_bytes(listing[24:28],'big'), MODELS)
    assert (OUT/'shadow.bin').read_bytes()[0x1da+6]==0
    assert (OUT/'live.bin').read_bytes()==b'\0'
    log=(OUT/'port.log').read_text();assert 'ILLEGAL' not in log and 'ended on quit' in log
    part=(OUT/'part.bin').read_bytes();desc=(OUT/'desc.bin').read_bytes()
    assert part[0x22]==1 and part[60:63]==b'AB\x01',('selection',part[0x22],part[60:63])
    assert 64 < part[0x1da+8] < 127, ('LPF encoder',part[0x1da+8])
    assert part[0x1da+6]==0,('MODEL',part[0x1da+6])
    assert list(part[48:54])==[64,80,80,64,64,0],list(part[48:54])
    assert desc[0x4e+6*6:0x4e+6*6+6]==bytes(6)
    assert int.from_bytes(desc[0xd2+4*6:0xd2+4*7],'big')==0
    assert int.from_bytes((OUT/'page.bin').read_bytes(),'big')==sym['desc']+0x38, 'MODEL page did not change'
    for model in (0,1):
        d=desc[model*458:(model+1)*458]
        assert d[0x4e+2*6:0x4e+2*6+6]==(b'TONE\0\0' if model==0 else b'TUNE\0\0')
        assert d[0x4e+8*6:0x4e+8*6+6]==b'LPF\0\0\0'
        assert int.from_bytes(d[0x1c2:0x1c6],'big')==0x111
        assert int.from_bytes(d[0x1c6:0x1ca],'big')==0x10111111
        assert d[0x96+8]==127
        assert d[0x4e+5*6:0x4e+6*6] == b'SAT\0\0\0'
        assert d[0x96+9:0x96+11] == bytes([64,64])
        assert int.from_bytes(d[0x132+4*6:0x136+4*6],"big")==0
        assert int.from_bytes(d[0x162+4*6:0x166+4*6],"big")==0
        if model:
            assert d[0x4e+9*6:0x4e+11*6] == b'LOW\0\0\0HIGH\0\0'
    print('PASS chooser: Analog Bassdrum, defaults, hidden MODEL encoder is inert and LPF remains editable; LEFT returns to machine chooser, FLEX/AB horizontal navigation, engine pool selects the last row then row 0, cancels a browse and reopens on row 0')

    # ---- the scroll case -------------------------------------------------
    # Jesse, on the ten-row build: "the window would not scroll down past the
    # 6th entry." ab_engine_open tells the stock controller the viewport is
    # AB_ROWS lines; ab_engine_draw used to paint every entry from the top of
    # the window and ignore the selection, so the controller's selection moved
    # down the list and the drawing never followed it. Selecting the LAST row
    # is the case that was broken, and the proof is PIXELS: the highlight is a
    # filled rectangle over the selected line, so if the window scrolled, the
    # list area has an inverted band; if it did not, the selected row is off
    # screen and there is none.
    if MODELS > ROWS:
        # ⚠️ ITS OWN SHORT SCRIPT, AND NO YES. Built from the long chooser
        # script this run took over 600 s and stalled in the card reads; it
        # also does not need to COMMIT a row -- the question is whether the
        # window follows the selection, so it ends with the list still open on
        # the last row and the LCD dumped there.
        ls=key(0x10)+[(.6,'key 0x2d down'),(.3,'key 0x22 down'),(.3,'key 0x22 up'),(.3,'key 0x2d up')]
        for _ in range(6): ls+=key(0x20,.25,.25)
        ls+=key(0x31)+key(0x32)
        ls+=[(.6,'key 0x10 down'),(.06,'key 0x10 up'),
             (.15,'key 0x10 down'),(.06,'key 0x10 up')]
        ls+=END()+[(.8,'quit')]
        elapsed=0; events=[]
        for delay,event in ls:
            elapsed+=round(delay*1000)
            events.append(f'{elapsed} {event}\n')
        lastfile=OUT/'last-events.txt'; lastfile.write_text(''.join(events))
        subprocess.run([sys.executable,str(ROOT/'tools/emu/ot_emu/stage_card.py'),str(fixture),
                        'OCTABAM','RIG','--tree',str(OUT/'tree'),'--out',str(card)],check=True,cwd=ROOT)
        with (OUT/'last-port.log').open('w') as log:
            subprocess.run(cmd+['--live-script',str(lastfile)],cwd=ROOT,
                           stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
        shutil.copy2(OUT/'lcd.bin',OUT/'last-lcd.bin')
        listing=(OUT/'list.bin').read_bytes()
        assert int.from_bytes(listing[:4],'big')!=0, 'the engine list is not open'
        assert int.from_bytes(listing[24:28],'big')==MODELS, 'row count'
        sel=int.from_bytes(listing[16:20],'big')
        assert sel==MODELS-1, ('holding DOWN did not reach the last row -- the '
                               'stock list controller clamps, see the header', sel)
        log=(OUT/'last-port.log').read_text()
        assert 'ILLEGAL' not in log and 'ended on quit' in log
        # ⚠️ THE WINDOW'S OWN INK, NOT THE COMPOSITED SCREEN. The page behind
        # the popup has a 112 px solid run of its own, so a screen-wide scan
        # passes whatever the list draws -- the instrument has to be able to
        # see the absence it is being used to rule out.
        bars=window_bars((OUT/'last-lcd.bin').read_bytes())
        widest=max([b for *_,b in bars] or [0])
        assert widest>=60, ('row %d is selected and no row is highlighted inside '
                            'the list window -- the window did not scroll' % sel, bars)
        print(f'PASS scroll: holding DOWN reaches row {sel} ({LABELS[sel]}) of {MODELS} '
              f'in a {ROWS}-row window, and its highlight is on screen '
              f'(widest lit run {widest} px)')


if __name__=='__main__':main()
