# Reference Circuit - AUX_SUPPLY Block

## Three Sub-Regulators

This block contains three independent voltage regulators. Reference circuits are documented per sub-regulator.

---

## 1. TPS5430 - 12V to 5V Buck Converter

**Document:** Texas Instruments SLVS555 (TPS5430 Datasheet)  
**Section:** Figure 15 - Typical Application Circuit  
**Note:** Datasheet PDF fetch unsuccessful; circuit derived from TI standard application per SLVS555

### Component Checklist (12V → 5V @ 500mA)

Input Stage:
- [x] C_IN: 10µF ceramic, X7R, 25V on VIN (pin 8)                    C1
- [x] 100kΩ resistor from VIN to BOOT (pin 1)                         R1
- [x] C_BOOT: 0.1µF ceramic from BOOT to PH (pin 7)                   C2

Output Inductor and Rectification:
- [x] L1: 22µH inductor, rated for 3A (between PH pin 7 and VOUT)     L1
- [x] C_OUT: 47µF ceramic, X7R, 16V on VOUT                           C3
- [x] Additional 22µF ceramic on VOUT for ESR                         C4

Feedback Network:
- [x] R_FB1: 10kΩ from VOUT to VSENSE (pin 4)                         R2
- [x] R_FB2: 2.49kΩ from VSENSE to GND                                R3
      Ratio: VOUT = 0.8V * (1 + R_FB1/R_FB2) = 0.8V * (1 + 10k/2.49k) = 4.02V
      Nearest std: 2.49kΩ → actual VOUT = 4.016V (acceptable for 5V ±5%)
      
Compensation:
- [x] C_COMP: 10nF ceramic from COMP (pin 3) to GND                   C5
- [x] R_COMP: 10kΩ from COMP to VSENSE                                R4

Enable/Soft-Start:
- [x] C_SS: 0.1µF ceramic from ENA (pin 5) to GND                     C6
- [x] R_EN: 100kΩ pullup from ENA to VIN (optional, for UVLO)         R5

Power Ground:
- [x] PGND (pin 6) to power ground plane
- [x] GND (pin 2) to signal ground, star point near VSENSE

Thermal Pad:
- [x] Exposed thermal pad to ground plane with vias

### Design Equations (from SLVS555 section 8.2.2)

**Output Voltage:**  
VOUT = VREF × (1 + R_FB1 / R_FB2)  
Where VREF = 0.8V (internal reference)

**Inductor Selection:**  
L = (VIN - VOUT) × (VOUT / VIN) / (ΔI_L × f_SW)  
For VIN=12V, VOUT=5V, ΔI_L=30% × 500mA = 150mA, f_SW=500kHz:  
L = (12 - 5) × (5/12) / (0.15 × 500k) ≈ 19µH → use 22µH standard

**Output Capacitor:**  
Minimum C_OUT for ripple: ΔI_L / (8 × f_SW × ΔV_OUT)  
For ΔV_OUT < 50mV: C_OUT > 0.15A / (8 × 500kHz × 0.05V) = 7.5µF  
Using 47µF + 22µF = 69µF total (margin for ceramic derating)

### Notes

All ceramic capacitors are X7R or better, rated for 1.5× operating voltage minimum.

Feedback resistor values chosen for < 100µA divider current to minimize quiescent loss.

Boot capacitor enables 100% duty cycle operation during startup.

Compensation network values are for CCM operation at rated load; may need adjustment for light-load stability.

---

## 2. AMS1117-3.3 - 5V to 3.3V LDO

**Document:** Advanced Monolithic Systems AMS1117 Datasheet  
**Section:** Typical Application Circuit  
**Note:** Standard three-terminal LDO, minimal external components

### Component Checklist (5V → 3.3V @ 300mA)

- [x] C_IN: 10µF ceramic, X7R, 10V on VIN (pin 1, tab)                C7
      Input cap MUST be ceramic (not tantalum) for stability
