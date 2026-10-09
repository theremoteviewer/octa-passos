; ---------------------------------------------------------------------------
; RESONATOR -- eight tuned state-variable filters the track's own audio rings
; through. An insert: assignable to FX1 or FX2, no buffers, no bus role.
;
; Insert contract: frames in place at x:(r0) / x:(r0+n0) with n0 = 1, sixteen
; of them (n7), knobs from r6, state in this instance's r7 block.
;
; ⚠️ NOT A PORT OF MUTABLE INSTRUMENTS' RINGS. Jesse asked for "the rings algo
; as an assignable effect so any sound could ring through its resonator"
; (5 Oct 2026); Rings is MIT-licensed, (c) Emilie Gillet, and its sources could
; not be fetched in the session that wrote this file -- GitHub is unreachable
; from that sandbox, it has no API access to the repository, and routing around
; a blocked fetch is not allowed -- with no Rings in the container to capture
; reference audio from either. Every number here is this module's own and what
; it claims is structural.
;
;   (L+R)/2 -> one-pole (BRITE) -> the exciter buffer
;                                      |
;   8 x  Chamberlin SVF, band output    (PITCH, STRUC, DECAY, TILT)
;                                      |
;                        summed -> MIX -> back into the frames
;
; ⚠️ AN SVF PER PARTIAL, NOT THE TWO-POLE DIRECT FORM THE DRUM ROW USES, AND
; THE REASON IS GAIN. A two-pole resonator's impulse gain is 1/sin(w) -- twelve
; times larger at 563 Hz than at 5.9 kHz -- so a bank of them fed ONE signal is
; a fundamental with seven whispers behind it unless every partial carries a
; compensating weight, which costs a word of state and a multiply each, and
; (worse) makes the low partials' STATE saturate while the output is still
; quiet. modules/analog-bassdrum/bdring.asm records what that cost the drum
; row. An SVF's band-pass peak gain is its Q, the same at every frequency, so
; this bank needs no weights at all -- and its ring time is 2Q/w, so at one Q
; the high partials ring SHORTER, which is what a struck object does and what
; the drum row has to fake with per-partial decay offsets.
;
; ⚠️ A HIGH-Q RESONATOR FED A SUSTAINED TONE AT ITS OWN FREQUENCY RINGS UP BY Q,
; AND NOTHING HERE PREVENTS THAT. Impulse gain is about f (0.08 at 563 Hz) and
; sustained gain is Q (up to 1200): eighty dB apart, which no single input
; scale serves. The level here is set for transients -- a drum hit, a pluck, a
; percussive loop, which is what the effect is for -- and a sustained tone at a
; partial's frequency drives the filter into the state store's limiter, i.e.
; into soft clipping rather than into a number that wraps. That is the same
; behaviour a struck bowl has when you play a loud sine at it. MIX and the
; track level are the controls for it, and verify_resonator holds the OUTPUT to
; full scale and to silence after the input stops.
;
; ---- r7 slots ------------------------------------------------------------
;   $20..$3f  eight resonators, four words each: band, low, f/2, damp/2
;   $40 the exciter's one-pole state   $41 its corner coefficient
;   $42 wet   $43 dry
;   $45 STRUC as knob/128   $46 the fundamental's index   $47 the Q base index
;   $48 the per-partial Q step (signed)   $49 the running Q index
;   $4a the P table's base
;   $60..$6f the exciter buffer (16, modulo-addressed)
;   $70..$7f the output accumulator (16, modulo-addressed)
; Every one of them is written before it is read in a block, except the eight
; resonators' band/low and the exciter's pole, which init zeroes -- the
; "a persistent slot that init does not clear" trap (AGENTS.md): this id's
; previous occupant was the stock COMPRESSOR and its leftovers are a filter
; mid-swing, which a Q of 1200 would ring on for ever.
;
; Every mpy is y0,x0 or x0,y1 -- the signed encodings AGENTS.md audits. No Tcc
; shares a compare with anything but moves between.
; ---------------------------------------------------------------------------

init:
; ⚠️ PRESERVE r1: the FX1 dispatcher keeps the effect id there ACROSS the init
; call (AGENTS.md; P:0x4c8), so an init that moves it sends the proc call
; through a garbage word and the core dies at project load. Zero through r4.
        move    #>$ffffff,m4
        move    r7,r4
        move    #>$20,n4
        move    (r4)+n4
        clr     a
        do      #$30,rz_zst             ; $20..$4f
        move    a,x:(r4)+
