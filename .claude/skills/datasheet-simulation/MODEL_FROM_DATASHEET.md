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

## 3. Then read the curves

Curves carry the shape the table cannot. Find them, render them, and **look at
them** - this is one of the places where reading an image is the tool for the
job.

```python
import fitz
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
