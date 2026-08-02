# Turning a datasheet into a model you can trust

A behavioural model is a claim about a real part. Writing one is easy; writing
one that is right, and knowing which it is, needs a procedure. This is that
procedure, and it is what `circuit_synth/simulation/parts/tps7a49.py` follows.

The whole thing rests on one idea: **build from one set of published numbers,
check against a different set.** A model built from a curve will reproduce that
curve, and that proves the arithmetic works and nothing else.

## 1. Get the document, not a summary

The vendor's PDF, with its document number and revision. Note them - datasheets
disagree with themselves across revisions often enough that "the AMS1117
datasheet" is not a citation.

```bash
curl -sL -o part.pdf https://www.ti.com/lit/ds/symlink/tps7a49.pdf
```

## 2. Take the table first

The specification table is measured silicon at stated conditions, and it is
text, so it can be read exactly. Pull every parameter with its conditions:

```python
timeout 300 python -c "
import fitz
d = fitz.open('part.pdf')
print(d[5].get_text())"
```

Record the conditions with the value. A dropout voltage without its load
current is not a number, and a PSRR without its frequency and its capacitors is
not either.

## 3. Then read the curves - and try the vectors before your eyes

Curves carry the shape the table cannot. Before rendering anything, check
whether the figure is vector art, because most datasheet plots are, and then
the curve is *in the file* as coordinates rather than as an image of
coordinates.

```python
import fitz
page = fitz.open('part.pdf')[2]
for i, d in enumerate(page.get_drawings()):
    print(i, d['rect'], len(d['items']), d.get('width'))
```

The plot is a cluster of drawings sharing one rectangle: a frame, some
gridlines, and one path with far more segments than the rest. That path is the
data. Map it through the axes and you have the curve to the precision it was
plotted at:

```python
X0, X1, Y0, Y1 = 351.1, 520.6, 423.8, 593.3      # the frame, from its rect
T = lambda x: -60 + (x - X0) / (X1 - X0) * 240   # axis min .. max
R = lambda y: 2.5 * (Y1 - y) / (Y1 - Y0)
```

**Check the calibration against the gridlines**, which are drawings too. If
they come back at -40.0, -20.0, 0.0, 20.0 and not at -39.6, -19.1, 1.2, the
mapping is right and every point you extract is right with it.

This is worth the extra step. The IRF3205's normalised resistance curve read
off a 300 dpi render put the 100C point at 1.38; the vector path says 1.505.
An 8% error, invisible, and it would have gone into every prediction built on
it. Log axes are worse, because a small pixel error near a decade boundary is
a large error in the value.

Two things the vectors will not give you. Markers are separate glyphs, so the
curve's own endpoints can sit a few tenths off the round number they were drawn
for - the IRF3205's 175C point maps to 174.85C, and the one at 25C, where
normalisation makes the value exactly 1, maps to 25.02C. That slop is the
plotting software, not the data, and it is fair to snap to the intended value
and say you did. And a figure that is a scanned bitmap has no vectors at all.

For those, render and read:

```python
fitz.open('part.pdf')[8].get_pixmap(dpi=200).save('fig.png')
```

Then Read the PNG and write down points. Two rules:

- **Record the reading accuracy.** A log-frequency plot read by eye at 200 dpi
  is worth about ±2 dB; a linear plot about ±2% of full scale. Carry that
  number, because everything downstream inherits it and pretending to more
  precision than you have is how a model comes to look authoritative.
- **Do not smooth the features out.** The dip and peak in a PSRR curve near the
  loop's crossover are the interesting part - they are where a switching supply
  puts its ripple. A tidy monotonic curve is a nicer graph and a worse model.

## 4. Split the data before you fit

This is the step that makes the difference, and it has to be done before
fitting rather than after.

Pick which published numbers will **build** the model and which will **judge**
it, and choose so the two are genuinely independent measurements:

| Build from | Judge with | Why they are independent |
|---|---|---|
| Figure 9, dropout at 15-135 mA | Table's dropout at 100 and 150 mA | table and figure are separate characterisations |
| the PSRR curve | the table's PSRR at 120 Hz | same |
| the reference noise density | the table's integrated output noise | different mechanism entirely |

Mark every point `in_sample=True` or `False` in its `ReferencePoint`. A report
made only of in-sample points says so instead of looking like a pass.

## 5. Choose a form that matches the physics

