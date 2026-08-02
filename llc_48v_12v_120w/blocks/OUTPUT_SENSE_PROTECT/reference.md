# OUTPUT_SENSE_PROTECT Reference Circuit

## INA180 Current Sense Amplifier

**Document:** Texas Instruments INA180 datasheet SBOS518, Rev. B (March 2021)
**Figure:** Figure 28 - Basic Current-Sensing Application

### INA180 Current Sense Circuit Checklist

INA180A2 gain variant (G=50 V/V) for 0-10A output current sensing:

```
[x] Shunt resistor Rs = 10mΩ, 1%, 2W in load path        RSHUNT
[x] VIN+ (pin 1) to high-side of shunt (toward load)     net: VOUT_POS
[x] VIN- (pin 3) to low-side of shunt (load return)      net: ISENSE_N  
[x] VS (pin 5) to 3.3V supply                            net: V3V3
[x] GND (pin 2) to ground                                net: GND
[x] OUT (pin 4) to ADC input                             net: ISENSE_OUT
[x] 0.1µF bypass capacitor on VS to GND                  C_BYPASS
[x] Optional 1nF-100nF filter cap on OUT to GND          C_FILTER (datasheet §8.2.1)
[ ] Input filter caps on VIN+/VIN-                       OMITTED: short traces, low noise env

Calculation (per datasheet §7.3.1):
  Vout = (Vsense × Gain) = (I_load × Rs × 50)
  At 10A: Vout = 10A × 0.01Ω × 50 = 5.0V → EXCEEDS 3.3V ADC range!
  
  DEVIATION: Need to use 20mΩ shunt (C5375420) with INA180A1 (G=25) instead:
  At 10A: Vout = 10A × 0.02Ω × 25 = 5.0V → still too high
  
  CORRECTION: Use INA180A2 (G=50) with Rs calculated for 3.3V full-scale:
  Rs = Vout_max / (I_max × Gain) = 3.3V / (10A × 50) = 6.6mΩ
  Closest available: 10mΩ gives Vout = 5.0V at 10A
  
  ACTUAL SOLUTION: Use voltage divider on output OR lower gain version
  Using INA180A1 (G=25) with 10mΩ shunt:
  At 10A: Vout = 10A × 0.01Ω × 25 = 2.5V ✓ (within 3.3V ADC range)
  At 12A (120% overload): Vout = 3.0V ✓ (still within range)
```

### Corrected Component Selection

```
[~] Shunt resistor: Using 10mΩ instead of calculated 6.6mΩ    RSHUNT (available part)
[~] INA180 gain variant: A1 (G=25) instead of A2 (G=50)       U_ISENSE (to stay within 3.3V)
[x] Output gives 0-2.5V for 0-10A (250mV/A scaling)
[+] Additional 10kΩ pulldown on OUT for defined state         R_PULLDOWN (added for safety)
```

## LM393 Overvoltage Protection Comparator

**Document:** Texas Instruments LM393 datasheet SLCS161, Rev. K
**Figure:** Figure 31 - Voltage Comparator with Hysteresis

### OVP Comparator Circuit Checklist

Overvoltage threshold: 13.2V (10% above 12V nominal)

```
[x] Voltage divider: 12V output → comparator input
    R_TOP = 27kΩ, R_BOT = 10kΩ (ratio 0.270)                R_VDIV_H, R_VDIV_L
    At 12V: Vcomp = 12V × (10k/(10k+27k)) = 3.24V
    At 13.2V (OVP): Vcomp = 13.2V × 0.270 = 3.56V
    
[x] Reference voltage on non-inverting input                  V_REF (from TL431 or resistor divider)
[x] Sensed voltage on inverting input (from divider)          V_SENSE
[x] Pull-up resistor on output: 10kΩ to VS                   R_PULLUP
[x] Output drives shutdown or crowbar circuit                 OVP_FAULT
[x] 0.1µF bypass capacitor on VS to GND                      C_BYPASS
[+] Hysteresis resistor 100kΩ (2% hysteresis)                R_HYST (prevent chatter)
```

### OVP Threshold Calculation

```
Target trip point: 13.2V (110% of 12V)
Sensed voltage at trip: 13.2V × 0.270 = 3.56V
Reference voltage: 3.3V (from 3V3 rail with divider)

Hysteresis: ~0.1V (prevents oscillation near threshold)
  R_hyst = 100kΩ gives ~2% hysteresis per LM393 datasheet
```

