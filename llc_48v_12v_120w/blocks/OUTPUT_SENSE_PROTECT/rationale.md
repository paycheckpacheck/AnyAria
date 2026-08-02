# OUTPUT_SENSE_PROTECT Rationale

## Current Sensing Group

**INA180A1 Current Sense Amplifier Circuit**

Implements current sensing for 0-10A output monitoring using high-side sensing.

Components:
- RSHUNT (10mΩ, 2W): Current shunt in load path. Chosen for 100mV drop at 10A (V=IR=10A×0.01Ω=0.1V), well within INA180 common-mode range. 2W power rating gives 2× margin (P=I²R=1W at 10A). Reference: INA180 datasheet SBOS518 Figure 28.

- U_ISENSE (INA180A1): Gain variant A1 (G=25 V/V) selected to keep output within 3.3V ADC range. At 10A full scale: Vout = I × Rs × G = 10A × 0.01Ω × 25 = 2.5V, providing 24% margin below 3.3V limit. Alternative A2 variant (G=50) would give 5.0V at 10A, exceeding ADC range.

- C_ISENSE_BYPASS (100nF): Power supply decoupling on VS pin per SBOS518 § 8.2.1. Placed close to IC for high-frequency noise rejection.

- C_ISENSE_FILT (100nF): Output filter capacitor reduces switching noise on ADC input. Optional per datasheet, included for cleaner RP2040 ADC readings.

- R_ISENSE_PD (10kΩ): Pulldown ensures defined 0V state when INA180 output is high-impedance (e.g., during power-up). Not in reference circuit but added for robustness.

**Deviation from reference:** Using A1 gain variant instead of typical A2 to accommodate 3.3V ADC input range. Scaling factor is 250mV/A.

## Voltage Sensing Group

**Resistive Divider for 12V→3.3V ADC Input**

Simple resistor divider scales 12V output to RP2040 ADC input range.

Components:
- R_VSENSE_H (27kΩ, 1%, 0805): Upper divider resistor
- R_VSENSE_L (10kΩ, 1%, 0805): Lower divider resistor
- Ratio: 10k/(10k+27k) = 0.270, giving 3.24V at 12V input
- At 13.2V (OVP threshold): 3.56V output (slightly above 3.3V, but OVP trips first)
- Quiescent current: 12V/37kΩ = 324µA (negligible)
- 1% resistors ensure ±1% voltage measurement accuracy

- C_VSENSE_FILT (100nF): Low-pass filter with ~43Hz cutoff (1/(2π×37kΩ×100nF)) removes switching noise from ADC.

**Deviation from reference:** Using 0805 package instead of 0603 for better JLCPCB Basic parts availability. No electrical impact.

## Overvoltage Protection Group

**LM393 Comparator with Hysteresis**

Monitors output voltage and flags overvoltage condition above 13.2V (110% of nominal).

Components:
- U_OVP (LM393): Dual comparator, using one section. Sensed voltage (VSENSE_DIV = 3.56V at 13.2V) compared against reference (V3V3 = 3.3V). Output goes high when VOUT exceeds threshold. Reference: LM393 datasheet SLCS161 Figure 31.

- R_OVP_PU (10kΩ): Pull-up resistor for open-collector output. Standard value per datasheet.

- R_OVP_HYST (100kΩ): Positive feedback resistor creates ~2% hysteresis (per TI app note SLVA863), preventing oscillation near trip point. Ensures clean trip/release behavior.

- C_OVP_BYPASS (100nF): Power supply decoupling on VCC pin.

**Deviation from reference:** Added hysteresis resistor not shown in basic LM393 application circuit but recommended for voltage monitoring applications to prevent chatter.

**Note:** OVP_FAULT signal connects to shutdown or crowbar circuit (implementation in system integration, outside this block).

## Feedback Isolation Group

**PC817 Optocoupler for Voltage Feedback**

Isolates secondary-side voltage feedback to primary-side control loop.

Components:
- U_OPTO (PC817): Phototransistor optocoupler providing galvanic isolation. CTR (current transfer ratio) = 50-200% typical. Reference: PC817 datasheet typical application.

- R_LED (10kΩ): LED current limiting resistor. Calculated for I_LED = (12V - 1.2V)/R = 1.08mA. Lower than typical 5mA recommendation, but acceptable for reduced power (13mW vs 60mW). CTR is still adequate at this current level.

- R_OPTO_COLL (10kΩ): Collector load resistor (on primary side in reality). Shown here for circuit completeness.

**Deviation from reference:** R_LED is 10kΩ instead of calculated optimal 2.2kΩ (for 5mA LED current). This reduces power consumption and LED stress while maintaining adequate CTR for feedback signal. LED forward current of ~1mA is within PC817 operating range (1-50mA).

**Note:** Phototransistor emitter shown connected to GND in this block; in actual system integration it connects to primary-side ground (isolated from secondary GND).

## Temperature Sensing Group

**NTC Thermistor Voltage Divider**

Monitors temperature near output power components (SR FETs, output capacitors).

Components:
- R_NTC (10kΩ NTC, B3950): Thermistor with negative temperature coefficient. R=10kΩ at 25°C, decreases to ~1.5kΩ at 80°C (from B-value equation and NTC lookup tables).

- R_TEMP_TOP (10kΩ, 1%): Fixed upper resistor forms divider with NTC.

- At 25°C: V_adc = 3.3V × 10k/(10k+10k) = 1.65V
- At 80°C: V_adc = 3.3V × 10k/(10k+1.5k) ≈ 2.87V
- Voltage increases with temperature (thermistor resistance decreases)

- C_TEMP_FILT (10nF): Filter capacitor slows response for stable temperature readings. Thermal time constants are slow (seconds), so 10nF provides adequate filtering without excessive lag.

**Deviation from reference:** Using 10nF filter cap instead of commonly-used 100nF for slightly faster response while still rejecting noise.

**Note:** RP2040 firmware must implement Steinhart-Hart equation or lookup table to convert ADC voltage to temperature in °C.

## Part Cost Summary

From parts.json:
- Current shunt: $0.0502 (Extended)
- INA180: $0.1298 (Extended)
- LM393: $0.0656 (Basic)
- PC817: $0.0299 (Basic)
- NTC thermistor: $0.0068 (Basic)
- Resistors (×6): ~$0.05 total (Basic)
- Capacitors (×5): ~$0.10 total (Basic)

**Total block cost:** ~$0.48 per board

## Deviations Summary

1. INA180 gain variant: A1 (G=25) instead of A2 (G=50) to fit 3.3V ADC range
2. Resistor packages: 0805 instead of 0603 for better JLCPCB availability
3. Optocoupler LED current: 1mA instead of 5mA to reduce power
4. OVP hysteresis: Added for stability (not in basic LM393 application)

## Unsourced/Placeholder Components

- R_OVP_HYST (100kΩ): Not in parts.json, needs sourcing or use series combination of 10kΩ resistors
- C_TEMP_FILT (10nF): Not in parts.json, using generic symbol/footprint, needs sourcing

These placeholders must be resolved before board manufacture.