Fit the smallest form that the physics justifies, and when it fails, **name the
mechanism** rather than adding parameters until the residual goes away.

The worked example makes the point. Dropout looks like a resistance, so the
obvious model is `V = I·R`:

```
100 mA -> 260.0 mV, off by  0.0%     (it was anchored here)
150 mA -> 390.0 mV, off by 17.1%
```

Anchored to one point it is exact there, and 17% out at the other end - an
error big enough to matter and small enough to look like measurement scatter. A
pass element in dropout is not a resistor: it has an offset that appears within
the first few milliamps and a resistive slope after it.

```python
def predict_dropout(current):
    knee = DROPOUT_KNEE * (1.0 - math.exp(-current / DROPOUT_KNEE_CURRENT))
    return knee + DROPOUT_RESISTANCE * current
```

Fitted to the *curve*, judged against the *table*:

```
100 mA -> 258.8 mV, off by  0.5%
150 mA -> 338.5 mV, off by  1.6%
```

Both points out of sample. The improvement came from naming the mechanism, not
from a better optimiser.

## 6. Predict something you were not told

The strongest test available. Build the model from one set of behaviours, then
ask it for a behaviour that nothing in that set implies.

For the LDO: the model is built from the rejection curve and the regulation
specs, then asked for the integrated output noise, which comes from the
reference's noise density and the NR/SS corner - a different mechanism
altogether. It predicts 19.96 µV against a published 21.15 µV, 5.6% out.

If a model can only reproduce what it was given, it is a lookup table.

## 6a. When the model and the datasheet disagree, check the datasheet

A disagreement is not automatically the model's fault, and assuming it is leads
somewhere bad: you tune until the number matches, and every other prediction
gets worse to pay for it.

Before touching the model, check the published value against the rest of the
document. The TL072H worked example is the case in point. Its model is built
from gain-bandwidth, slew rate, phase margin and open-loop gain, with **no
fitted parameters**, and predicts four published settling times:

```
  10V to 0.01%   0.817us vs 0.91us published    10.2%
  10V to  0.1%   0.697us vs 0.63us published    10.6%
   2V to 0.01%   0.519us vs 0.48us published     8.1%
   2V to  0.1%   0.392us vs 0.56us published    30.0%   <- the outlier
```

Three within 11%, one at 30%. The tempting move is to adjust something until
the fourth comes into line. Look at the table first:

| step | tolerance | published |
|---|---|---|
| 2 V | 0.1% | 0.56 µs |
| 2 V | **0.01%** | **0.48 µs** |

The output has to cross the 0.1% band on its way into the 0.01% band, so it
cannot reach the tighter one sooner. **One of those two numbers is wrong**, no
model can match both, and the model's largest error falls on exactly that pair.

So: record the contradiction, widen the tolerance on that point and say why in
the same breath, and leave the model alone. Fitting to an impossibility buys a
matching number and costs accuracy everywhere else.

The general rule: when a prediction is out by much more than its neighbours,
work out which mechanism would have to be wrong to explain it. If no mechanism
would, suspect the number.

## 6b. When a parameter is not published, fit exactly one — and prove it

Sometimes the datasheet does not contain what the physics needs. A discrete
switching design gives gate charge and switching times; an integrated converter
has the FETs inside and publishes neither, so the switching loss cannot be
derived at all.

That is not a reason to abandon the model, and it is not permission to fit
freely. The rule:

**Fit one coefficient, tie it to a named mechanism, then validate it against a
condition it was not fitted to — one that mechanism must respond to.**

The TPS62130 example. Efficiency is conduction (grows as I²), switching
(roughly constant), and quiescent. Conduction comes from the published
on-resistances; quiescent from the published Iq; the switching term is fitted
at 2.5 MHz. So far that could be a curve fit dressed up as physics.

The test: predict the **1.25 MHz** curve. Same silicon, half the switching
frequency. If the coefficient stands for energy lost per cycle it must halve
and the whole curve must move with it; if it stands for the shape of one graph
it will not.

```
IN SAMPLE     2.5 MHz      within 0.9 points across 0.5-3A
OUT OF SAMPLE 1.25 MHz     within 1.8 points across 0.5-3A
```

The curve reads to about ±1.5 points, so the out-of-sample error is at the
accuracy of the source. The mechanism is right.

Pick the validating condition so that a *wrong* model fails it. Predicting the
same frequency at a different current would not have worked — conduction
already explains that, and the switching term barely moves. Frequency is the
axis the fitted term owns.