rz_zst:
        move    r7,r4
        move    #>$60,n4
        move    (r4)+n4
        clr     a
        do      #$20,rz_zbuf            ; $60..$7f, both buffers
        move    a,x:(r4)+
rz_zbuf:
        rts

proc:
; ---- the P table's base, parked ------------------------------------------
; ⚠️ ONE $fab1e0 LITERAL IS ALL THE BUILD ALLOWS (build_bus.py refuses a
; second), so the base is loaded once and kept in a slot; every lookup below
; reads it back.
        move    #>$fab1e0,r5
        move    r5,x0
        move    x0,x:(r7+$4a)
        move    #>$ffffff,m2
        move    #>$ffffff,m3
        move    #>$ffffff,m5
; ---- PITCH: the fundamental's index --------------------------------------
        move    x:(r6+$0),a
        move    a1,x0
        move    x0,x:(r7+$46)
; ---- STRUC: knob/128, the blend between harmonic and bar spacing ---------
        move    x:(r6+$1),a
        asl     #$10,a,a
        move    a1,x0
        move    x0,x:(r7+$45)
; ---- DECAY: the Q index, and TILT: the per-partial step ------------------
        move    x:(r6+$2),a
        move    a1,x0
        move    x0,x:(r7+$47)
        move    x0,x:(r7+$49)           ; the running index starts there
        move    x:(r6+$4),a
        sub     #>$40,a
        asr     #$4,a,a                 ; (knob - 64)/16: +-4 steps per partial
        move    a1,x0
        move    x0,x:(r7+$48)
; ---- BRITE: the exciter's one-pole corner, from the frequency curve ------
        move    x:(r6+$3),a
        move    #$0,x0
        tst     a
        tmi     x0,a
        tfr     a,b
        move    #>$7f,a
        move    #>$7f,x0
        sub     b,a
        tmi     x0,b
        tfr     b,a
        asr     #$1,a,a
        move    a1,n5
        move    x:(r7+$4a),r5
        move    (r5)+n5
        move    p:(r5),x0
        move    x0,x:(r7+$41)
; ---- MIX: wet and dry ----------------------------------------------------
        move    x:(r6+$5),a
        asl     #$10,a,a
        move    a1,x0
        move    x0,x:(r7+$42)
        move    #>$7fffff,a
        move    x0,y0
        sub     y0,a
        move    a,x0
        move    x0,x:(r7+$43)
; ---- the eight partials' coefficients ------------------------------------
; Where each partial sits is an index OFFSET, because the frequency curve is
; exponential: the harmonic series at STRUC 0, a free bar's modes at 127, and
; the blend is (struc/128 * RSD/128) >> 16, which is (struc * RSD)/128 exactly.
; The per-partial pair (RSH, RSD/128) is read from the P table with p:(r2)+.
        move    x:(r7+$4a),r2
        move    #>$80,n2
        move    (r2)+n2                 ; past the two 64-word curves
        move    r7,r4
        move    #>$20,n4
        move    (r4)+n4                 ; resonator 0's block
        do      #$8,rz_pend
        move    p:(r2)+,b               ; RSH_k
        move    p:(r2)+,y0              ; RSD_k/128
        move    x:(r7+$45),x0
        mpy     y0,x0,a
        asr     #$10,a,a
        move    a1,x0
        move    x0,a                    ; the integer part, remainder dropped
        add     b,a
        move    x:(r7+$46),x0
        move    x0,b
        add     b,a                     ; + the fundamental's index
        move    #$0,x0
        tst     a
        tmi     x0,a
        tfr     a,b
        move    #>$7f,a
        move    #>$7f,x0
        sub     b,a
        tmi     x0,b
        tfr     b,a
        asr     #$1,a,a
        move    a1,n5
        move    x:(r7+$4a),r5
        move    (r5)+n5
        move    p:(r5),x0               ; f/2
        move    x0,x:(r4+$2)
; the Q index: the running value, clamped, then 64 words further into the
; table where the damping curve starts
        move    x:(r7+$49),a
        move    #$0,x0
        tst     a
        tmi     x0,a
        tfr     a,b
        move    #>$7f,a
        move    #>$7f,x0
        sub     b,a
        tmi     x0,b
        tfr     b,a
        asr     #$1,a,a
        move    a1,x0
        move    x0,a
        add     #>$40,a
        move    a1,n5
        move    x:(r7+$4a),r5
        move    (r5)+n5
        move    p:(r5),x0               ; damp/2
        move    x0,x:(r4+$3)
        move    x:(r7+$49),a
        move    x:(r7+$48),x0
        move    x0,b
        add     b,a
        move    a1,x0
        move    x0,x:(r7+$49)           ; the next partial's Q index
        move    #>$4,n4
        move    (r4)+n4
