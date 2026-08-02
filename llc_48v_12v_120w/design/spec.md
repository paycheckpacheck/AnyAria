# LLC Converter 48V→12V 120W Specification

## Project Goal
High-efficiency, compact LLC resonant converter demonstration board with integrated telemetry for evaluation and monitoring.

## Electrical Requirements

### Power Specifications
- **Input Voltage:** 48V nominal (assume 36-60V operating range)
- **Output Voltage:** 12V ±2%
- **Output Current:** 10A maximum (120W)
- **Target Efficiency:** 95% at full load
- **Topology:** Discrete LLC resonant converter with GaN FETs

### Rails Required
1. **Primary Input:** 48V from external supply
2. **Primary Output:** 12V @ 10A (main output)
3. **RP2040 System:**
   - 3.3V @ 200mA (I/O supply)
   - 1.1V @ 100mA (core supply)
4. **Gate Drive Supplies:**
   - Primary side: Bootstrap or isolated 12V supply
   - Secondary side: Derived from output

### Interfaces
- **Power Input:** 2-pin screw terminal or high-current connector (48V input)
- **Power Output:** 2-pin screw terminal or high-current connector (12V output)
- **USB:** USB-C for RP2040 telemetry interface
- **Telemetry Signals:**
  - Input voltage sensing (ADC)
  - Output voltage sensing (ADC)
  - Output current sensing (ADC via shunt + amplifier)
  - Temperature sensing (thermistor or integrated sensor)
  - Primary FET temperatures
  - Efficiency calculation capability

## Physical Constraints
- **Size:** Business card form factor ≤ 85mm × 55mm
- **Assembly:** JLCPCB PCBA (all parts must be JLCPCB-sourceable)
- **Layer Count:** Assume 4-layer minimum for power routing and thermal

## Critical Design Numbers

### LLC Resonant Tank
- **Switching Frequency Range:** 100-500kHz (variable for regulation)
- **Resonant Frequency:** ~250kHz (target design point)
- **Quality Factor (Q):** 0.3-0.5 for good regulation range
- **Transformer Turns Ratio:** ~3:1 or 4:1 (48V → 12V with rectification)

### Power Stage
- **Primary GaN FETs:** 
  - Voltage rating: ≥150V (3× input for safety)
  - Current rating: ≥8A (accounting for transformer ratio and RMS)
  - RDS(on): <50mΩ for efficiency
- **Secondary SR FETs:**
  - Voltage rating: ≥40V (3× output)
  - Current rating: ≥15A (>1.5× output for margin)
  - RDS(on): <5mΩ for efficiency

### Thermal
- **Power Dissipation Budget:**
  - Input power at full load: 120W / 0.95 = 126.3W
  - Total losses: 6.3W
  - Breakdown (estimated):
    - Primary FETs: 2W
    - Secondary FETs: 2W
    - Transformer: 1.5W
    - Other: 0.8W

## Key Assumptions
1. **Transformer:** Custom LLC transformer will be required (unlikely to be in JLCPCB catalog). This is a **MAJOR RISK** for full PCBA assembly. May require:
   - External sourcing and hand-assembly, OR
   - Pre-consigned component to JLCPCB, OR
   - Design compromise if suitable catalog transformer found
   
2. **Operating Environment:** Indoor, ambient 25°C, natural convection cooling

3. **Control Strategy:** 
   - LLC controller IC for variable frequency control (not fully discrete logic)
   - RP2040 provides monitoring only, not primary control loop
   
4. **Isolation:** 
   - Transformer provides galvanic isolation
   - Telemetry monitoring is on secondary (output) side only for simplicity
   - If primary-side sensing needed, would require isolated sensors

5. **Protection:**
   - Overcurrent protection (OCP)
   - Overvoltage protection (OVP) on output
   - Over-temperature protection (OTP)
   - Short circuit protection

## Success Criteria
- ✓ Generates stable 12V output from 48V input
- ✓ Delivers 10A continuously
- ✓ Achieves ≥93% efficiency at full load (95% is aggressive target)
- ✓ Fits within 85mm × 55mm footprint
- ✓ RP2040 telemetry provides real-time voltage, current, efficiency, temperature
- ✓ All components sourceable from JLCPCB (except transformer - see assumptions)
- ✓ Passes basic safety: no excessive temperatures, stable operation

## Known Limitations
1. **Transformer availability:** Likely requires custom or external sourcing
2. **Business card size:** Extremely tight for 120W - may need to relax to "compact" vs strict business card
3. **Efficiency target:** 95% is achievable but aggressive for this power level and size
4. **Testing complexity:** LLC converters require careful startup sequencing and frequency control
5. **Layout criticality:** LLC performance very sensitive to layout parasitics

---
*Specification locked: 2026-08-01*
*Do not modify after architecture approval gate*