If there is no such condition available, say the coefficient is unvalidated.
One fitted parameter with an out-of-sample check is a model; one fitted
parameter without one is a curve fit, and the difference matters when somebody
uses it at a condition you never tried.

## 6c. When the answer depends on itself, solve for it

Some parts have no operating point you can evaluate. A power MOSFET's
on-resistance rises with junction temperature, the dissipation is I²R, and the
junction temperature is set by that dissipation - so the answer is an input to
its own calculation.

Do not break the loop by evaluating it once at 25C. That is not a small error
and it is not conservative in a knowable direction: the IRF3205 at 175C has
2.2 times its 25C resistance, so a part sized on the specification table is
undersized by that factor exactly when it matters.

Find the value that reproduces itself:

```python
def settles_at(temperature):
    return reference + duty * current**2 * on_resistance(temperature) * rth

# f(T) = settles_at(T) - T starts positive. A root is an operating point.
```

Bisection is enough, and it is better than iterating the loop directly,
because a diverging iteration and a slowly converging one look the same for the
first several passes.

**The interesting case is when there is no root.** Above some current the
device heats faster than the path carries heat away, at every temperature the
datasheet describes. That is thermal runaway. It is a result:

```python
if settles_at(curve_max) - curve_max > 0:
    return ThermalSolution(converged=False, note="no stable junction temperature ...")
```

Neither raising nor returning a number is right. Raising says the model failed;
it did not, it answered. Returning the last iterate says the part runs at that
temperature; it does not. Return the finding.

Say what you cannot distinguish, too. Once the curve runs out you cannot tell
runaway from a stable point above the rated maximum - and you do not need to,
because both mean the design is wrong. Write that down rather than picking one.

The same shape turns up wherever a loss depends on the state it produces:
regulator efficiency against die temperature, a battery's internal resistance
against its own heating, an LED's forward voltage against junction temperature
on a fixed-current driver. Once one part in a design has it, everything sharing
its heatsink has it too.

## 6d. Check the arithmetic against a simulator, not against the datasheet

There are two questions about a model and only one of them the datasheet can
answer:

| Question | What answers it |
|---|---|
| Is this the right part? | the datasheet, via `check()` |
| Is the maths right? | a simulator, via `crosscheck` |

They fail identically. A model built from exactly the right numbers that
integrates them badly looks precisely like a part that misses its own
specification, and if you only ever compare against the datasheet you cannot
tell which you have - so you tune the physics to fix a numerical error.

Wherever a model's behaviour reduces to a network SPICE represents exactly,
that network is the reference:

```python
from circuit_synth.simulation.crosscheck import cross_check_settling
print(cross_check_settling(tl072.model(), step=0.1, tolerance=1e-3).summary())
# [agrees] settling to 0.1% after a 0.1V step: model 3.811e-07 s,
#          ngspice transient on the equivalent RLC 3.827e-07 s, apart by 0.43%
```

The op-amp's settling time is a hand-rolled forward-Euler integration of a
lightly damped second-order system - exactly where numerical damping creeps in
without anyone noticing. Below the slew limit that system *is* a series RLC, so
ngspice integrates the same problem with an implicit method and adaptive steps.
0.43% apart. That is what makes the TL072's disagreement with its own datasheet
readable as a statement about the part rather than about the integrator.

**Stay inside what the reference represents.** The RLC is the model's linear
behaviour, so a step big enough to slew compares two different problems and the
difference means nothing. `cross_check_settling` raises rather than returning
that number, because a meaningless number that looks like a result is worse
than no result.

### Use a second model to bound an approximation, not to replace one

Every model simplifies something, and a gap that says "this is ignored" leaves
the reader to guess whether it matters. A second, independent model built from
the same datasheet by a different route can turn that into a number.

The IRF3205's Python model takes on-resistance as independent of drain current,
which is false. `vdmos.fit()` builds an ngspice card from the specification
table - threshold, transconductance, and a drain resistance solved for at the
datasheet's own test point - and that model *does* represent the dependence:

```
  ID      vdmos Rds(on)   vs the 62A fit point
    5A       7.884 mohm        -1.4%
   20A       7.914 mohm        -1.1%
   80A       8.039 mohm        +0.5%
```

Under 1.5% across the whole range, which is less than the curve can be read to.
So the gap now says that, with the bound, instead of leaving a worry.

