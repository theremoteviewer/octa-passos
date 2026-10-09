; ---------------------------------------------------------------------------
; ab_glue -- the Analog BD's 808/909 engines at the per-track source stage, one copy per
; payload (tools/build/ab_image.py assembles it with both engines behind it,
; into the harvested SPRING REV's P region).
;
; The seam: the stock `move a,x:>$20e` just before the source (payload A
; P:0x39c, B P:0x1a2) is a jsr here. Every track's source record comes
; through; a record ab_render wrote for Analog BD carries a signature, and only
; then does the voice run. Anything else returns into the stock source
; untouched: the non-synth path clobbers only r4, b and x0, which the stock source
; loads before it reads (A P:0x39e.., B P:0x1a4..).
;
; The record, in DSP words (the ColdFire's 32-bit words as hi,lo 16-bit
; halves; control.c ab_render):
;   w0 $ab09, w2 $0909   the signature (stock w2 is the high half of a
;                        bounded ring position, never $0909; REVIEW.md)
;   w3                   1 when this frame carries the track's trig
;   w8..w19              the twelve knob bytes, 0..127
;
; The synth path also clobbers a, x1, y0/y1, r0/r1/r5/r6, n1/n7,
; m0/m1/m4/m5/m6 and condition codes; it continues after the stock source.
; An Analog BD track's voice block is X:VBASE + 2*x:$418 (x:$418 = 0/$20/$40/$60,
; the track within this core): the engine's state, then its knob block at
; +$30. The voice renders into X:0, where the stock source would have put
; the track's samples, and the stock code continues after the source (A
; P:0x426, B P:0x221): AMP, FX1, FX2 and the packer run unchanged.
; ---------------------------------------------------------------------------

zg01:
        move    a,x:>$20e               ; the stock instruction the jsr replaced
        move    x:>$209,r4              ; this track's source record
        move    #>$00ab09,x0
        move    x:(r4),b
        and     #>$ffff,b
        cmp     x0,b
        bne     zg02
        move    #>$000909,x0
        move    x:(r4+$2),b
        and     #>$ffff,b
        cmp     x0,b
        beq     zg03
zg02:
        rts                             ; not an Analog BD record: the stock source
zg03:
        move    x:>$20b,a               ; keep the next track's FLEX ring base
        add     #>$80,a
        move    a,x:>$20b
        move    x:>$418,a               ; the voice block
        asl     a
        move    x:(r4+$e),b            ; MODEL, masked transport byte
        and     #>$7f,b
; ⚠️ WHICH VOICE A MODEL RUNS IS A TABLE, NOT model!=0. With two models the
; test could be "zero is the 808"; a third model on the 808's voice would have
; been sent to the 909's engine and its state block. M_ENGINE[model] says which
; voice, and it is read HERE rather than in the engine because
; verify_analog_bd_exact drives the engines directly and never runs this glue --
; so the stock 808 and 909 stay bit-identical by construction.
        move    b1,n1
        move    #>@M_ENGINE@,r1
        move    x:(r1+n1),b
        move    #>@VBASE@,x0
        move    #>@V808@,x1
        tst     b
        move    x0,b
        teq     x1,b
        move    b,x0
        add     x0,a
        move    #>$ffffff,m5
        move    #>$ffffff,m6
        move    a1,r5
        lua     (r5+$30),r6             ; its knob block
        move    #>$ffffff,m0
        lua     (r4+$8),r0
        do      #<$c,zg04
        move    x:(r0)+,x0
        move    x0,a
        and     #>$7f,a
        move    a,x:(r6)+
zg04:
        move    x:>$20c,a               ; the trig's frame offset (stock, above
        move    #>$ffffff,x0            ; the seam), or -1: no trig this frame
        move    x:(r4+$3),b
        and     #>$ffff,b
        teq     x0,a
        move    a,x:(r6)
        lua     (r5+$30),r6
        move    #>$10,n7
        move    #$0,r0
        move    x:(r6+$6),a            ; MODEL -> which voice, via the same table
        move    a1,n1
        move    #>@M_ENGINE@,r1
        move    x:(r1+n1),a
        tst     a
        beq     zg05
; three voices now: 0 is the 808, below the midpoint core B's noise voice,
; above it the 909. Core B shares the 909's voice block, which is why the base
; chosen above is already right for it.
        move    #>@MIDNZ@,x1
        cmp     x1,a
        blt     zg08
        bsr     zq01
        bra     zg06
zg08:
        bsr     zn01
        bra     zg06
zg05:
; The 808 branch, and only here: this machine's body frequency into MB. The 909
; uses every state slot, so this write must never reach its block.
        move    x:(r4+$e),b
        and     #>$7f,b
        move    b1,n1
        move    #>@M_BASE@,r1
        move    x:(r1+n1),b
        move    b,x:(r5+$3d)
        bsr     zv01
zg06:
        move    ssh,x0                  ; drop the seam's return: the stock
        jmp     @CONT@                 ; source is skipped