rz_pend:
; ---- the exciter: (L+R)/2 through the one-pole, into the buffer ----------
        move    r0,r3
        move    #$1,n3
        move    r7,r4
        move    #>$60,n4
        move    (r4)+n4
        move    #>$f,m4                 ; the buffer wraps on its own
        do      n7,rz_exend
        move    x:(r3)+n3,x0            ; L
        move    x:(r3)+n3,x1            ; R
        move    x0,a
        move    x1,b
        add     b,a
        asr     a                       ; (L+R)/2
        move    x:(r7+$40),x0
        move    x0,b
        sub     b,a                     ; in - s
        move    a,x0
        move    x:(r7+$41),y0
        mpy     y0,x0,a                 ; c*(in - s)
        move    x:(r7+$40),b
        add     a,b
        move    b,x:(r7+$40)
        move    b,x:(r4)+
rz_exend:
; ---- clear the accumulator ----------------------------------------------
        move    r7,r5
        move    #>$70,n5
        move    (r5)+n5
        move    #>$f,m5
        clr     a
        do      n7,rz_acend
        move    a,x:(r5)+
rz_acend:
; ---- the bank: eight resonators, sixteen frames each --------------------
; ⚠️ A NESTED HARDWARE LOOP, which the stock payload uses at 28 sites (checked
; against out/dsp/payload_A.asm, not assumed). Resonators outside, frames
; inside, so each partial's state and both its coefficients live in REGISTERS
; across all sixteen samples -- four loads and two stores per partial per
; block instead of per sample.
        move    r7,r2
        move    #>$20,n2
        move    (r2)+n2
        do      #$8,rz_bkend
        move    x:(r2)+,x0              ; band
        move    x:(r2)+,x1              ; low
        move    x:(r2)+,y0              ; f/2
        move    x:(r2)+,y1              ; damp/2
        do      n7,rz_rsend
; high = in - damp*band - low ; band += f*high ; low += f*band
; f and damp are stored HALVED, as the family's curves are, and each product
; is doubled with `asl` -- never the accumulated state (AGENTS.md).
        mpy     x0,y1,a         x:(r4)+,b       ; (damp/2)*band ; the exciter
        asl     a
        sub     a,b                             ; in - damp*band
        tfr     x1,a                            ; low
        sub     a,b                             ; b = high
        tfr     x0,a                            ; keep band
        move    b,x0                            ; x0 = high
        mpy     y0,x0,b
        asl     b                               ; f*high
        add     b,a                             ; band + f*high
        move    a,x0                            ; the new band
        mpy     y0,x0,b
        asl     b                               ; f*band
        tfr     x1,a
        add     b,a
        move    a,x1                            ; the new low
        move    x:(r5),b
        tfr     x0,a
        add     b,a
        move    a,x:(r5)+                       ; the bank's running sum
rz_rsend:
        move    #>$fffffe,n2
        move    (r2)+n2                 ; back two words, to band
        move    x0,x:(r2)+
        move    x1,x:(r2)+
        move    #>$2,n2
        move    (r2)+n2                 ; past f and damp, to the next partial
rz_bkend:
; ---- MIX the bank's sum back into the frames ----------------------------
; The wet is boosted two bits before the mix: an SVF's IMPULSE gain is f, which
; is 0.08 at 563 Hz, so a transient rings the bank at a fraction of the input
; even though a sustained tone would ring it up by Q. x4 puts a percussive
; input in range without touching the sustained case, which the store's own
; limiter handles.
        move    r0,r3
        move    #$1,n3
        do      n7,rz_mxend
        move    x:(r5)+,x0
        move    x:(r7+$42),y0           ; wet
        mpy     y0,x0,a
        asl     a
        asl     a
        move    a,y1                    ; y1 = the wet sample, limited
        move    x:(r3),x0               ; L
        move    x:(r7+$43),y0           ; dry
        mpy     y0,x0,a
        move    y1,b
        add     b,a
        move    a,x:(r3)+n3
        move    x:(r3),x0               ; R
        move    x:(r7+$43),y0
        mpy     y0,x0,a
        move    y1,b
        add     b,a
        move    a,x:(r3)+n3
rz_mxend:
        move    #>$ffffff,m4
        move    #>$ffffff,m5
        rts
