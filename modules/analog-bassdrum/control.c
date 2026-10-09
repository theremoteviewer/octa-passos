/* Native source renderer + stock-page registration, derived from the measured
 * Machinedrum Part/chooser seams and the stock kind-table renderer ABI.
 * The synthesis is upstream of AMP and both FX slots: 808 and 909 on the DSP via ab_glue.asm.
 */
#include "engine.h"
#define U8(a) (*(volatile uint8_t *)(uintptr_t)(a))
#define U32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define BANK 0x46c82456u
#define PART_IDX 0x100b14cfu
#define PART_OFF 0x8ed80u
#define PART_STRIDE 0x18b2u
#define SIG 60u
#define DESC_SIZE 0x1cau
/* ---- the machine table -------------------------------------------------
 * One row per entry in the engine browser. `engine` is which DSP voice runs
 * it; `tables` is the index of its coefficient set within that voice, so
 * several machines share one engine and differ only in their tables -- which
 * is how the Machinedrum's own families are built (out/md-machines/NOTES.md
 * section 11.3: two signal paths cover twenty-one machines).
 *
 * Adding a row here adds a browser entry, a page descriptor and a stored
 * MODEL id. It adds DSP CODE only if `engine` is one that does not exist yet.
 */
#define AB_MODELS 11
/* ⚠️ THE VIEWPORT COUNT IS SHARED BY THE OPEN CALL AND THE DRAW, and the first
 * ten-entry build proved why it has to be one constant: open told the stock
 * list controller six rows, draw painted all AB_MODELS from the top of the
 * window and ignored the scroll entirely. With two models that is invisible;
 * with ten the list would not move past the sixth entry (Jesse, 3 Oct 2026). */