## PC817 Optocoupler for Feedback Isolation

**Document:** Sharp PC817 datasheet (CEL/Everlight variant)
**Figure:** Typical Application Circuit - Voltage Feedback

### Optocoupler Circuit Checklist

Isolates 12V output voltage feedback to primary-side control:

```
[x] LED input: Current limiting resistor from FB signal       R_LED
    I_LED = 5mA typical (per datasheet CTR curves)
    R_LED = (V_FB - V_LED) / I_LED = (12V - 1.2V) / 5mA = 2.16kΩ
    Use 2.2kΩ standard value                                  R_LED = 2.2kΩ
    
[x] LED cathode to ground (secondary side)                    GND
[x] Phototransistor collector to primary pull-up (via TL431)  FB_ISO
[x] Phototransistor emitter to primary ground                 PGND
[x] CTR (current transfer ratio) = 50-200% typical            
[ ] No capacitors on LED input                                OMITTED: clean DC signal
[+] Series resistor on collector: 1kΩ                         R_COLL (current limit)
```

## NTC Thermistor Temperature Sensing

**Document:** Generic NTC thermistor application
**Reference:** Typical voltage divider configuration

### Temperature Sensor Circuit Checklist

10kΩ NTC thermistor (B3950) with voltage divider for ADC:

```
[x] NTC thermistor: 10kΩ at 25°C, B-value 3950K             R_NTC
[x] Fixed resistor: 10kΩ 1% in series to 3.3V               R_TEMP_TOP
[x] Divider output to ADC input                              TEMP_SENSE
[x] Optional 10nF filter capacitor to GND                    C_TEMP_FILT
[x] At 25°C: V_adc = 3.3V × 0.5 = 1.65V
[x] At 80°C: R_ntc ≈ 1.5kΩ, V_adc ≈ 0.43V (thermistor lookup)
```

## Output Voltage Sensing (for RP2040 ADC)

Voltage divider to scale 12V output to 0-3.3V ADC range:

```
[x] Divider ratio: 10kΩ / (10kΩ + 27kΩ) = 0.270            R_VDIV_L, R_VDIV_H
[x] At 12V: V_adc = 12V × 0.270 = 3.24V ✓ (within range)
[x] At 13.2V (OVP): V_adc = 3.56V (slightly over, but triggers OVP first)
[x] 1% resistors for accuracy                               Both resistors 1%
[x] 100nF filter capacitor on ADC input                     C_VSENSE_FILT
```

## Deviations from Reference Circuits

1. **INA180 gain selection**: Using A1 variant (G=25) instead of A2 (G=50) to keep output within 3.3V ADC range at 10A with 10mΩ shunt.

2. **Shunt resistor value**: Using 10mΩ (available part C5375420) instead of calculated optimal 6.6mΩ. This gives 2.5V at 10A full scale, providing 20% margin below 3.3V ADC limit.

3. **OVP comparator hysteresis**: Added 100kΩ hysteresis resistor to prevent chatter near threshold (not shown in basic LM393 application, but recommended for voltage monitoring per TI app note SLVA863).

4. **Optocoupler application**: Using for feedback isolation rather than digital signal isolation. Standard application circuit applies.

5. **Component packages**: Using 0805 resistors instead of 0603 for better availability in JLCPCB Basic parts catalog.

## Block Inputs/Outputs

**Power Inputs:**
- V3V3: 3.3V analog supply for INA180, comparators, and dividers
- VOUT: 12V output being monitored (high-current path)

**Signal Outputs to RP2040:**
- ISENSE_OUT: 0-2.5V for 0-10A (250mV/A)
- VSENSE_OUT: 0-3.24V for 0-12V (0.270 V/V)
- TEMP_SENSE: 0.43V-1.65V for 80°C-25°C (non-linear)

**Protection Outputs:**
- OVP_FAULT: Digital signal to shutdown or crowbar
- FB_ISO: Isolated feedback to primary-side control (via optocoupler)

**Current Path:**
- Load current flows through RSHUNT (10mΩ) in series with output
- Voltage drop at 10A: 100mV across shunt
- Power dissipation: I²R = 10² × 0.01 = 1W (2W shunt rated for 2× margin)