Note what makes this fair: the two routes share only the datasheet. One comes
from the normalised resistance curve, the other from the table plus a fit, and
they are compared at currents neither was anchored to. Two models sharing a
derivation would agree for no reason at all.

### ngspice is probably available even when it looks absent

`shutil.which("ngspice")` finds nothing on a normal KiCad install, because
KiCad ships the simulator as a library and no program. Taking that as "nothing
to check" is how this repository spent several sessions believing SPICE could
not run here.

`simulation.ngspice_runner` finds the library and an interpreter that can load
it. The wrinkle worth knowing, because the wrong diagnosis was convincing: on
Windows on ARM the venv's `python.exe` has an ARM64 PE header and
`platform.machine()` says ARM64, yet the entry is a trampoline that launches an
x86-64 CPython - and inside that emulated process an ARM64 DLL fails to load
with `WinError 193`, the same error a genuine architecture mismatch gives. The
honest signal is `PROCESSOR_ARCHITECTURE`, which reports what the process
actually is. KiCad bundles an interpreter matching its own DLL, so the runner
drives ngspice through that in a subprocess and the caller keeps whatever
Python it has.

## 7. Write down what it does not represent

Every model carries a `gaps` list, and it is not an apology. A gate driver
model that says "no figure for output impedance, so edge shape is not
modelled" tells a reader which of its numbers to trust. One that assumes 2 ohms
because that is typical produces a number that looks exactly as trustworthy as
a real one, which is worse than having no number.

Where a datasheet genuinely does not support a question, say so and stop. A
part specified at one temperature contains no temperature coefficient. A part
with typical-only switching times cannot bound a worst case.

## 8. Keep the check runnable

```python
def check() -> ValidationReport:
    """Run the model against every published value."""
    return validate("TPS7A49", predictions, reference_points())
```

A model with a `check()` that runs in a test is a model that says when it has
drifted. One without is a claim nobody will look at again.

```
TPS7A49 against its datasheet:
  [pass] output noise 10Hz-100kHz: model 1.996e-05 V, datasheet 2.115e-05 V, off by 5.6%
  [pass] dropout at 150 mA: model 0.3384 V, datasheet 0.333 V, off by 1.6%
  [pass] PSRR at 120 Hz: model 71 dB, datasheet 72 dB, off by 1.4%
  [pass] dropout at 100 mA: model 0.2588 V, datasheet 0.26 V, off by 0.5%
  -> matches; 4 of 6 point(s) were out of sample
```

## 9. Register it, or nobody will find it

A model that lives in a file nobody looks up gets rebuilt by the next agent to
meet the part, by hand, without the checking. Two models of one part give two
answers for one design, and nothing in the flow compares them.

Add an entry to `REGISTRY` in `circuit_synth/simulation/parts/__init__.py`:

```python
"TPS7A49": PartModel(
    prefix="TPS7A49",              # what an order code is matched against
    validated_part="TPS7A4901",    # the exact device check() was run on
    document="SBVS121E",
    summary="low-noise LDO: rejection against frequency, dropout against load",
    module=tps7a49,
    check=tps7a49.check,
    gaps=tps7a49.gaps,
    fitted=False,                  # true if any coefficient was fitted
),
```

Two things to get right, and they pull against each other:

- **The prefix decides who finds it.** Order codes carry package and reel
  suffixes the model knows nothing about, so match on the family. Set it one
  digit short of the validated part when the neighbouring devices are the same
  silicon - a TPS62133 should find the TPS62130 model rather than nothing.
- **`validated_part` decides who is warned.** Anything matching the prefix but
  not this string comes back with `exact=False` and a caveat naming the
  document to go and read. That is what keeps a family match from quietly
  becoming a citation.

`check_all()` then runs every registered model in the test suite, so a model
that stops matching its datasheet fails a test rather than going on being
believed.

## Choosing tolerances

A tolerance is a claim too, so pick it from what the number is:

| Source | Reasonable tolerance |
|---|---|
| a value in the specification table | 5% |
| a value read off a linear plot | 10% |
| a value read off a log plot | 5% of the decibel figure, not the ratio |
| a prediction from a different mechanism | 25% |
| a limit rather than a typical | not a tolerance - only stay inside it |

A model checked against typical values is checked against a typical part, which
is not the same as being checked against the part you will be sent. Say which
you did.