#define AB_ROWS 6
static const struct ab_model {
    const char *label;
    const char *names[12];
    unsigned engine;          /* 0 = the 808 voice, 1 = the 909 voice.
                                 MUST match dsp808.MACHINE_ENGINE, which is
                                 what the glue reads to route the voice. */
    const uint8_t defaults[12];
} ab_models[AB_MODELS] = {
    /* ---- the body oscillator: kicks, and anything else pitched ---------
     * ⚠️ A TOM IS THIS ENGINE TUNED UP, and that is not a cheat: it is why one
     * voice covers kick and tom on every drum machine ever built. The rows
     * were pulled on 3 Oct 2026 when the browser was NOTHING but body
     * variants; with six other mechanisms beside them they read as toms.
     * Their base frequency is dsp808.MACHINE_BASE_HZ -- one already-allocated
     * X word each and no P words at all.
     */
    {"001 808", {"PITCH","DECAY","TONE","ATK","SWEEP","SAT","","ACCNT","LPF","LOW","HIGH","---"}, 0,
     {64, 80, 80, 64, 64, 0, 0, 64, 127, 64, 64, 0}},
    {"002 909", {"PITCH","DECAY","TUNE","ATK","TDEP","SAT","","ACCNT","LPF","LOW","HIGH","---"}, 1,
     {64, 80, 80, 64, 64, 0, 1, 64, 127, 64, 64, 0}},
    /* ---- band-passed noise: the Machinedrum hats -----------------------
     * The only two engines here with MEASURED targets -- band and -30 dB
     * point from emulator captures of the real machine. CH came back at
     * Jesse's request, 5 Oct 2026.
     */
    {"003 TRX CH", {"PITCH","DECAY","WIDTH","SWEEP","ATK","DRIVE","","ACCNT","--","--","--","---"}, 2,
     {64, 64, 64, 64, 64, 0, 2, 100, 127, 64, 64, 0}},
    {"004 TRX OH", {"PITCH","DECAY","WIDTH","SWEEP","ATK","DRIVE","","ACCNT","--","--","--","---"}, 2,
     {64, 64, 64, 64, 64, 0, 3, 100, 127, 64, 64, 0}},
    /* ---- the other mechanisms ------------------------------------------
     * ⚠️ EVERY KNOB IS NAMED PER ENGINE because it MEANS something different
     * per engine: a filter corner on the hat, a dry/wet on the snare, how
     * much room on the clap, the modulator ratio on the FM. One knob called
     * WIDTH meaning five things is how a user learns to distrust the labels.
     *
     * ⚠️ AND EVERY ROW NAMES SIX, which is Jesse's own ask on 5 Oct 2026 --
     * "not all of the parameters work. In fact I'd like each of the drums to
     * have 6 parameters". Six rows named three and left three drawing "--",
     * and a knob that is named but read by nothing is the worse half of the
     * same complaint: it draws, it moves, it stores into the Part and it
     * changes nothing. `tools/harness/bdnoise.py` now renders every named
     * knob at 20 and at 110 and refuses one whose output does not move;
     * `tools/verify/verify_drum_rows.py` refuses a row that names fewer
     * than six.
     *
     * ⚠️ KNOBS 3 AND 4 DEFAULT TO 64 AND KNOB 5 TO 0, AND EVERY ENGINE IS
     * NEUTRAL THERE. A row's defaults apply only to a NEW assignment, so a
     * track that existed before this build arrives holding exactly these
     * three bytes -- whatever the engine reads in them has to be the machine
     * as it was measured, or a build that only ADDED parameters detunes every
     * stored Part. So knob 3 and knob 4 are centred on the fixed constant
     * each one replaced, and knob 5 (DRIVE, on every one of these rows) is
     * unity gain at zero.
     */
    {"005 PL HAT", {"PITCH","DECAY","METAL","SPRD","RES","DRIVE","","ACCNT","--","--","--","---"}, 2,
     {64, 64, 64, 64, 64, 0, 4, 100, 127, 64, 64, 0}},   /* six oscillators */
    {"006 PL SNR", {"PITCH","DECAY","SNAP","RATIO","NDEC","DRIVE","","ACCNT","--","--","--","---"}, 2,
     {64, 64, 64, 64, 64, 0, 5, 100, 127, 64, 64, 0}},   /* bodies + wires */
    {"007 PL CLP", {"PITCH","DECAY","ROOM","SPRD","REPS","DRIVE","","ACCNT","--","--","--","---"}, 2,
     {64, 64, 64, 64, 64, 0, 6, 100, 127, 64, 64, 0}},   /* a burst train */
    {"008 PL FM", {"PITCH","DECAY","RATIO","INDEX","IDEC","DRIVE","","ACCNT","--","--","--","---"}, 2,
     {64, 64, 64, 64, 64, 0, 7, 100, 127, 64, 64, 0}},   /* two-operator FM */
    {"009 PL TOM", {"PITCH","DECAY","TONE","ATK","SWEEP","SAT","","ACCNT","LPF","LOW","HIGH","---"}, 0,
     {64, 56, 80, 64, 64, 0, 8, 100, 127, 64, 64, 0}},   /* a body at 180 Hz */
    {"010 PL CNG", {"PITCH","DECAY","TONE","ATK","SWEEP","SAT","","ACCNT","LPF","LOW","HIGH","---"}, 0,
     {64, 40, 80, 64, 64, 0, 9, 100, 127, 64, 64, 0}},   /* a body at 310 Hz */
    /* ---- four tuned resonators struck by a noise burst -----------------
     * Jesse, 5 Oct 2026: "Also interested in the rings algo." A modal
     * resonator bank: the partials' spacing, the strike's brightness and
     * which partials are emphasised, with the POLE RADIUS as the decay so
     * four partials ring for four different lengths. Not a port of Mutable
     * Instruments' Rings and not matched to it -- modules/analog-bassdrum/
     * bdring.asm says why, and credits it.
     */
    {"011 PL RNG", {"PITCH","DECAY","STRUC","BRITE","POS","DRIVE","","ACCNT","--","--","--","---"}, 2,
     {64, 64, 64, 64, 64, 0, 10, 100, 127, 64, 64, 0}},  /* resonator bank */
};
static uint8_t desc[AB_MODELS][DESC_SIZE] = {{0}};
uint32_t ab_desc_p = 0;
uint32_t ab_render_calls = 0, ab_hits = 0;
static unsigned signed_track(const volatile uint8_t *part, unsigned t) {
    const volatile uint8_t *s=part+SIG+30*t;
    return t<8 && part[0x22+t]==1 && s[0]=='A' && s[1]=='B' && s[2]==1;
}
/* Each core owns four independent voice slots, addressed by track. */
unsigned ab_admit_track(const volatile uint8_t *part, unsigned track) {
    (void)part;
    return track<8;
}
static volatile uint8_t *part_base(void) {
    return (volatile uint8_t *)(uintptr_t)(U32(BANK)+PART_OFF+(U8(PART_IDX)&3)*PART_STRIDE);
}
/* Track double-tap must not open FLEX's sample pool for a synthesized source. */
unsigned ab_selected_source(void) {
    unsigned track=U8(0x100b14ccu);
    return !U8(0x80000015u) && track<8 && signed_track(part_base(),track);
}
unsigned ab_type(unsigned type, const volatile uint8_t *ptr) {
    volatile uint8_t *part=part_base();
    uintptr_t t=(uintptr_t)ptr-(uintptr_t)(part+0x22);
    return type==1 && t<8 && signed_track(part,(unsigned)t) ? 5 : type;
}
static void put32(uint8_t *p,uint32_t v) {
    p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v;
}
static void text(uint8_t *p,const char *s,unsigned n) {
    unsigned i=0; for (;i+1<n && s[i];++i) p[i]=(uint8_t)s[i];
    for (;i<n;++i) p[i]=0;
}
void ab_lpf_fmt(char *out,int value) {
    if(!value) { text((uint8_t*)out,"OFF",4); return; }
    if(value==64) { text((uint8_t*)out,"ORIG",5); return; }
    unsigned hz=ab_lpf_frequency((unsigned)value),n=0;
    char digits[5];
    do { digits[n++]=(char)('0'+hz%10); hz/=10; } while(hz && n<5);
    unsigned i=0; while(n) out[i++]=digits[--n]; out[i]=0;
}
static uint32_t page_for(unsigned model) {
    if (!ab_desc_p) {
        const volatile uint8_t *src=(const volatile uint8_t *)0x400d3176u;
        for(unsigned m=0;m<AB_MODELS;++m) {
            uint8_t *d=desc[m];
            for(unsigned i=0;i<DESC_SIZE;++i) d[i]=src[i];
            text(d+0x3c,"DRUM",5); text(d+0x41,"DRUMS",13);
            for(unsigned i=0;i<12;++i) {
                text(d+0x4e + 6*i,ab_models[m].names[i],6);
                d[0x96+i]=ab_models[m].defaults[i];
                put32(d+0xa2+4*i,0);
                put32(d+0xd2+4*i,i==6?0:128);
                put32(d+0x102+4*i,i==8 ? (uint32_t)(uintptr_t)ab_lpf_fmt:0);
                put32(d+0x132+4*i,0);
                put32(d+0x162+4*i,0);
            }
            put32(d+0x1c2,0x111); put32(d+0x1c6,0x10111111u);
        }
        ab_desc_p=(uint32_t)(uintptr_t)(desc[0]+0x38);
    }
    return (uint32_t)(uintptr_t)(desc[model<AB_MODELS?model:0]+0x38);
}
uint32_t ab_track_page(const volatile uint8_t *type_ptr) {
    volatile uint8_t *part=part_base();
    uintptr_t track=(uintptr_t)type_ptr-(uintptr_t)(part+0x22);
    return page_for(track<8 ? part[0x1da+6+30*track] : 0);
}
void ab_ui_tick(void) {
    if(U32(BANK)<0x40000000u || U32(BANK)>=0x48000000u) {
        U32(0x400d5f38u+5*4)=page_for(0); return;
    }
    volatile uint8_t *part=part_base();
    U32(0x400d5f38u+5*4)=ab_track_page(part+0x22+(U8(0x100b14ccu)&7));
}
/* Validator temporarily sees stock FLEX defaults for every AB track. All
 * twelve original bytes are restored. Every other Part byte is checked by
 * stock's real validator. The assembly trampoline skips our own detour. */