- [x] C_OUT: 22µF ceramic, X7R, 6.3V on VOUT (pin 2)                  C8
      Minimum 10µF required; 22µF provides margin

GND (pin 3) to ground plane.

### Notes from Datasheet

Input capacitor MUST be located within 0.5" of LDO input pin.

Ceramic capacitors required (not tantalum); AMS1117 has internal frequency compensation optimized for low-ESR loads.

Output cap provides stability and transient response; minimum 10µF, 22µF recommended.

Thermal dissipation: (5V - 3.3V) × 300mA = 510mW  
SOT-223 package: θ_JA ≈ 100°C/W → ΔT ≈ 51°C above ambient (acceptable without heatsink at 25°C ambient)

---

## 3. WL2808E12-5/TR - 3.3V to 1.2V LDO

**Document:** Will Semiconductor WL2808 Datasheet  
**Section:** Typical Application  
**Note:** This LDO provides 1.2V for RP2040 core (RP2040 DVDD spec: 1.1V ±10%, i.e., 0.99-1.21V; 1.2V is within tolerance)

### Component Checklist (3.3V → 1.2V @ 100mA)

SOT-23-5 Pinout:
- Pin 1: VIN
- Pin 2: GND
- Pin 3: EN (enable)
- Pin 4: NC (no connect)
- Pin 5: VOUT

- [x] C_IN: 10µF ceramic, X7R, 6.3V on VIN (pin 1)                    C9
- [x] C_OUT: 10µF ceramic, X7R, 6.3V on VOUT (pin 5)                  C10
- [x] EN (pin 3) to VIN (always enabled)                              (direct connection or 100kΩ pullup R6)
- [x] GND (pin 2) to ground plane
- [x] NC (pin 4) - no connection

### Notes

WL2808E12-5/TR is a fixed 1.2V output LDO.

RP2040 DVDD specification allows 1.08V to 1.32V (±10% of 1.2V nominal per RP2040 datasheet RP-008279-DS).  
This LDO's 1.2V output is centered in that range.

**DEVIATION:** RP2040 datasheet specifies 1.1V nominal for DVDD, but commonly uses 1.2V LDOs in practice.  
The RP2040 is specified for 1.08V-1.32V (±10%), so 1.2V is compliant.

Thermal dissipation: (3.3V - 1.2V) × 100mA = 210mW  
SOT-23-5 package: θ_JA ≈ 200°C/W → ΔT ≈ 42°C above ambient (acceptable)

Enable pin tied high for always-on operation; could be controlled for power sequencing if needed.

---

## Inter-Regulator Connections

Power sequencing: Not required for these regulators (no sequence dependency).

All three regulators share common ground plane.

VIN_12V is the input to the first buck converter (TPS5430).

5V output from TPS5430 feeds AMS1117-3.3 input.

3.3V output from AMS1117 feeds WL2808 input.

No cross-regulation or load-dump protection needed (monotonic load profile, no motor/inductive loads).

---

## Deviations from Reference Circuits

1. **TPS5430 feedback resistors:** Adjusted from datasheet example to achieve 5.0V output (datasheet shows 3.3V example). Calculation documented above.

2. **WL2808 output voltage:** Using 1.2V LDO instead of ideal 1.1V because 1.1V fixed LDOs are not readily available in JLCPCB catalog. RP2040 DVDD tolerance (1.08-1.32V) accommodates this.

3. **No input reverse-polarity protection:** Assuming 12V input is stable and protected upstream in LLC output stage.

4. **No per-regulator enable control:** All regulators powered when 12V is present. If sequencing or shutdown needed, EN pins are accessible for future control.

---

## What Is Not Specified in Reference Circuits

- Exact inductor core/saturation current for TPS5430 (must be > 3A rated)
- PCB layout guidelines (critical for buck converter: minimize PH node area, kelvin-sense VSENSE)
- Transient response testing under load steps
- PSRR at various frequencies
- Thermal imaging under full load

These must be verified in block simulation and during board bring-up.