extern int ab_stock_validate(void *part);
int ab_validate_part(uint8_t *part) {
    uint8_t saved[8][12]; unsigned mask=0;
    const volatile uint8_t *stock=(const volatile uint8_t *)0x400d320cu;
    for(unsigned t=0;t<8;++t) if(signed_track(part,t)) {
        mask|=1u<<t;
        for(unsigned k=0;k<12;++k) {
            unsigned at=(k<6?0x2a:0x1da)+30*t+6+k%6;
            saved[t][k]=part[at]; part[at]=stock[k];
        }
    }
    int result=ab_stock_validate(part);
    for(unsigned t=0;t<8;++t) if(mask&(1u<<t))
        for(unsigned k=0;k<12;++k) {
            unsigned at=(k<6?0x2a:0x1da)+30*t+6+k%6;
            part[at]=saved[t][k];
        }
    return result;
}
/* ABI measured at 4000d430/4000d518. Every track is rendered twice per
 * frame around its event's sample offset; the second call has end=16.
 * Header: source count, ring start, Q26 source rate, Q26 read position.
 * Stock transport converts the high 24 bits of each L/R long to DSP words.
 */
int ab_render(unsigned track,unsigned ping,unsigned start,unsigned end) {
    if(track>=8 || !signed_track(part_base(),track)) {
        return ((int (*)(unsigned,unsigned,unsigned,unsigned))0x40004008u)(track,ping,start,end);
    }
    ++ab_render_calls;
    volatile uint32_t *cursor=(volatile uint32_t *)(uintptr_t)U32(0x80001c80u);
    volatile uint16_t *fp=(volatile uint16_t *)(uintptr_t)U32(0x800062a8u);
    uint8_t p[12];
    for(unsigned k=0;k<12;++k) {
        p[k]=k<6 ? (uint8_t)(fp[k]>>8)
                 : U8(0x80000810u+72*track+0x20+k-6);
    }
    /* The stock builder calls twice, before and after the event offset.
     * Reserve the same space as FLEX so every later track keeps its record
     * boundary. Once the second segment exists, replace the start with a
     * control record: two signature halves, trig flag, then twelve knobs.
     * The transport sends each long as high/low 16-bit DSP words. */
    {
        unsigned n=end>start && end<=16 ? end-start:0;
        for(unsigned i=0;i<4+2*n;++i) cursor[i]=0;
        if(end==16) {
            /* On the first hit the first renderer can still be stock FLEX.
             * Use the packer's fixed slot, not that second call's cursor. */
            volatile uint32_t *record=(volatile uint32_t *)(uintptr_t)
                (0x80001c90u+(ping&1)*0xa80u+336u*track);
            unsigned trig=(U8(0x46104d0cu+track)&16)!=0;
            record[0]=0xab090000u; record[1]=0x09090000u|trig;
            record[2]=record[3]=0;
            for(unsigned k=0;k<6;++k) record[4+k]=((uint32_t)p[2*k]<<16)|p[2*k+1];
            if(trig) ++ab_hits;
        }
        U32(0x80001c80u)=(uint32_t)(uintptr_t)(cursor+4+2*n);
        return 0;
    }
}

/* Sample-pool sized engine browser: stock list navigation and window chrome.
 * Pin the destination at open, so a track/Part change cannot edit another voice.
 * Entries retain the stored MODEL ids; adding a label alone never adds DSP code.
 */
static uint32_t engine_bank = 0;
static unsigned engine_part = 0, engine_track = 0;
void ab_engine_select(unsigned model) {
    unsigned track=engine_track, part=engine_part;
    if(model>=AB_MODELS || U32(BANK)!=engine_bank || (U8(PART_IDX)&3)!=part ||
       U8(0x100b14ccu)!=track || !ab_selected_source()) return;
    unsigned offset=0x1da+6+30*track;
    part_base()[offset]=(uint8_t)model;
    U8(0x100a4eceu+PART_STRIDE*part+offset)=(uint8_t)model;
    U8(0x80000830u+72*track)=(uint8_t)model;
    /* Same dirty flags and bank notification as the stock SRC SETUP editor. */
    U8(engine_bank+0x95048u)|=(uint8_t)(1u<<part);
    U8(0x100b145eu)|=(uint8_t)(1u<<part);
    U32(engine_bank+0x9b332u)=1;
    U32(0x100f8598u)=1;
    ((void (*)(void))0x40027e00u)();
    ab_ui_tick();
    ((void (*)(void))0x4004d948u)();
}
/* One thunk per row: the stock list controller calls handlers[row](). */
#define AB_ENGINE_THUNK(n) static void engine_##n(void) { ab_engine_select(n); }
AB_ENGINE_THUNK(0)
AB_ENGINE_THUNK(1)
AB_ENGINE_THUNK(2)
AB_ENGINE_THUNK(3)
AB_ENGINE_THUNK(4)
AB_ENGINE_THUNK(5)
AB_ENGINE_THUNK(6)
AB_ENGINE_THUNK(7)
AB_ENGINE_THUNK(8)
AB_ENGINE_THUNK(9)
static const char *engine_labels[AB_MODELS];
unsigned ab_engine_draw(void) {
    uint32_t window=U32(0x460e5e30u);
    if(!window || U32(0x460e5e2cu)!=(uint32_t)(uintptr_t)engine_labels) return 0;
    void *surface=(void *)(uintptr_t)(window+0x24);
    ((void (*)(void *))0x4003567cu)(surface);
    int height=(int)U32(window+0x28);
    /* Scroll the window to follow the selection, and draw by SLOT rather than
     * by index: slot i is always the i'th line down the window, whatever row
     * it is showing. Derived from the selection the controller already
     * publishes, so there is no guess about where it keeps its own offset. */
    unsigned sel=U32(0x460e5e40u), first=0;
    if(AB_MODELS>AB_ROWS) {
        unsigned last=AB_MODELS-AB_ROWS;   /* only evaluated where it is >= 0 */
        if(sel>=AB_ROWS) first=sel-AB_ROWS+1;
        if(first>last) first=last;
    }
    for(unsigned i=0;i<AB_ROWS && first+i<AB_MODELS;++i) {
        unsigned row=first+i;
        int y=height-23-7*(int)i;
        ((void (*)(uint32_t,void *,int,int,int,const char *))0x40012bd8u)
            (0x400ba876u,surface,5,y,-1,engine_labels[row]);
        if(row==sel)
            ((void (*)(void *,int,int,int,int,int))0x40012254u)
                (surface,3,y-1,(int)U32(window+0x24)-5,y+5,-1);
    }
    U32(0x46c7c72cu)=1;
    return 1;
}
void ab_engine_open(void) {
    static void (*const handlers[AB_MODELS])(void)={engine_0, engine_1, engine_2, engine_3,
       engine_4, engine_5, engine_6, engine_7, engine_8, engine_9};
    for(unsigned m=0;m<AB_MODELS;++m) engine_labels[m]=ab_models[m].label;
    if(!ab_selected_source() || U32(0x460e5e30u)) return;
    engine_bank=U32(BANK);
    engine_part=U8(PART_IDX)&3;
    engine_track=U8(0x100b14ccu);
    unsigned model=part_base()[0x1da+6+30*engine_track];
    /* A Part saved under a shorter list can carry an id this build does not
     * implement; the stock list controller would use it as an index. */
    if(model>=AB_MODELS) model=0;
    /* Use the stock sample pool's 110 x 64 window at x=-1, y=0.
     * The stock list controller supplies arrows, LEVEL, YES and NO; only
     * its row content and drawing differ from the ordinary sample browser.
     */
    ((void (*)(uint32_t,unsigned,unsigned))0x4007ec60u)
        (0x460e5e38u,AB_ROWS,AB_MODELS);
    ((void (*)(uint32_t,unsigned))0x4007edb0u)(0x460e5e38u,model);
    U32(0x460e5e28u)=(uint32_t)(uintptr_t)handlers;
    U32(0x460e5e2cu)=(uint32_t)(uintptr_t)engine_labels;
    U32(0x460e5e34u)=0;
    uint32_t window=((uint32_t (*)(int,int,int,int,int,uint32_t))0x4005829cu)
        (110,64,-1,0,1,0x4006d754u);
    U32(0x460e5e30u)=window;
    if(!window) return;
    ((void (*)(uint32_t,const char *,unsigned))0x400570b8u)(window,"\xab MACHINE:DRUMS",0);
    ((void (*)(uint32_t))0x40031494u)(0x400ce0c4u);
    ab_engine_draw();
}

/* Horizontal navigation mirrors STATIC/FLEX: LEFT returns to the machine
 * column, RIGHT on the signed Analog BD row returns to its engine pool.
 * Other generic lists keep their original no-op LEFT binding. */
extern void ab_stock_pool_open(void);
void ab_engine_left(void) {
    if(!U32(0x460e5e30u) ||
       U32(0x460e5e2cu)!=(uint32_t)(uintptr_t)engine_labels) return;
    ((void (*)(void))0x4006d754u)();
    ab_stock_pool_open();
    ((void (*)(void))0x4007893cu)();
}
void ab_engine_right(unsigned key,unsigned value) {
    if(U32(0x460e70e0u) && !U32(0x460e739au) &&
       U32(0x460e738eu)==5 && ab_selected_source()) {
        ((void (*)(void))0x400789e4u)();
        ab_engine_open();
        return;
    }
    ((void (*)(unsigned,unsigned))0x4007909cu)(key,value);
}
